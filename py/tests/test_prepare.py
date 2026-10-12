"""Preparation unit tests (no services). Run: cd py && uv run python -m unittest discover -s tests"""
import os
import unittest

from kbpy.prepare import ItemError, _windows, chunk_text, prepare, prepare_pdf, prepare_text

CORPUS = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures", "corpus")
PREP = {"text": {"max_chars": 1600, "overlap_chars": 200}, "pdf": {"text_min_chars": 20, "render_dpi": 72},
        "audio": {"sample_rate": 16000, "segment_seconds": 30}, "video": {"fps": 1, "segment_seconds": 30, "streams": ["video"]}}


class ChunkText(unittest.TestCase):
    def test_bounds_and_full_coverage(self):
        text = ("Sentence number %d is here. " * 400) % tuple(range(400))
        spans = chunk_text(text, 500, 80)
        self.assertTrue(all(e - s <= 500 for s, e in spans))
        covered = set()
        for s, e in spans:
            covered.update(range(s, e))
        self.assertEqual(covered, set(range(len(text))), "no text may be silently dropped")
        self.assertTrue(all(b[0] < a[1] for a, b in zip(spans, spans[1:])), "consecutive passages overlap")

    def test_no_whitespace_runs_forever(self):
        spans = chunk_text("x" * 5000, 1000, 100)
        self.assertEqual(spans[0], (0, 1000))
        self.assertEqual(spans[-1][1], 5000)

    def test_offsets_point_at_content(self):
        text = "alpha\n\nbeta gamma\n\ndelta"
        for s, e in chunk_text(text, 12, 2):
            self.assertIn(text[s:e].strip(), text)


class StructureChunking(unittest.TestCase):
    CFG = {"strategy": "structure", "max_chars": 400, "overlap_chars": 80, "min_chars": 60}

    def test_sections_tables_overlap_and_offsets(self):
        from kbpy.prepare import structure_segments
        text = open(os.path.join(CORPUS, "..", "structured", "turbine-service-manual.md")).read()
        segs = structure_segments(text, self.CFG)
        sections = [s["location"]["section"] for s in segs]
        self.assertIn("WT-3 Wind Turbine Service Manual › 2. Gearbox › 2.1 Gearbox torque values", sections)
        for s in segs:
            self.assertLessEqual(len(s["content"]), int(self.CFG["max_chars"] * 1.4))
            self.assertTrue(text[s["location"]["start"]:s["location"]["end"]].strip(), "offsets point into the source")
        table = [s for s in segs if "Sensor bracket" in s["content"]][0]
        self.assertIn("| Fastener | Torque |", table["content"], "column names travel with the rows")
        same = [(a, b) for a, b in zip(segs, segs[1:]) if a["location"].get("section") == b["location"].get("section")]
        self.assertTrue(any(b["location"]["start"] < a["location"]["end"] for a, b in same), "sentence overlap within a section")
        covered = "".join(s["content"] for s in segs)
        for fact in ("ISO VG 320", "400 g", "50 milliohm", "GX-18", "2,850 Nm"):
            self.assertIn(fact, covered, "no content dropped")

    def test_long_sentence_is_split_not_dropped(self):
        from kbpy.prepare import structure_segments
        segs = structure_segments("# T\n\n" + "word " * 400, self.CFG)
        self.assertGreater(len(segs), 2)
        self.assertTrue(all(len(s["content"]) <= 400 for s in segs))

    def test_docx_structure_headings_and_table_header(self):
        segs = prepare(os.path.join(CORPUS, "manuals/compressor-maintenance.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       {**PREP, "text": {**self.CFG, "max_chars": 160, "overlap_chars": 40, "min_chars": 40}})
        self.assertTrue(all(s["location"].get("section", "").startswith("Air compressor maintenance") for s in segs))
        self.assertTrue(any(s["content"].startswith("Task | Interval") and "Separator element" in s["content"] for s in segs))

    def test_overlapping_media_windows(self):
        self.assertEqual(_windows(65, 30, 5), [(0.0, 30.0), (25.0, 55.0), (50.0, 65)])
        self.assertEqual(_windows(56, 30, 5), [(0.0, 30.0), (25.0, 56)])  # short tail merged into the previous window
        self.assertEqual(_windows(65, 30), [(0.0, 30.0), (30.0, 60.0), (60.0, 65)])  # p1/p2 behaviour unchanged


P4 = {**PREP,
      "pdf": {"text_min_chars": 20, "render_dpi": 72, "ocr": True, "ocr_dpi": 200},
      "audio": {**PREP["audio"], "transcribe": {"model": "Systran/faster-whisper-base", "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"}},
      "video": {"fps": 1, "segment_seconds": 20, "overlap_seconds": 4, "max_height": 720, "streams": ["video", "audio"],
                "transcribe": {"model": "Systran/faster-whisper-base", "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"}}}


class RichMedia(unittest.TestCase):
    def test_speech_is_transcribed_with_times(self):
        segs = prepare(os.path.join(CORPUS, "media/sensor-instructions.mp3"), "audio/mpeg", P4)
        t = [s for s in segs if s["location"].get("kind") == "transcript"]
        self.assertEqual(len(t), 1)
        self.assertIn("pressure sensor", t[0]["content"].lower())
        self.assertLess(t[0]["location"]["start_seconds"], t[0]["location"]["end_seconds"])
        self.assertTrue(any(s["modality"] == "audio" for s in segs), "the audio itself is still embedded")

    def test_no_speech_no_transcript(self):
        segs = prepare(os.path.join(CORPUS, "..", "tone.wav"), "audio/wav", P4)
        self.assertFalse([s for s in segs if s["location"].get("kind") == "transcript"], "tones must not hallucinate text")

    def test_scanned_pdf_gets_ocr_text_and_keeps_page_image(self):
        segs = prepare(os.path.join(CORPUS, "media/scanned-notice.pdf"), "application/pdf", P4)
        self.assertTrue(any(s["modality"] == "image" and s["location"] == {"page": 1} for s in segs))
        ocr = [s for s in segs if s["location"].get("kind") == "ocr"]
        self.assertTrue(ocr and "emergency shower" in ocr[0]["content"].lower() and "bay 4" in ocr[0]["content"].lower())

    def test_video_soundtrack_and_sharper_frames(self):
        segs = prepare(os.path.join(CORPUS, "media/charger-briefing.mp4"), "video/mp4", P4)
        kinds = {(s["modality"], s["location"].get("kind")) for s in segs}
        self.assertEqual(kinds, {("video", None), ("audio", "soundtrack"), ("text", "transcript")})
        self.assertIn("battery terminals", [s for s in segs if s["modality"] == "text"][0]["content"].lower())
        silent = prepare(os.path.join(CORPUS, "media/test-pattern.mp4"), "video/mp4", P4)
        self.assertEqual({s["modality"] for s in silent}, {"video"}, "no soundtrack, no audio/transcript segments")


class Formats(unittest.TestCase):
    def test_invalid_utf8_is_unreadable(self):
        with self.assertRaises(ItemError) as c:
            prepare_text(b"\xff\xfe\xfa", PREP["text"])
        self.assertEqual(c.exception.code, "UNREADABLE")
        self.assertFalse(c.exception.retryable)

    def test_empty_text(self):
        with self.assertRaises(ItemError) as c:
            prepare_text(b"   \n ", PREP["text"])
        self.assertEqual(c.exception.code, "EMPTY_CONTENT")

    def test_text_pdf_has_page_locations(self):
        segs = prepare(os.path.join(CORPUS, "manuals/hydraulic-pump.pdf"), "application/pdf", PREP)
        self.assertEqual(segs[0]["location"]["page"], 1)
        self.assertIn("HK-77", segs[0]["content"])

    def test_scanned_pdf_becomes_page_image(self):
        segs = prepare(os.path.join(CORPUS, "media/scanned-diagram.pdf"), "application/pdf", PREP)
        self.assertEqual([(s["modality"], s["location"]) for s in segs], [("image", {"page": 1})])

    def test_corrupt_pdf(self):
        with self.assertRaises(ItemError) as c:
            prepare_pdf(b"%PDF-1.4 not really", PREP["pdf"], PREP["text"])
        self.assertEqual(c.exception.code, "UNREADABLE")

    def test_encrypted_pdf(self):
        with open(os.path.join(CORPUS, "..", "encrypted.pdf"), "rb") as f:  # made with pikepdf (user password)
            data = f.read()
        with self.assertRaises(ItemError) as c:
            prepare_pdf(data, PREP["pdf"], PREP["text"])
        self.assertEqual(c.exception.code, "UNREADABLE")
        self.assertIn("encrypted", c.exception.message)

    def test_docx_paragraphs_tables_and_sections(self):
        segs = prepare(os.path.join(CORPUS, "manuals/compressor-maintenance.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", PREP)
        text = " ".join(s["content"] for s in segs)
        for needle in ("Daily checks", "ISO VG 46", "Separator element | 8,000 h"):
            self.assertIn(needle, text)
        self.assertEqual(segs[0]["modality"], "text")
        self.assertIn("section", segs[0]["location"])
        small = prepare(os.path.join(CORPUS, "manuals/compressor-maintenance.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", {**PREP, "text": {"max_chars": 120, "overlap_chars": 10}})
        self.assertTrue(any(s["location"].get("section") == "Oil change" for s in small), [s["location"] for s in small])

    def test_corrupt_docx(self):
        from kbpy.prepare import prepare_docx
        for data in (b"not a zip", open(os.path.join(CORPUS, "..", "encrypted.pdf"), "rb").read()):
            with self.assertRaises(ItemError) as c:
                prepare_docx(data, PREP["text"])
            self.assertEqual(c.exception.code, "UNREADABLE")

    def test_media_time_ranges(self):
        a = prepare(os.path.join(CORPUS, "media/sensor-instructions.mp3"), "audio/mpeg", PREP)
        self.assertEqual(a[0]["location"]["start_seconds"], 0.0)
        self.assertGreater(a[0]["location"]["end_seconds"], 3)
        v = prepare(os.path.join(CORPUS, "media/test-pattern.mp4"), "video/mp4", PREP)
        self.assertEqual(v[0]["modality"], "video")

    def test_corrupt_media(self):
        with tempfile_with(b"not audio") as p:
            with self.assertRaises(ItemError):
                prepare(p, "audio/wav", PREP)

    def test_windows(self):
        self.assertEqual(_windows(65, 30), [(0.0, 30.0), (30.0, 60.0), (60.0, 65.0)])

    def test_unknown_type(self):
        with self.assertRaises(ItemError) as c:
            prepare("/dev/null", "application/x-msdownload", PREP)
        self.assertEqual(c.exception.code, "FORMAT_UNSUPPORTED")


class tempfile_with:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        import tempfile
        self.f = tempfile.NamedTemporaryFile(delete=False)
        self.f.write(self.data)
        self.f.close()
        return self.f.name

    def __exit__(self, *a):
        os.unlink(self.f.name)


if __name__ == "__main__":
    unittest.main()
