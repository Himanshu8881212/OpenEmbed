// Retrieval quality (real model, labelled set), exact vs approximate search, embeddings compatibility contract.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { after, before, describe, test } from "node:test";
import OpenAI from "openai";
import { api, BASE, corpusFiles, dot, ingest, newStore, newWorkspace, norm, owner, ROOT, search, startWorker, stopAllWorkers } from "./helpers.mjs";

let W, store, key, prof;
before(async () => {
  startWorker({ KB_WORKER_CONCURRENCY: "3" });
  W = await newWorkspace("alice");
  store = await newStore(W, "corpus");
  const j = await ingest(W, store.id, corpusFiles());
  assert.equal(j.state, "completed", JSON.stringify(j.items));
  key = (await W.ok("POST", "/v1/api-keys", { name: "app", scopes: ["search", "embeddings"], stores: [store.id] })).secret;
  prof = (await W.ok("GET", "/v1/embedding-profiles")).data[0];
});
after(async () => { await stopAllWorkers(); await owner.end(); });

describe("retrieval quality (real EmbeddingGemma 2, labelled set)", () => {
  async function evaluate(storeId, mode) {
    const ev = JSON.parse(readFileSync(`${ROOT}tests/fixtures/eval.json`, "utf8"));
    let hits = 0, rr = 0;
    const misses = [];
    for (const q of ev.queries) {
      const r = await W.ok("POST", `/v1/stores/${storeId}/search`, { query: { text: q.query }, limit: 5, mode });
      const paths = r.results.map((x) => x.source.path);
      const rank = paths.indexOf(q.expected_path);
      if (rank >= 0) { hits++; rr += 1 / (rank + 1); } else misses.push(`${q.query} -> ${paths.slice(0, 3)}`);
      for (const x of r.results) assert.ok(x.source.file_id && x.source.version_id && x.source.location && x.segment_id);
    }
    return { hit5: hits / ev.queries.length, mrr: rr / ev.queries.length, n: ev.queries.length, misses, threshold: ev.threshold };
  }
  test("hit@5 meets the predeclared threshold in both modes; hybrid is at least as good as vector", async () => {
    const v = await evaluate(store.id, "vector"), h = await evaluate(store.id, "hybrid");
    console.log(`retrieval eval [${store.profile_id}]: vector hit@5=${v.hit5.toFixed(3)} MRR=${v.mrr.toFixed(3)} | hybrid hit@5=${h.hit5.toFixed(3)} MRR=${h.mrr.toFixed(3)} n=${h.n} misses=${JSON.stringify(h.misses)}`);
    assert.ok(v.hit5 >= v.threshold && h.hit5 >= h.threshold, JSON.stringify({ v, h }));
    assert.ok(h.mrr >= v.mrr - 0.01, "hybrid must not be worse than vector");
  });
  test("default profile (p4: structure-aware + transcripts/OCR/sharper video) is at least as good as p1; image vectors are reused, not recomputed", async () => {
    assert.equal(store.profile_id, "eg2-914f7f8-fp32-p4", "provider default for new stores");
    const rj = await W.ok("POST", `/v1/stores/${store.id}/reindex-jobs`, { profile_id: "eg2-914f7f8-fp32-p1" });
    for (let i = 0; i < 600 && (await W.ok("GET", `/v1/jobs/${rj.job_id}`)).state !== "completed"; i++) await new Promise((r) => setTimeout(r, 500));
    const reused = (await owner.query(`SELECT count(*)::int n FROM segments a JOIN segments b ON a.file_version_id = b.file_version_id AND a.ordinal = b.ordinal
      WHERE a.profile_id = 'eg2-914f7f8-fp32-p4' AND b.profile_id = 'eg2-914f7f8-fp32-p1' AND a.modality = 'image' AND a.embedding = b.embedding AND a.workspace_id = $1`, [W.ws])).rows[0].n;
    assert.ok(reused >= 3, `identical image vectors copied across profiles (${reused})`);
    await W.ok("POST", `/v1/stores/${store.id}/index-promotions`, { index_revision: rj.index_revision });
    const p1 = await evaluate(store.id, "hybrid");
    const back = (await W.ok("GET", `/v1/stores/${store.id}/stats`)).index_revisions.find((r) => r.profile_id === "eg2-914f7f8-fp32-p4");
    await W.ok("POST", `/v1/stores/${store.id}/index-promotions`, { index_revision: back.id });
    const p3 = await evaluate(store.id, "hybrid");
    console.log(`profile eval (hybrid): p1 hit@5=${p1.hit5.toFixed(3)} MRR=${p1.mrr.toFixed(3)} | p4 (default) hit@5=${p3.hit5.toFixed(3)} MRR=${p3.mrr.toFixed(3)}`);
    assert.ok(p3.mrr >= p1.mrr - 0.01, "structure-aware chunking must not be worse");
  });
  test("all advertised formats were indexed with typed locations", async () => {
    const files = (await W.ok("GET", `/v1/stores/${store.id}/files?limit=200`)).data;
    const byType = Object.fromEntries(files.map((f) => [f.version.media_type, f]));
    for (const t of ["text/plain", "text/markdown", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/pdf", "image/png", "image/jpeg", "audio/mpeg", "video/mp4"]) assert.ok(byType[t]?.segment_count > 0, t);
    const segs = await W.ok("GET", `/v1/files/${byType["audio/mpeg"].id}/segments`);
    assert.ok(segs.data[0].location.end_seconds > 0);
    const word = await W.ok("GET", `/v1/files/${byType["application/vnd.openxmlformats-officedocument.wordprocessingml.document"].id}/segments`);
    assert.ok(word.data.every((s) => s.location.section && s.location.end > s.location.start), "docx segments carry section + offsets");
    const pdf = files.find((f) => f.path === "media/scanned-diagram.pdf");
    assert.equal((await W.ok("GET", `/v1/files/${pdf.id}/segments`)).data[0].modality, "image");
  });
  test("cursor pagination walks every file exactly once; timestamps are UTC ISO; sizes in bytes", async () => {
    const seen = [];
    let cursor = null, pages = 0;
    do {
      const r = await W.ok("GET", `/v1/stores/${store.id}/files?limit=5${cursor ? `&cursor=${cursor}` : ""}`);
      assert.ok(r.data.length <= 5);
      for (const f of r.data) { seen.push(f.id); assert.match(f.created_at, /Z$/); assert.equal(typeof f.version.size, "number"); }
      cursor = r.next_cursor; pages++;
    } while (cursor && pages < 20);
    assert.equal(seen.length, 21);
    assert.equal(new Set(seen).size, 21);
    assert.equal((await W("GET", `/v1/stores/${store.id}/files?cursor=not-a-cursor`)).status, 400);
    // regression: rows created within the same millisecond must not be skipped (cursor keeps microseconds)
    const ids = seen.slice(0, 3);
    await owner.query("UPDATE files SET created_at = '2026-01-01 00:00:00+00'::timestamptz + (x.n * interval '1 microsecond') FROM unnest($1::uuid[]) WITH ORDINALITY AS x(id, n) WHERE files.id = x.id", [ids]);
    const one = [];
    for (let c = null, i = 0; i < 40; i++) {
      const r = await W.ok("GET", `/v1/stores/${store.id}/files?limit=1${c ? `&cursor=${c}` : ""}`);
      one.push(...r.data.map((f) => f.id)); c = r.next_cursor; if (!c) break;
    }
    assert.equal(new Set(one).size, 21, "page size 1 still returns every file");
  });
  test("original content is retrievable byte-for-byte", async () => {
    const f = (await W.ok("GET", `/v1/stores/${store.id}/files?limit=200`)).data.find((x) => x.path === "manuals/hydraulic-pump.pdf");
    const r = await fetch(`${BASE}/v1/files/${f.id}/content`, { headers: { authorization: `Bearer ${W.tok}`, "x-workspace-id": W.ws } });
    assert.equal(r.headers.get("content-type"), "application/pdf");
    assert.deepEqual(Buffer.from(await r.arrayBuffer()), readFileSync(`${ROOT}tests/fixtures/corpus/manuals/hydraulic-pump.pdf`));
  });
  test("media query (image asset) retrieves the matching image", async () => {
    const a = await api(W.tok, "POST", "/v1/query-assets", undefined, { ws: W.ws, raw: readFileSync(`${ROOT}tests/fixtures/red.png`), headers: { "content-type": "image/png" } });
    const r = await W.ok("POST", `/v1/stores/${store.id}/search`, { query: { asset_id: a.body.id }, limit: 3 });
    assert.equal(r.results[0].source.path, "media/red-square.png");
    await owner.query("UPDATE query_assets SET expires_at = now() - interval '1 second' WHERE id = $1", [a.body.id]);
    assert.equal((await W("POST", `/v1/stores/${store.id}/search`, { query: { asset_id: a.body.id } })).status, 410);
  });
});

describe("chunking quality on a long structured manual (passage level)", () => {
  test("structure-aware p3 beats or matches p1 at answer@1 and meets the predeclared threshold", async () => {
    const qa = JSON.parse(readFileSync(`${ROOT}tests/fixtures/structured/qa.json`, "utf8"));
    const s = await newStore(W, "manual-chunking");
    await ingest(W, s.id, [{ path: "turbine-service-manual.md", data: readFileSync(`${ROOT}tests/fixtures/structured/turbine-service-manual.md`) }]);
    const score = async () => {
      let ok = 0;
      for (const x of qa.queries) {
        const r = await W.ok("POST", `/v1/stores/${s.id}/search`, { query: { text: x.q }, limit: 1 });
        if (r.results[0]?.content?.includes(x.fact)) ok++;
      }
      return ok / qa.queries.length;
    };
    const p3 = await score();
    const segs = (await W.ok("GET", `/v1/files/${(await W.ok("GET", `/v1/stores/${s.id}/files`)).data[0].id}/segments`)).data;
    assert.ok(segs.every((x) => x.location.section), "every p3 passage records its section");
    assert.ok(!segs.some((x) => x.content.includes("## 2. Gearbox") && x.content.includes("## 3. Main bearing")), "passages never cross sections");
    const torque = segs.find((x) => x.content.includes("Housing cover"));
    assert.match(torque.content, /Fastener \| Torque/, "table passages carry the header row");
    const rj = await W.ok("POST", `/v1/stores/${s.id}/reindex-jobs`, { profile_id: "eg2-914f7f8-fp32-p1" });
    for (let i = 0; i < 600 && (await W.ok("GET", `/v1/jobs/${rj.job_id}`)).state !== "completed"; i++) await new Promise((r) => setTimeout(r, 500));
    await W.ok("POST", `/v1/stores/${s.id}/index-promotions`, { index_revision: rj.index_revision });
    const p1 = await score();
    console.log(`chunking eval (answer@1, n=${qa.queries.length}): p1=${p1.toFixed(2)} p3=${p3.toFixed(2)}`);
    assert.ok(p3 >= qa.threshold, `p3 answer@1 ${p3}`);
    assert.ok(p3 >= p1, `p3 ${p3} must not be worse than p1 ${p1}`);
  });
});

describe("exact vs approximate search", () => {
  let big;
  before(async () => {
    big = await newStore(W, "many");
    const topics = ["valve", "pump", "bearing", "filter", "sensor", "motor", "belt", "seal"];
    const files = Array.from({ length: 320 }, (_, i) => ({ path: `n/${String(i).padStart(3, "0")}.txt`, data: Buffer.from(`Note ${i}: the ${topics[i % 8]} on line ${i % 17} was inspected; reading ${i * 7 % 101} units, action code ${i % 5}.`) }));
    const j = await ingest(W, big.id, files);
    assert.equal(j.state, "completed");
    const list = (await W.ok("GET", `/v1/stores/${big.id}/files?limit=200`)).data;
    for (const f of list.slice(0, 4)) await W.ok("PATCH", `/v1/files/${f.id}`, { metadata: { department: "service" } });
  });
  const ids = (r) => r.results.map((x) => x.segment_id);
  test("unfiltered top-10 matches exact scan", async () => {
    for (const q of ["pump inspection reading", "sensor on line 3", "action code 4 bearing"]) {
      const a = await W.ok("POST", `/v1/stores/${big.id}/search`, { query: { text: q }, limit: 10 });
      const e = await W.ok("POST", `/v1/stores/${big.id}/search?exact=true`, { query: { text: q }, limit: 10 });
      const overlap = ids(a).filter((x) => e.results.some((y) => y.segment_id === x)).length;
      assert.ok(overlap >= 9, `${q}: recall@10 ${overlap}/10`);
    }
  });
  test("selective filter (4 of 320 files) still fills results and equals exact", async () => {
    const body = { query: { text: "inspection reading" }, limit: 10, filter: { metadata: { department: "service" } } };
    const a = await W.ok("POST", `/v1/stores/${big.id}/search`, body);
    const e = await W.ok("POST", `/v1/stores/${big.id}/search?exact=true`, body);
    assert.equal(a.results.length, 4);
    assert.deepEqual(new Set(ids(a)), new Set(ids(e)));
    assert.ok(a.results.every((r) => r.source.metadata.department === "service"));
  });
  test("path and media-type filters", async () => {
    const r = await W.ok("POST", `/v1/stores/${store.id}/search`, { query: { text: "maintenance" }, limit: 20, filter: { path_prefix: "policies/" } });
    assert.ok(r.results.length > 0 && r.results.every((x) => x.source.path.startsWith("policies/")));
    const m = await W.ok("POST", `/v1/stores/${store.id}/search`, { query: { text: "picture" }, limit: 20, filter: { media_types: ["image/png", "image/jpeg"] } });
    assert.ok(m.results.every((x) => x.source.media_type.startsWith("image/")));
  });
});

describe("/v1/models and /v1/embeddings (OpenAI-compatible subset)", () => {
  const E = (body, k = key) => api(k, "POST", "/v1/embeddings", body);
  test("models list envelope with purpose-specific immutable aliases", async () => {
    const r = await api(key, "GET", "/v1/models");
    assert.equal(r.body.object, "list");
    const ids = r.body.data.map((m) => m.id);
    assert.ok(ids.includes(store.query_model));
    assert.ok(r.body.data.every((m) => m.object === "model" && ["query", "document"].includes(m.purpose)));
  });
  test("ordered results, unit-norm finite 768-d vectors, measured token usage", async () => {
    const inputs = ["pressure sensor replacement", "cafeteria lunch hours", "fire assembly point"];
    const r = await E({ model: store.query_model, input: inputs });
    assert.equal(r.status, 200);
    assert.equal(r.body.object, "list");
    assert.equal(r.body.model, store.query_model);
    assert.deepEqual(r.body.data.map((d) => d.index), [0, 1, 2]);
    for (const d of r.body.data) {
      assert.equal(d.object, "embedding");
      assert.equal(d.embedding.length, 768);
      assert.ok(d.embedding.every(Number.isFinite));
      assert.ok(Math.abs(norm(d.embedding) - 1) < 1e-4);
    }
    for (const [i, t] of inputs.entries()) {
      const single = (await E({ model: store.query_model, input: t })).body.data[0].embedding;
      assert.ok(dot(single, r.body.data[i].embedding) > 0.9999, `order/index ${i}`);
    }
    assert.ok(r.body.usage.prompt_tokens > inputs.length);
    assert.equal(r.body.usage.total_tokens, r.body.usage.prompt_tokens);
  });
  test("base64 encoding decodes to the same float32 vector", async () => {
    const f = (await E({ model: store.query_model, input: "hello", encoding_format: "float" })).body.data[0].embedding;
    const b = (await E({ model: store.query_model, input: "hello", encoding_format: "base64" })).body.data[0].embedding;
    const buf = Buffer.from(b, "base64");
    const v = Array.from(new Float32Array(buf.buffer, buf.byteOffset, buf.length / 4));
    assert.equal(v.length, 768);
    assert.ok(v.every((x, i) => Math.abs(x - f[i]) < 1e-6));
  });
  test("query and document aliases apply different instructions", async () => {
    const doc = store.query_model.replace(/-query$/, "-document");
    const q = (await E({ model: store.query_model, input: "turbine" })).body.data[0].embedding;
    const d = (await E({ model: doc, input: "turbine" })).body.data[0].embedding;
    assert.ok(dot(q, d) < 0.999);
  });
  test("explicit OpenAI-style errors for unsupported inputs and parameters", async () => {
    const cases = [
      [{ model: store.query_model, input: [1, 2, 3] }, 400, "unsupported_input", "input"],
      [{ model: store.query_model, input: [[1, 2]] }, 400, "unsupported_input", "input"],
      [{ model: store.query_model, input: "x", dimensions: 256 }, 400, "unsupported_dimensions", "dimensions"],
      [{ model: store.query_model, input: "x", foo: 1 }, 400, "unsupported_parameter", "foo"],
      [{ model: "text-embedding-3-small", input: "x" }, 404, "model_not_found", "model"],
      [{ model: store.query_model, input: [] }, 400, "invalid_request", "input"],
      [{ model: store.query_model, input: "x", encoding_format: "int8" }, 400, "invalid_request", "encoding_format"],
      [{ model: store.query_model, input: [{ type: "image" }] }, 400, "invalid_request", "input"],
      [{ model: store.query_model, input: "word ".repeat(9000) }, 413, "input_too_large", "input.0"],
    ];
    for (const [body, status, code, param] of cases) {
      const r = await E(body);
      assert.equal(r.status, status, JSON.stringify(body).slice(0, 80));
      assert.deepEqual(Object.keys(r.body.error).sort(), ["code", "message", "param", "type"]);
      assert.equal(r.body.error.code, code);
      assert.equal(r.body.error.param, param);
      assert.match(r.headers.get("x-request-id"), /^req_/);
    }
    assert.equal((await E({ model: store.query_model, input: "x", dimensions: 768 })).status, 200);
    assert.equal((await api(null, "POST", "/v1/embeddings", { model: store.query_model, input: "x" })).body.error.type, "authentication_error");
  });
  test("official openai JS SDK (pinned 7.32.0) with default settings", async () => {
    const c = new OpenAI({ baseURL: `${BASE}/v1`, apiKey: key });
    const r = await c.embeddings.create({ model: store.query_model, input: ["pressure sensor", "lunch"] });
    assert.equal(r.data.length, 2);
    assert.equal(r.data[0].embedding.length, 768);
    assert.ok(Math.abs(norm(r.data[0].embedding) - 1) < 1e-4);
    const models = await c.models.list();
    assert.ok(models.data.some((m) => m.id === store.query_model));
    await assert.rejects(c.embeddings.create({ model: "nope", input: "x" }), (e) => e.status === 404 && e.code === "model_not_found");
  });
  test("official openai Python SDK (pinned 3.29.0)", () => {
    const outp = execFileSync(`${ROOT}py/.venv/bin/python`, ["-c", `
import os, math
from openai import OpenAI
c = OpenAI(base_url=os.environ["B"] + "/v1", api_key=os.environ["K"])
r = c.embeddings.create(model=os.environ["M"], input=["pressure sensor", "lunch"])
v = r.data[0].embedding
print(len(r.data), len(v), round(math.sqrt(sum(x*x for x in v)), 4), r.usage.prompt_tokens > 0)
`], { env: { ...process.env, B: BASE, K: key, M: store.query_model } }).toString().trim();
    assert.equal(outp, "2 768 1.0 True");
  });
});

describe("multimodal extension and query embeddings", () => {
  test("ordered text+image parts produce one vector; store query-embedding matches /v1/embeddings query alias", async () => {
    const a = await api(key, "POST", "/v1/query-assets", undefined, { raw: readFileSync(`${ROOT}tests/fixtures/red.png`), headers: { "content-type": "image/png" } });
    assert.equal(a.status, 201);
    const r = await api(key, "POST", "/v1/multimodal-embeddings", { profile_id: prof.id, purpose: "query", inputs: [{ parts: [{ type: "text", text: "find this" }, { type: "image", asset_id: a.body.id }] }, { parts: [{ type: "image", asset_id: a.body.id }] }] });
    assert.equal(r.status, 200);
    assert.equal(r.body.data.length, 2);
    assert.ok(r.body.data.every((d) => d.embedding.length === 768 && d.tokens > 200));
    assert.equal((await api(key, "POST", "/v1/multimodal-embeddings", { profile_id: prof.id, purpose: "query", inputs: [{ parts: [{ type: "audio", asset_id: a.body.id }] }] })).status, 400);
    assert.equal((await api(key, "POST", "/v1/query-assets", undefined, { raw: Buffer.from("x"), headers: { "content-type": "application/pdf" } })).status, 415);
    const qe = await api(key, "POST", `/v1/stores/${store.id}/query-embeddings`, { query: { text: "pressure sensor" } });
    const oe = await api(key, "POST", "/v1/embeddings", { model: qe.body.model, input: "pressure sensor" });
    assert.ok(dot(qe.body.embedding, oe.body.data[0].embedding) > 0.9999);
    assert.equal((await api(key, "DELETE", `/v1/query-assets/${a.body.id}`)).status, 204);
  });
});
