import { z } from "zod";
import type { Db } from "./db";
import { ApiError } from "./http";
import { embed, queryText, toVector, type Part, type Profile } from "./inference";
import { enforce, record } from "./usage";

export const Filter = z.object({
  metadata: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])).optional(),
  path_prefix: z.string().max(1024).optional(),
  media_types: z.array(z.string()).max(20).optional(),
}).strict();
export type Filter = z.infer<typeof Filter>;

/** Query vector for a store profile; meters query tokens (hard cap enforced before inference). */
export async function queryVector(db: Db, profile: Profile, parts: Part[], requestId: string) {
  await enforce(db, "query");
  const input = parts.map((p) => (p.type === "text" ? { ...p, text: queryText(profile, p.text) } : p));
  const [r] = await embed(profile, [input]);
  const media = parts.some((p) => p.type !== "text");
  await record(db, media ? "query_media_tokens" : "query_text_tokens", r.tokens, `q:${requestId}`);
  return r;
}

/**
 * Ranked segments from the store's resolved membership with the active profile.
 * exact=false: HNSW with iterative scan (pgvector 0.8) so selective filters still fill the limit.
 * Membership and workspace are joined inside the scan and re-checked on the final rows.
 */
export const MODALITIES = ["text", "image", "audio", "video"] as const;

export async function searchSegments(db: Db, storeId: string, profileId: string, vector: number[], limit: number, filter: Filter = {}, exact = false, modalities: string[] | null = null) {
  if (exact) await db.query("SET LOCAL enable_indexscan = off");
  else {
    await db.query("SET LOCAL hnsw.iterative_scan = relaxed_order");
    await db.query(`SET LOCAL hnsw.ef_search = ${Math.max(40, Math.min(1000, limit * 4))}`);
  }
  const { rows } = await db.query(`
    WITH m AS MATERIALIZED (
      SELECT mm.file_id, mm.version_id FROM kb_store_members($1) mm
        JOIN files f ON f.id = mm.file_id JOIN file_versions fv ON fv.id = mm.version_id
       WHERE f.metadata @> $4::jsonb AND ($5::text IS NULL OR starts_with(f.path, $5)) AND ($6::text[] IS NULL OR fv.media_type = ANY($6))
    ),
    hits AS (
      SELECT s.id, s.file_version_id, s.modality, s.location, s.content, s.embedding <=> $2::vector AS distance
        FROM segments s WHERE s.profile_id = $3 AND s.file_version_id IN (SELECT version_id FROM m) AND ($8::text[] IS NULL OR s.modality = ANY($8))
       ORDER BY s.embedding <=> $2::vector LIMIT $7
    )
    SELECT h.*, m.file_id, fv.filename, fv.version_no, fv.media_type, f.path, f.metadata
      FROM hits h JOIN m ON m.version_id = h.file_version_id JOIN files f ON f.id = m.file_id AND f.deleted_at IS NULL
      JOIN file_versions fv ON fv.id = h.file_version_id
     ORDER BY h.distance, h.id`,
    [storeId, toVector(vector), profileId, JSON.stringify(filter.metadata ?? {}), filter.path_prefix ?? null, filter.media_types ?? null, limit, modalities]);
  return rows;
}

const RRF_K = 60;

/**
 * Identifier-like tokens (contain a digit, or 2+ capitals): the cases dense retrieval misses. Natural-language words are
 * left to the embeddings: matching them as keywords promotes chunks that merely share common terms (measured: answer@1
 * dropped 0.7 → 0.3 on the DUNE sheets with any-term matching).
 */
export function identifiers(text: string): string[] {
  return [...new Set((text.match(/[A-Za-z0-9][\w.\-\/]*/g) ?? []).filter((t) => /\d/.test(t) || /^[A-Z]{2,}[\w\-]*$/.test(t)))].slice(0, 12);
}

/**
 * Hybrid retrieval: Reciprocal Rank Fusion of the vector ranking and an identifier keyword ranking (Postgres English
 * tsvector; all *selective* identifier tokens must match, e.g. "PS-400", "ISO VG 46"; tokens present in >10% of the
 * store's passages are dropped as non-discriminating). Without such identifiers it is the vector ranking.
 * ponytail: document frequency is counted per query over the store's passages; precompute ts_stat per store if stores grow
 * past ~10^6 passages. Both candidate lists are drawn from the same resolved
 * membership, profile and filters; `score` stays the cosine similarity, ordering follows the fused rank.
 */
export async function searchHybrid(db: Db, storeId: string, profileId: string, vector: number[], text: string, limit: number, filter: Filter = {}, exact = false, modalities: string[] | null = null) {
  if (exact) await db.query("SET LOCAL enable_indexscan = off");
  else {
    await db.query("SET LOCAL hnsw.iterative_scan = relaxed_order");
    await db.query(`SET LOCAL hnsw.ef_search = ${Math.max(40, Math.min(1000, limit * 8))}`);
  }
  const n = Math.max(limit * 4, 40);
  const { rows } = await db.query(`
    WITH m AS MATERIALIZED (
      SELECT mm.file_id, mm.version_id FROM kb_store_members($1) mm
        JOIN files f ON f.id = mm.file_id JOIN file_versions fv ON fv.id = mm.version_id
       WHERE f.metadata @> $4::jsonb AND ($5::text IS NULL OR starts_with(f.path, $5)) AND ($6::text[] IS NULL OR fv.media_type = ANY($6))
    ),
    elig AS (SELECT count(*) AS n FROM segments s WHERE s.profile_id = $3 AND s.file_version_id IN (SELECT version_id FROM m) AND s.content IS NOT NULL),
    -- keep identifiers that discriminate: present in the store but in at most 10% of eligible passages
    df AS (SELECT t, (SELECT count(*) FROM segments s WHERE s.profile_id = $3 AND s.file_version_id IN (SELECT version_id FROM m)
                       AND s.tsv @@ plainto_tsquery('english', t)) AS d FROM unnest($9::text[]) t),
    q AS (SELECT CASE WHEN count(*) = 0 THEN NULL ELSE plainto_tsquery('english', string_agg(t, ' ')) END AS tq
            FROM df, elig WHERE d > 0 AND d <= greatest(1, elig.n * 0.1)),
    vec AS (
      SELECT s.id, row_number() OVER (ORDER BY s.embedding <=> $2::vector) AS rk FROM (
        SELECT s.id, s.embedding FROM segments s
         WHERE s.profile_id = $3 AND s.file_version_id IN (SELECT version_id FROM m) AND ($8::text[] IS NULL OR s.modality = ANY($8))
         ORDER BY s.embedding <=> $2::vector LIMIT $7) s
    ),
    kw AS (
      SELECT s.id, row_number() OVER (ORDER BY ts_rank_cd(s.tsv, q.tq) DESC, s.id) AS rk
        FROM segments s, q
       WHERE q.tq IS NOT NULL AND s.tsv @@ q.tq AND s.profile_id = $3 AND s.file_version_id IN (SELECT version_id FROM m)
         AND ($8::text[] IS NULL OR s.modality = ANY($8))
       ORDER BY ts_rank_cd(s.tsv, q.tq) DESC, s.id LIMIT $7
    ),
    fused AS (
      SELECT id, sum(1.0 / (${RRF_K} + rk)) AS rrf, min(rk) FILTER (WHERE src = 'kw') AS kw_rank, min(rk) FILTER (WHERE src = 'vec') AS vec_rank
        FROM (SELECT id, rk, 'vec' AS src FROM vec UNION ALL SELECT id, rk, 'kw' FROM kw) x GROUP BY id
    )
    SELECT s.id, s.file_version_id, s.modality, s.location, s.content, s.embedding <=> $2::vector AS distance,
           fu.rrf, fu.kw_rank, fu.vec_rank, m.file_id, fv.filename, fv.version_no, fv.media_type, f.path, f.metadata
      FROM fused fu JOIN segments s ON s.id = fu.id JOIN m ON m.version_id = s.file_version_id
      JOIN files f ON f.id = m.file_id AND f.deleted_at IS NULL JOIN file_versions fv ON fv.id = s.file_version_id
     ORDER BY fu.rrf DESC, distance, s.id LIMIT $10`,
    [storeId, toVector(vector), profileId, JSON.stringify(filter.metadata ?? {}), filter.path_prefix ?? null, filter.media_types ?? null, n, modalities, identifiers(text), limit]);
  return rows;
}

/**
 * Balanced multimodal ranking. Cross-modal similarities sit on different scales (text→text scores run higher than
 * text→image: the "modality gap"), so a single score ordering hides media. Rank within each modality, then interleave
 * by that rank (ties: higher score first). Each result keeps its raw score and gets `modality_rank`.
 */
export async function searchBalanced(db: Db, storeId: string, profileId: string, vector: number[], limit: number, filter: Filter, exact: boolean, modalities: readonly string[], text: string | null = null) {
  const per = [];
  for (const m of modalities) { // sequential: one connection/transaction (SET LOCAL scan settings apply to each query)
    const rows = text && m === "text" ? await searchHybrid(db, storeId, profileId, vector, text, limit, filter, exact, [m]) : await searchSegments(db, storeId, profileId, vector, limit, filter, exact, [m]);
    per.push(rows.map((r: any, i: number) => ({ ...r, modality_rank: i + 1 })));
  }
  return per.flat().sort((a, b) => a.modality_rank - b.modality_rank || a.distance - b.distance).slice(0, limit);
}

export function resultJson(r: any) {
  return {
    segment_id: r.id,
    ...(r.modality_rank ? { modality_rank: r.modality_rank } : {}),
    ...(r.rrf !== undefined ? { match: { keyword_rank: r.kw_rank ?? null, vector_rank: r.vec_rank ?? null } } : {}),
    score: Number((1 - r.distance).toFixed(6)),
    modality: r.modality,
    content: r.modality === "text" ? r.content : { type: r.modality, media_url: `/v1/files/${r.file_id}/content?version_id=${r.file_version_id}`, location: r.location },
    source: { file_id: r.file_id, version_id: r.file_version_id, version_no: r.version_no, filename: r.filename, path: r.path, media_type: r.media_type, location: r.location, metadata: r.metadata },
  };
}

export const SearchReq = z.object({
  query: z.object({ text: z.string().min(1).max(20000).optional(), asset_id: z.string().uuid().optional() }).strict()
    .refine((q) => q.text || q.asset_id, "query.text or query.asset_id is required"),
  limit: z.number().int().min(1).max(50).default(10),
  filter: Filter.optional(),
  modalities: z.array(z.enum(MODALITIES)).min(1).max(4).optional(),
  balance: z.boolean().default(false),
  mode: z.enum(["hybrid", "vector"]).default("hybrid"),
}).strict();

