"""
Intelligent chunking service for text extraction and splitting.
Handles TEXT, MARKDOWN, and PDF modalities.
Image/Video/Audio are not chunked (embedded as single units).
"""
import re
import os
from typing import List, Dict, Optional

from app.core.config import settings
from app.core.logger import app_logger as logger


# ── Text Chunking ────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """
    Recursive character splitting with sliding overlap.
    Splits on paragraph breaks → sentence boundaries → hard break,
    then prepends ~overlap chars from the previous chunk so semantics
    spanning chunk boundaries are preserved.
    """
    chunk_size = chunk_size or settings.chunk_size
    if overlap is None:
        overlap = max(0, chunk_size // 6)  # ~16% overlap by default
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    # Try splitting on paragraph boundaries first
    paragraphs = re.split(r'\n\s*\n', text)
    if len(paragraphs) > 1:
        base = _merge_splits(paragraphs, chunk_size)
    else:
        # Try splitting on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 1:
            base = _merge_splits(sentences, chunk_size)
        else:
            base = _hard_split(text, chunk_size)

    return _apply_overlap(base, overlap) if overlap > 0 else base


def _apply_overlap(chunks: List[str], overlap: int) -> List[str]:
    """Prepend the trailing `overlap` chars (cut at word boundary) of the previous chunk."""
    if overlap <= 0 or len(chunks) < 2:
        return chunks
    out = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        tail = prev[-overlap:] if len(prev) > overlap else prev
        # cut at the first whitespace so we don't break a word
        ws = tail.find(' ')
        if ws > 0:
            tail = tail[ws + 1:]
        out.append(f"{tail.strip()} {chunks[i]}".strip() if tail.strip() else chunks[i])
    return out


def _merge_splits(parts: List[str], chunk_size: int) -> List[str]:
    """Merge small parts together until they approach chunk_size."""
    chunks = []
    current = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # If this single part exceeds chunk_size, recursively chunk it
        if len(part) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(chunk_text(part, chunk_size))
            continue

        if current and len(current) + len(part) + 2 > chunk_size:
            chunks.append(current.strip())
            current = part
        else:
            current = f"{current}\n\n{part}" if current else part

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _hard_split(text: str, chunk_size: int) -> List[str]:
    """Split text at word boundaries when no better split point exists."""
    chunks = []
    while len(text) > chunk_size:
        # Find the last space before chunk_size
        split_at = text.rfind(' ', 0, chunk_size)
        if split_at <= 0:
            split_at = chunk_size  # No space found, hard cut
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks


# ── Markdown Chunking ────────────────────────────────────────────

def chunk_markdown(text: str, chunk_size: int = None) -> List[Dict]:
    """
    Split markdown on headers first, then recursive split if sections are too large.
    Preserves header hierarchy in metadata.
    """
    chunk_size = chunk_size or settings.chunk_size
    text = text.strip()
    if not text:
        return []

    # Split on markdown headers (lines starting with # )
    header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    sections = []
    last_end = 0
    current_section = ""

    matches = list(header_pattern.finditer(text))

    if not matches:
        # No headers, treat as plain text
        chunks = chunk_text(text, chunk_size)
        return [{"text": c, "section": ""} for c in chunks]

    # Content before first header
    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

    for i, match in enumerate(matches):
        header = match.group(0).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        full_section = f"{header}\n\n{body}" if body else header
        sections.append((header, full_section))

    # Now chunk each section if needed
    result = []
    for header, content in sections:
        if len(content) <= chunk_size:
            result.append({"text": content, "section": header})
        else:
            # Section too large, sub-chunk it
            sub_chunks = chunk_text(content, chunk_size)
            for sc in sub_chunks:
                result.append({"text": sc, "section": header})

    return result


# ── PDF Text Extraction ──────────────────────────────────────────

def extract_pdf_text(file_bytes: bytes) -> List[Dict]:
    """
    Extract text from PDF using PyMuPDF (fitz).
    Returns per-page text with page numbers.
    """
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()
            if text:
                pages.append({"text": text, "page": page_num + 1})
        doc.close()
        return pages
    except Exception as e:
        logger.warning(f"PDF text extraction failed: {e}")
        return []


def chunk_pdf(file_bytes: bytes, chunk_size: int = None) -> List[Dict]:
    """
    Extract PDF text, then chunk while tracking page numbers.
    Returns empty list if extraction fails (caller falls back to Gemini multimodal).
    """
    chunk_size = chunk_size or settings.chunk_size
    pages = extract_pdf_text(file_bytes)
    if not pages:
        return []

    # Build segments with page tracking
    # Each segment: (text, page_number)
    segments = []
    for page_data in pages:
        page_text = page_data["text"]
        page_num = page_data["page"]
        # Split page text into paragraphs for finer granularity
        paragraphs = re.split(r'\n\s*\n', page_text)
        for para in paragraphs:
            para = para.strip()
            if para:
                segments.append((para, page_num))

    if not segments:
        return []

    # Merge segments into chunks, tracking page ranges
    chunks = []
    current_text = ""
    current_pages = set()

    for seg_text, page_num in segments:
        # If this single segment exceeds chunk_size, handle it
        if len(seg_text) > chunk_size:
            # Flush current
            if current_text:
                chunks.append({
                    "text": current_text.strip(),
                    "page_numbers": ",".join(str(p) for p in sorted(current_pages)),
                })
                current_text = ""
                current_pages = set()
            # Hard-split the large segment
            sub_chunks = chunk_text(seg_text, chunk_size)
            for sc in sub_chunks:
                chunks.append({"text": sc, "page_numbers": str(page_num)})
            continue

        if current_text and len(current_text) + len(seg_text) + 2 > chunk_size:
            chunks.append({
                "text": current_text.strip(),
                "page_numbers": ",".join(str(p) for p in sorted(current_pages)),
            })
            current_text = seg_text
            current_pages = {page_num}
        else:
            current_text = f"{current_text}\n\n{seg_text}" if current_text else seg_text
            current_pages.add(page_num)

    if current_text.strip():
        chunks.append({
            "text": current_text.strip(),
            "page_numbers": ",".join(str(p) for p in sorted(current_pages)),
        })

    return chunks


# ── Main Entry Point ─────────────────────────────────────────────

def chunk_content(file_bytes: bytes, filename: str, modality: str) -> Optional[List[Dict]]:
    """
    Route to the correct chunker based on modality.

    Returns:
        List of chunk dicts for text/markdown/pdf.
        None for image/video/audio (signals single-embedding flow).
    """
    ext = os.path.splitext(filename)[1].lower()

    if modality == "text":
        text = file_bytes.decode("utf-8", errors="replace").strip()
        if not text:
            return None

        if ext == ".md":
            return chunk_markdown(text)
        else:
            chunks = chunk_text(text)
            return [{"text": c} for c in chunks]

    elif modality == "document":
        chunks = chunk_pdf(file_bytes)
        if not chunks:
            return None  # Extraction failed, fall back to multimodal
        return chunks

    else:
        # image, video, audio — no chunking
        return None
