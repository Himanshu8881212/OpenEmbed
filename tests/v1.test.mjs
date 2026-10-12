// V1 hardening and data-freedom features: export, split, custom profiles, nested views, rate limits, metrics, headers.
import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { api, BASE, client, dot, ingest, newStore, newWorkspace, norm, owner, search, startWorker, stopAllWorkers } from "./helpers.mjs";

const txt = (s) => Buffer.from(s);
let W, base;
before(async () => {
  startWorker();
  W = await newWorkspace("alice");
  base = await newStore(W);
  await ingest(W, base.id, [
    { path: "svc/pump.txt", data: txt("Service: pump impellers are inspected every 500 hours for cavitation damage.") },
    { path: "svc/valve.txt", data: txt("Service: valve packing is replaced when stem leakage is visible.") },
    { path: "hr/leave.txt", data: txt("Human resources: annual leave requests go through the portal.") },
    { path: "ops/shift.txt", data: txt("Operations: shift handover notes are written in the logbook.") },
  ]);
  const files = (await W.ok("GET", `/v1/stores/${base.id}/files`)).data;
  const tag = { "svc/pump.txt": "service", "svc/valve.txt": "service", "hr/leave.txt": "hr", "ops/shift.txt": "Ops & Planning" };
  for (const f of files) await W.ok("PATCH", `/v1/files/${f.id}`, { metadata: { department: tag[f.path] } });
});
after(async () => { await stopAllWorkers(); await owner.end(); });

describe("embedding export", () => {
  test("NDJSON with source, location, text and unit-norm 768-d embeddings for every indexed segment", async () => {
    const r = await fetch(`${BASE}/v1/stores/${base.id}/export`, { headers: { authorization: `Bearer ${W.tok}`, "x-workspace-id": W.ws } });
    assert.equal(r.status, 200);
    assert.match(r.headers.get("content-type"), /application\/x-ndjson/);
    assert.equal(r.headers.get("x-kb-profile"), base.profile_id);
    const lines = (await r.text()).trim().split("\n").map((l) => JSON.parse(l));
    const store = await W.ok("GET", `/v1/stores/${base.id}`);
    assert.equal(lines.length, store.segment_count);
    for (const l of lines) {
      assert.equal(l.embedding.length, 768);
      assert.ok(Math.abs(norm(l.embedding) - 1) < 1e-4);
      assert.ok(l.source.file_id && l.source.version_id && l.source.location && l.source.sha256);
      assert.equal(typeof l.content, "string");
    }
    // exported vectors are the ones search uses: the query vector ranks the matching segment first
    const q = await W.ok("POST", `/v1/stores/${base.id}/query-embeddings`, { query: { text: "impeller cavitation inspection" } });
    const best = lines.reduce((a, l) => (dot(l.embedding, q.embedding) > dot(a.embedding, q.embedding) ? l : a));
    assert.equal(best.source.path, "svc/pump.txt");
    const noVec = await (await fetch(`${BASE}/v1/stores/${base.id}/export?include=content`, { headers: { authorization: `Bearer ${W.tok}`, "x-workspace-id": W.ws } })).text();
    assert.ok(!noVec.includes('"embedding"'));
  });
  test("export needs source:read; other workspaces see 404", async () => {
    const searchOnly = (await W.ok("POST", "/v1/api-keys", { name: "s", scopes: ["search"], stores: [base.id] })).secret;
    assert.equal((await api(searchOnly, "GET", `/v1/stores/${base.id}/export`)).status, 403);
    const reader = (await W.ok("POST", "/v1/api-keys", { name: "r", scopes: ["source:read"], stores: [base.id] })).secret;
    assert.equal((await fetch(`${BASE}/v1/stores/${base.id}/export`, { headers: { authorization: `Bearer ${reader}` } })).status, 200);
    const B = await newWorkspace("bob");
    assert.equal((await B("GET", `/v1/stores/${base.id}/export`)).status, 404);
  });
});

describe("split by field", () => {
  test("one live view per value; membership correct and live; existing names skipped", async () => {
    const r = await W("POST", `/v1/stores/${base.id}/splits`, { field: "department", prefix: "dept" });
    assert.equal(r.status, 201);
    const byValue = Object.fromEntries(r.body.created.map((c) => [c.value, c.store]));
    assert.deepEqual(Object.keys(byValue).sort(), ["Ops & Planning", "hr", "service"]);
    assert.equal(byValue["Ops & Planning"].name, "dept-ops-planning");
    assert.equal(byValue.service.kind, "view");
    const svc = (await W.ok("GET", `/v1/stores/${byValue.service.id}/files`)).data.map((f) => f.path).sort();
    assert.deepEqual(svc, ["svc/pump.txt", "svc/valve.txt"]);
    // live: retagging moves a file between split stores
    const leave = (await W.ok("GET", `/v1/stores/${base.id}/files`)).data.find((f) => f.path === "hr/leave.txt");
    await W.ok("PATCH", `/v1/files/${leave.id}`, { metadata: { department: "service" } });
    assert.ok((await search(W, byValue.service.id, "annual leave portal")).results.some((x) => x.source.path === "hr/leave.txt"));
    assert.equal((await search(W, byValue.hr.id, "annual leave portal")).results.length, 0);
    await W.ok("PATCH", `/v1/files/${leave.id}`, { metadata: { department: "hr" } });
    const again = await W.ok("POST", `/v1/stores/${base.id}/splits`, { field: "department", prefix: "dept" });
    assert.equal(again.created.length, 0);
    assert.equal(again.skipped.length, 3);
    assert.equal((await W("POST", `/v1/stores/${base.id}/splits`, { field: "nonexistent" })).status, 400);
    const snap = await W.ok("POST", `/v1/stores/${base.id}/splits`, { field: "department", mode: "snapshot", prefix: "frozen" });
    assert.ok(snap.created.every((c) => c.store.kind === "snapshot"));
  });
});

describe("custom chunking profiles", () => {
  test("customers cannot create chunking profiles unless the provider enables the plan feature", async () => {
    const r = await W("POST", "/v1/embedding-profiles", { name: "x", text: { max_chars: 800, overlap_chars: 100 } });
    assert.equal(r.status, 403);
    assert.equal(r.body.error.code, "FEATURE_DISABLED");
    await owner.query(`UPDATE workspaces SET plan = jsonb_set(plan, '{features}', '{"custom_profiles": true}') WHERE id = $1`, [W.ws]);
  });
  test("workspace profile: bounded, private to the workspace, used for new stores and reindex; aliases work", async () => {
    assert.equal((await W("POST", "/v1/embedding-profiles", { name: "bad", text: { max_chars: 100000, overlap_chars: 0 } })).status, 400);
    assert.equal((await W("POST", "/v1/embedding-profiles", { name: "bad", text: { max_chars: 400, overlap_chars: 300 } })).status, 400);
    const p = await W.ok("POST", "/v1/embedding-profiles", { name: "tiny passages", text: { max_chars: 200, overlap_chars: 20 }, audio: { segment_seconds: 10 } });
    assert.match(p.id, /^ws-/);
    const listed = (await W.ok("GET", "/v1/embedding-profiles")).data.find((x) => x.id === p.id);
    assert.equal(listed.scope, "workspace");
    assert.equal(listed.preparation.text.max_chars, 200);
    const B = await newWorkspace("bob");
    assert.ok(!(await B.ok("GET", "/v1/embedding-profiles")).data.some((x) => x.id === p.id), "invisible to other workspaces");
    assert.equal((await B("POST", "/v1/stores", { name: "steal", profile_id: p.id })).status, 400);
    const generated = await B.ok("POST", "/v1/stores", {});
    assert.match(generated.name, /^[a-z]+-[a-z]+-\d{2}$/, "omitted name is generated");
    const long = Array.from({ length: 12 }, (_, i) => `Clause ${i}: the contractor maintains the chiller plant and reports refrigerant levels monthly.`).join(" ");
    const s = await W.ok("POST", "/v1/stores", { name: `custom-${Date.now()}`, profile_id: p.id });
    await ingest(W, s.id, [{ path: "contract.txt", data: txt(long) }]);
    const seg = (await W.ok("GET", `/v1/stores/${s.id}`)).segment_count;
    assert.ok(seg >= 5, `200-char passages produce many segments (got ${seg})`);
    assert.equal((await search(W, s.id, "refrigerant reporting")).profile_id, p.id);
    const models = await W.ok("GET", "/v1/models");
    assert.ok(models.data.some((m) => m.id === `${p.id}-query`));
    const key = (await W.ok("POST", "/v1/api-keys", { name: "e", scopes: ["embeddings"] })).secret;
    assert.equal((await api(key, "POST", "/v1/embeddings", { model: `${p.id}-query`, input: "x" })).status, 200);
    const bkey = (await B.ok("POST", "/v1/api-keys", { name: "e", scopes: ["embeddings"] })).secret;
    assert.equal((await api(bkey, "POST", "/v1/embeddings", { model: `${p.id}-query`, input: "x" })).status, 404);
    // reindex an existing store onto the custom profile, then promote
    const rj = await W.ok("POST", `/v1/stores/${base.id}/reindex-jobs`, { profile_id: p.id });
    for (let i = 0; i < 240 && (await W.ok("GET", `/v1/jobs/${rj.job_id}`)).state !== "completed"; i++) await new Promise((r) => setTimeout(r, 500));
    const promoted = await W.ok("POST", `/v1/stores/${base.id}/index-promotions`, { index_revision: rj.index_revision });
    assert.equal(promoted.profile_id, p.id);
    await assert.rejects(owner.query("UPDATE embedding_profiles SET name = 'x' WHERE id = $1", [p.id]), /immutable/);
  });
});

describe("nested live views", () => {
  test("a view over a view resolves recursively and follows changes; depth is limited", async () => {
    const svc = (await W.ok("GET", "/v1/stores?name=dept-service")).data[0];
    const pumps = await W.ok("POST", `/v1/stores/${svc.id}/derivations`, { name: "svc-pumps", mode: "view", filter: { path_prefix: "svc/pump" } });
    assert.deepEqual((await W.ok("GET", `/v1/stores/${pumps.id}/files`)).data.map((f) => f.path), ["svc/pump.txt"]);
    const d3 = await W.ok("POST", `/v1/stores/${pumps.id}/derivations`, { name: "svc-pumps-2", mode: "view" });
    assert.equal((await W("POST", `/v1/stores/${d3.id}/derivations`, { name: "too-deep", mode: "view" })).status, 400);
    const frozen = await W.ok("POST", `/v1/stores/${pumps.id}/derivations`, { name: "svc-pumps-frozen", mode: "snapshot" });
    assert.equal(frozen.kind, "snapshot");
    const pump = (await W.ok("GET", `/v1/stores/${base.id}/files`)).data.find((f) => f.path === "svc/pump.txt");
    await W.ok("PATCH", `/v1/files/${pump.id}`, { metadata: { department: "retired" } });
    assert.equal((await W.ok("GET", `/v1/stores/${pumps.id}/files`)).data.length, 0, "nested view follows the root");
    assert.equal((await W.ok("GET", `/v1/stores/${frozen.id}/files`)).data.length, 1, "snapshot of a view stays fixed");
  });
});

describe("production hardening", () => {
  test("per-principal rate limit returns 429 with Retry-After and limit headers", async () => {
    const R = await newWorkspace("alice");
    await owner.query(`UPDATE workspaces SET plan = jsonb_set(plan, '{limits,requests_per_minute}', '5') WHERE id = $1`, [R.ws]);
    const codes = [];
    let last;
    for (let i = 0; i < 7; i++) { last = await R("GET", "/v1/stores"); codes.push(last.status); }
    assert.ok(codes.slice(0, 5).every((c) => c === 200), codes.join());
    assert.equal(codes[6], 429);
    assert.equal(last.body.error.code, "RATE_LIMITED");
    assert.ok(Number(last.headers.get("retry-after")) > 0);
    assert.equal(last.headers.get("x-ratelimit-limit"), "5");
    assert.equal((await W("GET", "/v1/stores")).status, 200, "other principals/workspaces unaffected");
  });
  test("/metrics requires its token and exposes HTTP and queue metrics", async () => {
    assert.equal((await fetch(`${BASE}/metrics`)).status, 404);
    const r = await fetch(`${BASE}/metrics`, { headers: { authorization: `Bearer ${process.env.KB_METRICS_TOKEN}` } });
    assert.equal(r.status, 200);
    const t = await r.text();
    for (const m of ["kb_http_requests_total{", "kb_http_request_duration_seconds_bucket{", "kb_segments ", "kb_jobs{", "kb_workers_alive "]) assert.ok(t.includes(m), m);
    assert.ok(!/[0-9a-f]{8}-[0-9a-f]{4}-/.test(t), "no identifiers in metric labels");
  });
  test("security headers on API and pages", async () => {
    for (const p of ["/v1/openapi.json", "/"]) {
      const r = await fetch(BASE + p);
      assert.match(r.headers.get("content-security-policy") ?? "", /frame-ancestors 'none'/);
      assert.equal(r.headers.get("x-content-type-options"), "nosniff");
      assert.equal(r.headers.get("x-frame-options"), "DENY");
      assert.equal(r.headers.get("referrer-policy"), "no-referrer");
    }
  });
});
