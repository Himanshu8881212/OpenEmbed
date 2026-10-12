-- Hybrid keyword side: English stemming + stop-word removal (codes like PS-400, ISO VG 46 tokenize intact);
-- queries use any-term matching ranked by coverage (ts_rank_cd) so natural-language questions contribute too.
DROP INDEX segments_tsv;
ALTER TABLE segments DROP COLUMN tsv;
ALTER TABLE segments ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;
CREATE INDEX segments_tsv ON segments USING gin (tsv);
