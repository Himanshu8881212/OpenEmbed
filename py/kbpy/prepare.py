"""Source preparation: file -> ordered segments with source locations and model input parts.

Each segment: {"modality", "location", "content" (text or None), "parts": [inference parts]}.
Callers apply the profile's document template to text parts (title = filename).
"""
import base64
import io
import re
import json
import os
import subprocess
import tempfile

import numpy as np


class ItemError(Exception):
    """Item-level failure reported to the user. retryable=False means the source must be corrected."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def chunk_text(text: str, max_chars: int, overlap: int) -> list[tuple[int, int]]:
    """Split into passages <= max_chars, preferring paragraph/line/sentence/word boundaries. Returns (start, end) offsets."""
    out, start, n = [], 0, len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", "\n", ". ", " "):
                k = window.rfind(sep)
                if k > max_chars // 2:
                    end = start + k + len(sep)
                    break
        if text[start:end].strip():
            out.append((start, end))
        if end >= n:
            break
        nxt = max(end - overlap, start + 1)
        sp = text.find(" ", nxt, end)  # start the overlap on a word boundary
        start = sp + 1 if sp != -1 else nxt
    return out


# ---------------------------------------------------------------- structure-aware chunking (profile strategy "structure")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _units_from_text(text: str, base: int = 0, section: str = "", table_header: str | None = None) -> list[dict]:
    """Sentence units with absolute offsets. A unit never spans a paragraph."""
    units, pos = [], 0
    for para in re.split(r"(\n\s*\n)", text):
        if not para.strip() or re.fullmatch(r"\n\s*\n", para):
            pos += len(para)
            continue
        lead = len(para) - len(para.lstrip())
        cursor = pos + lead
        for sent in _SENT.split(para.strip()):
            i = text.find(sent, cursor)
            if i < 0:
                i = cursor
            units.append({"start": base + i, "end": base + i + len(sent), "text": sent, "section": section, "table_header": table_header})
            cursor = i + len(sent)
        pos += len(para)
    return units


def _markdown_units(text: str) -> list[dict]:
    """Markdown: heading lines set the section path (by level); table rows are units that repeat the header row."""
    units, stack, offset, table_header = [], [], 0, None
    lines = text.splitlines(keepends=True)
    block, block_start = [], 0

    def flush():
        nonlocal block
        if block:
            chunk = "".join(block)
            units.extend(_units_from_text(chunk, block_start, " › ".join(t for _, t in stack)))
            block = []

    for line in lines:
        m = _MD_HEADING.match(line.strip())
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip()
            stack[:] = [(l, t) for l, t in stack if l < level] + [(level, title)]
            units.append({"start": offset, "end": offset + len(line.rstrip()), "text": line.strip(), "section": " › ".join(t for _, t in stack), "table_header": None, "heading": True})
            table_header = None
        elif line.lstrip().startswith("|"):
            flush()
            row = line.strip()
            if table_header is None:  # the header row is content too (and is repeated if a passage starts mid-table)
                table_header = row
                units.append({"start": offset, "end": offset + len(line.rstrip()), "text": row, "section": " › ".join(t for _, t in stack), "table_header": table_header})
            elif not re.fullmatch(r"\|[\s:\-|]+\|?", row):
                units.append({"start": offset, "end": offset + len(line.rstrip()), "text": row, "section": " › ".join(t for _, t in stack), "table_header": table_header})
        else:
            if not block:
                block_start = offset
            block.append(line)
            if not line.strip():
                table_header = None
        offset += len(line)
    flush()
    return units


def _pack(units: list[dict], cfg: dict, base_loc: dict | None = None) -> list[dict]:
    """Greedy packing of whole units into passages <= max_chars without crossing sections; sentence-level overlap;
    tiny section tails merged into the previous passage. Over-long units are split at word boundaries."""
    max_c, ovl, min_c = cfg["max_chars"], cfg.get("overlap_chars", 0), cfg.get("min_chars", cfg["max_chars"] // 4)
    flat = []
    for u in units:  # split units longer than max_chars
        if len(u["text"]) <= max_c:
            flat.append(u)
            continue
        for s, e in chunk_text(u["text"], max_c, 0):
            flat.append({**u, "start": u["start"] + s, "end": u["start"] + e, "text": u["text"][s:e].strip()})
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    size = lambda us: sum(len(x["text"]) + 1 for x in us)
    for u in flat:
        if cur and (u["section"] != cur[-1]["section"] or size(cur) + len(u["text"]) > max_c):
            chunks.append(cur)
            carry = []
            if u["section"] == cur[-1]["section"] and ovl:
                for x in reversed(cur):  # whole trailing sentences, same section, within the overlap budget
                    if x.get("heading") or size(carry) + len(x["text"]) > ovl:
                        break
                    carry.insert(0, x)
            cur = carry if size(carry) + len(u["text"]) <= max_c else []
        cur.append(u)
    if cur:
        chunks.append(cur)
    merged: list[list[dict]] = []
    for c in chunks:  # merge tiny tails into the previous passage of the same section
        own = [x for x in c if not any(x is y for y in (merged[-1] if merged else []))]
        if merged and size(own) < min_c and c[-1]["section"] == merged[-1][-1]["section"] and size(merged[-1]) + size(own) <= int(max_c * 1.25):
            merged[-1] = merged[-1] + own
        else:
            merged.append(c)
    segs = []
    for c in merged:
        if not any(x["text"].strip() for x in c) or all(x.get("heading") for x in c):
            continue
        # repeat a table's header row only when the passage starts inside that table
        header = c[0].get("table_header") if c[0].get("table_header") and c[0]["text"] != c[0]["table_header"] else None
        body = "\n".join(x["text"] for x in c)
        content = f"{header}\n{body}" if header else body
        loc = {**(base_loc or {}), "start": c[0]["start"], "end": c[-1]["end"]}
        if c[-1]["section"]:
            loc["section"] = c[-1]["section"][:200]
        segs.append({"modality": "text", "location": loc, "content": content, "parts": [{"type": "text", "text": content}]})
    return segs


def structure_segments(text: str, cfg: dict, markdown: bool = True, base_loc: dict | None = None) -> list[dict]:
    return _pack(_markdown_units(text) if markdown else _units_from_text(text), cfg, base_loc)


def _text_segments(text: str, cfg: dict, extra_loc: dict | None = None) -> list[dict]:
    segs = []
    for s, e in chunk_text(text, cfg["max_chars"], cfg["overlap_chars"]):
        passage = text[s:e].strip()
        segs.append({"modality": "text", "location": {**(extra_loc or {}), "start": s, "end": e}, "content": passage,
                     "parts": [{"type": "text", "text": passage}]})
    return segs


def prepare_text(data: bytes, cfg: dict) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ItemError("UNREADABLE", "text file is not valid UTF-8")
    if "\x00" in text:
        raise ItemError("UNREADABLE", "text file contains NUL bytes (binary?)")
    segs = structure_segments(text, cfg) if cfg.get("strategy") == "structure" else _text_segments(text, cfg)
    if not segs:
        raise ItemError("EMPTY_CONTENT", "file has no text content")
    return segs


def prepare_pdf(data: bytes, cfg: dict, text_cfg: dict) -> list[dict]:
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        msg = str(e).lower()
        if "password" in msg:
            raise ItemError("UNREADABLE", "PDF is encrypted; supply an authorised readable version")
        raise ItemError("UNREADABLE", "PDF could not be parsed")
    segs = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            text = page.get_textpage().get_text_range().replace("\r\n", "\n").replace("\r", "\n")
            if len(text.strip()) >= cfg["text_min_chars"]:
                segs += structure_segments(text, text_cfg, markdown=False, base_loc={"page": i + 1}) if text_cfg.get("strategy") == "structure" else _text_segments(text, text_cfg, {"page": i + 1})
            else:  # scanned page: embed the rendered page image
                img = page.render(scale=cfg["render_dpi"] / 72).to_pil().convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                segs.append({"modality": "image", "location": {"page": i + 1}, "content": None,
                             "parts": [{"type": "image", "data_b64": b64(buf.getvalue())}]})
                if cfg.get("ocr"):  # also make the scanned words searchable (keeps the page image segment)
                    hi = io.BytesIO()
                    page.render(scale=cfg.get("ocr_dpi", 200) / 72).to_pil().convert("RGB").save(hi, format="PNG")
                    words = ocr_text(hi.getvalue())
                    if len(words.strip()) >= cfg["text_min_chars"]:
                        for s in structure_segments(words, text_cfg, markdown=False, base_loc={"page": i + 1, "kind": "ocr"}):
                            segs.append(s)
    finally:
        pdf.close()
    if not segs:
        raise ItemError("EMPTY_CONTENT", "PDF has no pages")
    return segs


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def prepare_docx(data: bytes, cfg: dict) -> list[dict]:
    """Word (.docx): body paragraphs and tables in document order. Location = char offsets in the extracted text plus
    the nearest preceding heading (`section`). Headers/footers, comments and text boxes are not extracted."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        d = docx.Document(io.BytesIO(data))
    except Exception:
        raise ItemError("UNREADABLE", "DOCX could not be opened (encrypted, damaged or not a .docx file)")
    if cfg.get("strategy") == "structure":
        return _docx_structure(d, cfg, Paragraph, Table)
    blocks, headings, pos = [], [], 0
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            text = p.text.strip()
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            if style.lower().startswith(("heading", "title")):
                headings.append((pos, text))
        elif tag == "tbl":
            rows = []
            for r in Table(el, d).rows:
                cells, seen = [], set()
                for c in r.cells:  # merged cells repeat; keep each once
                    if id(c._tc) not in seen:
                        seen.add(id(c._tc))
                        cells.append(c.text.strip())
                rows.append(" | ".join(cells))
            text = "\n".join(x for x in rows if x.strip(" |"))
            if not text:
                continue
        else:
            continue
        blocks.append(text)
        pos += len(text) + 2
    full = "\n\n".join(blocks)
    segs = _text_segments(full, cfg)
    if not segs:
        raise ItemError("EMPTY_CONTENT", "DOCX has no text content")
    for s in segs:
        sec = [h for o, h in headings if o <= s["location"]["start"]]
        if sec:
            s["location"]["section"] = sec[-1][:200]
    return segs


def _docx_structure(d, cfg: dict, Paragraph, Table) -> list[dict]:
    """Heading levels form the section path; paragraphs become sentence units; each table row is a unit that repeats
    the header row when a passage starts mid-table. Offsets refer to the extracted text (blocks joined by blank lines)."""
    units, stack, pos = [], [], 0
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            text = p.text.strip()
            if not text:
                continue
            style = ((p.style.name if p.style is not None else "") or "").lower()
            m = re.match(r"heading (\d)", style)
            if style.startswith("title") or m:
                level = 0 if style.startswith("title") else int(m.group(1))
                stack[:] = [(l, t) for l, t in stack if l < level] + [(level, text)]
                units.append({"start": pos, "end": pos + len(text), "text": text, "section": " › ".join(t for _, t in stack), "table_header": None, "heading": True})
            else:
                units.extend(_units_from_text(text, pos, " › ".join(t for _, t in stack)))
        elif tag == "tbl":
            header, rowpos = None, pos
            for r in Table(el, d).rows:
                cells, seen = [], set()
                for c in r.cells:
                    if id(c._tc) not in seen:
                        seen.add(id(c._tc))
                        cells.append(c.text.strip())
                row = " | ".join(cells)
                if not row.strip(" |"):
                    continue
                if header is None:
                    header = row
                units.append({"start": rowpos, "end": rowpos + len(row), "text": row, "section": " › ".join(t for _, t in stack), "table_header": header})
                rowpos += len(row) + 1
            pos = rowpos + 1
            continue
        else:
            continue
        pos += len(text) + 2
    segs = _pack(units, cfg)
    if not segs:
        raise ItemError("EMPTY_CONTENT", "DOCX has no text content")
    return segs


def prepare_image(data: bytes) -> list[dict]:
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception:
        raise ItemError("UNREADABLE", "image could not be decoded")
    return [{"modality": "image", "location": {"type": "whole_image"}, "content": None,
             "parts": [{"type": "image", "data_b64": b64(data)}]}]


# ---------------------------------------------------------------- transcripts (ASR) and OCR: preparation, not embedding.
# Their text is embedded by EmbeddingGemma 2 like any passage. Models are pinned in the profile's preparation config.
_asr_models: dict = {}
_ocr = None


def _pcm16k(path: str) -> "np.ndarray":
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"], capture_output=True)
    if r.returncode != 0:
        return np.zeros(0, dtype=np.float32)  # no audio stream
    return np.frombuffer(r.stdout, dtype=np.float32)


def transcribe(path: str, cfg: dict) -> list[dict]:
    """Speech → time-stamped transcript passages (text segments, location kind=transcript). Silence/music yields none
    (voice-activity filter + no-speech probability), so tones never become hallucinated text."""
    audio = _pcm16k(path)
    if audio.size < 16000 * 0.5:
        return []
    from faster_whisper import WhisperModel
    key = (cfg["model"], cfg["revision"])
    if key not in _asr_models:
        _asr_models[key] = WhisperModel(cfg["model"], revision=cfg["revision"], device="cpu", compute_type="int8")
    segs, _ = _asr_models[key].transcribe(audio, vad_filter=True, beam_size=5)
    lines = [s for s in segs if s.no_speech_prob < 0.6 and s.text.strip()]
    out, buf = [], []
    max_c = cfg.get("max_chars", 600)
    for s in lines:  # group consecutive lines into passages of at most max_chars
        if buf and sum(len(x.text) for x in buf) + len(s.text) > max_c:
            out.append(buf)
            buf = []
        buf.append(s)
    if buf:
        out.append(buf)
    return [{"modality": "text", "location": {"start_seconds": round(b[0].start, 2), "end_seconds": round(b[-1].end, 2), "kind": "transcript"},
             "content": " ".join(x.text.strip() for x in b), "parts": [{"type": "text", "text": " ".join(x.text.strip() for x in b)}]} for b in out]


def ocr_text(png: bytes, min_confidence: float = 0.6) -> str:
    """Scanned page → text lines (RapidOCR, Apache-2.0, bundled models), top-to-bottom reading order."""
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    res, _ = _ocr(png)
    lines = sorted((r for r in (res or []) if float(r[2]) >= min_confidence), key=lambda r: (round(r[0][0][1] / 12), r[0][0][0]))
    return "\n".join(r[1] for r in lines)


def _ffprobe_duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path], capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        raise ItemError("UNREADABLE", "media could not be decoded")


def _ffmpeg(args: list[str]) -> bytes:
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", *args], capture_output=True)
    if r.returncode != 0:
        raise ItemError("UNREADABLE", "media could not be decoded")
    return r.stdout


def _windows(duration: float, seconds: float, overlap: float = 0.0) -> list[tuple[float, float]]:
    """Fixed windows; with overlap, stride = seconds - overlap and a short tail (< 30% of a window) extends the
    previous window instead of becoming a near-empty segment. overlap=0 keeps the original behaviour."""
    out, t = [], 0.0
    stride = seconds - overlap if 0 < overlap < seconds else seconds
    while t < duration - 0.05:
        end = min(duration, t + seconds)
        if overlap and out and (end - t) < 0.3 * seconds and end - out[-1][0] <= seconds * 1.3:
            out[-1] = (out[-1][0], round(end, 3))
            break
        out.append((round(t, 3), round(end, 3)))
        if end >= duration:
            break
        t += stride
    return out


def prepare_audio(path: str, cfg: dict) -> list[dict]:
    dur = _ffprobe_duration(path)
    segs = []
    for s, e in _windows(dur, cfg["segment_seconds"], cfg.get("overlap_seconds", 0)):
        wav = _ffmpeg(["-ss", str(s), "-t", str(e - s), "-i", path, "-ac", "1", "-ar", str(cfg["sample_rate"]), "-f", "wav", "pipe:1"])
        segs.append({"modality": "audio", "location": {"start_seconds": s, "end_seconds": e}, "content": None,
                     "parts": [{"type": "audio", "data_b64": b64(wav)}]})
    if not segs:
        raise ItemError("EMPTY_CONTENT", "audio has no duration")
    if cfg.get("transcribe"):
        segs += transcribe(path, cfg["transcribe"])
    return segs


def prepare_video(path: str, cfg: dict) -> list[dict]:
    if not cfg.get("streams") or set(cfg["streams"]) - {"video", "audio"}:
        raise ItemError("FORMAT_UNSUPPORTED", "profile requests unsupported video streams")
    max_h = int(cfg.get("max_height", 480))
    dur = _ffprobe_duration(path)
    segs = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (s, e) in enumerate(_windows(dur, cfg["segment_seconds"], cfg.get("overlap_seconds", 0))):
            out = os.path.join(tmp, f"{i}.mp4")
            _ffmpeg(["-ss", str(s), "-t", str(e - s), "-i", path, "-an", "-vf", f"fps={cfg['fps']},scale=-2:'min({max_h},ih)'",
                     "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-y", out])
            with open(out, "rb") as f:
                segs.append({"modality": "video", "location": {"start_seconds": s, "end_seconds": e}, "content": None,
                             "parts": [{"type": "video", "data_b64": b64(f.read())}]})
    if not segs:
        raise ItemError("EMPTY_CONTENT", "video has no duration")
    if "audio" in cfg["streams"] and _pcm16k(path).size >= 16000:  # soundtrack: audio windows + spoken transcript
        acfg = cfg.get("audio", {"sample_rate": 16000, "segment_seconds": 30, "overlap_seconds": 5})
        for s, e in _windows(dur, acfg["segment_seconds"], acfg.get("overlap_seconds", 0)):
            wav = _ffmpeg(["-ss", str(s), "-t", str(e - s), "-i", path, "-vn", "-ac", "1", "-ar", str(acfg["sample_rate"]), "-f", "wav", "pipe:1"])
            segs.append({"modality": "audio", "location": {"start_seconds": s, "end_seconds": e, "kind": "soundtrack"}, "content": None,
                         "parts": [{"type": "audio", "data_b64": b64(wav)}]})
        if cfg.get("transcribe"):
            segs += transcribe(path, cfg["transcribe"])
    return segs


def prepare(path: str, media_type: str, prep: dict) -> list[dict]:
    """Dispatch on the server-assigned media type (from the validated extension list)."""
    if media_type in ("text/plain", "text/markdown"):
        with open(path, "rb") as f:
            return prepare_text(f.read(), prep["text"])
    if media_type == DOCX_TYPE:
        with open(path, "rb") as f:
            return prepare_docx(f.read(), prep["text"])
    if media_type == "application/pdf":
        with open(path, "rb") as f:
            return prepare_pdf(f.read(), prep["pdf"], prep["text"])
    if media_type in ("image/jpeg", "image/png"):
        with open(path, "rb") as f:
            return prepare_image(f.read())
    if media_type in ("audio/wav", "audio/mpeg"):
        return prepare_audio(path, prep["audio"])
    if media_type == "video/mp4":
        return prepare_video(path, prep["video"])
    raise ItemError("FORMAT_UNSUPPORTED", f"{media_type} is not supported")
