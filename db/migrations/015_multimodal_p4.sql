-- p4: p3 + richer media preparation (provider default for new stores). Embeddings: EmbeddingGemma 2 only.
--   audio: + time-stamped speech transcripts (faster-whisper base, pinned revision) embedded as text passages
--   video: 720p frames, 280 soft tokens/frame (2x detail), 20 s windows with 4 s overlap (fits the 8,192 budget),
--          + soundtrack audio windows and transcript
--   pdf:   + OCR text of scanned pages (RapidOCR) next to the page image
--   images/text: as p3 (image vectors reused from p1/p2/p3)
INSERT INTO embedding_profiles (id, model, revision, dims, normalize, dtype, query_prompt, document_template, preparation, adapter_version, name)
VALUES ('eg2-914f7f8-fp32-p4', 'google/embeddinggemma-2', '914f7f89142e33e77833254d9c9b90c3cef7303b', 768, true, 'float32',
  'task: search result | query: ', 'title: {title} | text: {content}',
  '{"text":{"strategy":"structure","max_chars":1200,"overlap_chars":200,"min_chars":250,"contextual_title":true},
    "pdf":{"text_min_chars":20,"render_dpi":110,"ocr":true,"ocr_dpi":200},
    "image":{"max_soft_tokens":280},
    "audio":{"sample_rate":16000,"segment_seconds":30,"overlap_seconds":5,
             "transcribe":{"model":"Systran/faster-whisper-base","revision":"ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66","max_chars":600}},
    "video":{"fps":1,"segment_seconds":20,"overlap_seconds":4,"max_height":720,"max_soft_tokens":280,"streams":["video","audio"],
             "audio":{"sample_rate":16000,"segment_seconds":30,"overlap_seconds":5},
             "transcribe":{"model":"Systran/faster-whisper-base","revision":"ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66","max_chars":600}},
    "max_tokens":8192}',
  'kbpy-3', 'Multimodal rich (default)');
INSERT INTO model_aliases (alias, profile_id, purpose) VALUES
  ('eg2-914f7f8-fp32-p4-query', 'eg2-914f7f8-fp32-p4', 'query'),
  ('eg2-914f7f8-fp32-p4-document', 'eg2-914f7f8-fp32-p4', 'document');
