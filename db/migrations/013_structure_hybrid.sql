-- p3: structure-aware preparation (provider default for new stores). Same pinned model/runtime as p1/p2.
--   text/markdown/docx/pdf: heading-aware sections, sentence-level packing and overlap, tiny-tail merge,
--                            contextual title (file › section · page) in the embedding input, table header repeat
--   audio/video: 30 s windows with 5 s overlap, short tails merged; images unchanged (vectors reusable from p1/p2)
INSERT INTO embedding_profiles (id, model, revision, dims, normalize, dtype, query_prompt, document_template, preparation, adapter_version, name)
VALUES ('eg2-914f7f8-fp32-p3', 'google/embeddinggemma-2', '914f7f89142e33e77833254d9c9b90c3cef7303b', 768, true, 'float32',
  'task: search result | query: ', 'title: {title} | text: {content}',
  '{"text":{"strategy":"structure","max_chars":1200,"overlap_chars":200,"min_chars":250,"contextual_title":true},
    "pdf":{"text_min_chars":20,"render_dpi":110},"image":{"max_soft_tokens":280},
    "audio":{"sample_rate":16000,"segment_seconds":30,"overlap_seconds":5},
    "video":{"fps":1,"segment_seconds":30,"overlap_seconds":5,"streams":["video"]},"max_tokens":8192}',
  'kbpy-2', 'Structure-aware (default)');
INSERT INTO model_aliases (alias, profile_id, purpose) VALUES
  ('eg2-914f7f8-fp32-p3-query', 'eg2-914f7f8-fp32-p3', 'query'),
  ('eg2-914f7f8-fp32-p3-document', 'eg2-914f7f8-fp32-p3', 'document');

-- Hybrid retrieval: language-neutral full-text index over passage text ('simple' keeps codes like PS-400, ISO VG 46).
ALTER TABLE segments ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED;
CREATE INDEX segments_tsv ON segments USING gin (tsv);
