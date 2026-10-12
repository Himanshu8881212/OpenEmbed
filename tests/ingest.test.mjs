// Uploads, jobs and worker reliability against real services and the real model.
import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { execFileSync } from "node:child_process";
import { HeadObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { api, ROOT, workerLogs, ingest, newStore, newWorkspace, owner, search, sha, sleep, startWorker, stopAllWorkers, stopWorker, upload, waitJob } from "./helpers.mjs";

const s3 = new S3Client({ endpoint: process.env.KB_S3_ENDPOINT, region: process.env.KB_S3_REGION, forcePathStyle: true, credentials: { accessKeyId: process.env.KB_S3_ACCESS_KEY, secretAccessKey: process.env.KB_S3_SECRET_KEY } });
const exists = (Key) => s3.send(new HeadObjectCommand({ Bucket: process.env.KB_S3_BUCKET, Key })).then(() => true, () => false);
/** Text that prepares into many passages (slow enough to interrupt; ~16 passages per inference batch). */
const bigText = (n, tag = "") => Buffer.from(Array.from({ length: n }, (_, i) => `Section ${i} ${tag}. The maintenance log entry ${i} records inspection of valve V${i % 97} and pump P${i % 13}, noting seal wear and lubricant level.`).join("\n\n"));
const counts = async (versionId) => (await owner.query("SELECT count(*)::int n, count(DISTINCT ordinal)::int d FROM segments WHERE file_version_id = $1", [versionId])).rows[0];
const usageRows = async (ws) => (await owner.query("SELECT kind, quantity, idem_key FROM usage_events WHERE workspace_id = $1 AND kind LIKE 'index_%'", [ws])).rows;

let W, worker;
before(async () => { worker = startWorker(); W = await newWorkspace("alice"); });
after(async () => { await stopAllWorkers(); await owner.end(); });

describe("upload validation", () => {
  let s;
  before(async () => { s = await newStore(W); });
  test("unsafe paths are rejected (never interpreted as server paths)", async () => {
    for (const path of ["../etc/passwd", "/etc/passwd", "a/../../b.txt", "a\\b.txt", "C:/x.txt", "a//b.txt", "./a.txt", "a\u0000.txt"]) {
      const r = await W("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path, size: 3, sha256: sha("abc") }] });
      assert.equal(r.status, 400, path);
    }
  });
  test("unsupported format → 415; file and count limits → 413; duplicate paths → 400", async () => {
    assert.equal((await W("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path: "x.exe", size: 3, sha256: sha("abc") }] })).status, 415);
    assert.equal((await W("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path: "x.txt", size: 2 ** 40, sha256: sha("abc") }] })).status, 413);
    const many = Array.from({ length: 1001 }, (_, i) => ({ path: `f${i}.txt`, size: 1, sha256: sha("a") }));
    assert.equal((await W("POST", "/v1/upload-sessions", { store_id: s.id, files: many })).status, 413);
    assert.equal((await W("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path: "a.txt", size: 1, sha256: sha("a") }, { path: "a.txt", size: 1, sha256: sha("a") }] })).status, 400);
    assert.equal((await W("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path: "a.txt", size: 0, sha256: sha("") }] })).status, 400);
    assert.equal((await W("POST", "/v1/upload-sessions", { store_id: s.id, server_path: "/data", files: [] })).status, 400);
  });
  test("wrong part size, part checksum mismatch, incomplete commit, abandon", async () => {
    const { session } = await upload(W, s.id, [{ path: "p.txt", data: Buffer.from("hello world text") }], { commit: false, skipParts: ["p.txt:1"] });
    const f = session.files[0];
    const url = `/v1/upload-sessions/${session.id}/files/${f.id}/parts/1`;
    assert.equal((await W("PUT", url, undefined, { raw: Buffer.from("short") })).status, 400);
    const bad = await W("PUT", url, undefined, { raw: Buffer.from("hello world text"), headers: { "x-part-sha256": sha("other") } });
    assert.equal(bad.status, 400);
    assert.equal(bad.body.error.code, "CHECKSUM_MISMATCH");
    assert.equal((await W("PUT", `/v1/upload-sessions/${session.id}/files/${f.id}/parts/2`, undefined, { raw: Buffer.from("x") })).status, 400);
    const inc = await W("POST", `/v1/upload-sessions/${session.id}/commit`, {});
    assert.equal(inc.status, 409);
    assert.equal(inc.body.error.code, "UPLOAD_INCOMPLETE");
    assert.equal((await W("DELETE", `/v1/upload-sessions/${session.id}`)).status, 204);
    assert.equal((await W("PUT", url, undefined, { raw: Buffer.from("hello world text") })).status, 409);
  });
});

describe("resumable transfer", () => {
  test("interrupted multi-part upload resumes from the server's received-part list; one verified version", async () => {
    const s = await newStore(W);
    const data = Buffer.concat([bigText(10, "resume"), Buffer.alloc(9 * 1024 * 1024 - bigText(10, "resume").length, 0x20)]); // 9 MiB → 2 parts
    const { session } = await upload(W, s.id, [{ path: "big.txt", data }], { commit: false, skipParts: ["big.txt:2"] });
    const st = await W.ok("GET", `/v1/upload-sessions/${session.id}`);
    assert.deepEqual(st.files[0].parts_received, [1]);
    assert.equal(st.files[0].parts, 2);
    // resend part 1 (duplicate) and the missing part 2
    for (const n of [1, 2]) {
      const part = data.subarray((n - 1) * st.part_bytes, n * st.part_bytes);
      assert.equal((await W("PUT", `/v1/upload-sessions/${session.id}/files/${st.files[0].id}/parts/${n}`, undefined, { raw: part, headers: { "x-part-sha256": sha(part) } })).status, 200);
    }
    const c1 = await W("POST", `/v1/upload-sessions/${session.id}/commit`, {}, { headers: { "idempotency-key": "k1" } });
    assert.equal(c1.status, 202);
    const c2 = await W("POST", `/v1/upload-sessions/${session.id}/commit`, {}, { headers: { "idempotency-key": "k1" } });
    assert.equal(c2.body.job_id, c1.body.job_id, "replayed commit returns the same job");
    const c3 = await W("POST", `/v1/upload-sessions/${session.id}/commit`, { store_id: (await newStore(W)).id });
    assert.equal(c3.status, 409);
    const j = await waitJob(W, c1.body.job_id);
    assert.equal(j.state, "completed");
    const files = (await W.ok("GET", `/v1/stores/${s.id}/files`)).data;
    assert.equal(files.length, 1);
    assert.equal(files[0].version.version_no, 1);
  });
});

describe("integrity and partial failure", () => {
  test("whole-file checksum mismatch fails the item; nothing is published", async () => {
    const s = await newStore(W);
    const { commit } = await upload(W, s.id, [{ path: "liar.txt", data: Buffer.from("actual bytes"), manifestSha: sha("claimed bytes") }], { partSha: false });
    const j = await waitJob(W, commit.body.job_id);
    assert.equal(j.state, "failed");
    const items = (await W.ok("GET", `/v1/jobs/${j.id}/items`)).data;
    assert.equal(items[0].error.code, "CHECKSUM_MISMATCH");
    assert.equal(items[0].retryable, false);
    assert.equal((await W.ok("GET", `/v1/stores/${s.id}/files`)).data.length, 0);
  });
  test("one unreadable file → completed_with_errors; good file searchable; not retryable", async () => {
    const s = await newStore(W);
    const j = await ingest(W, s.id, [{ path: "good.txt", data: Buffer.from("Hydrogen fuel cells convert hydrogen and oxygen into electricity.") }, { path: "broken.png", data: Buffer.from("this is not a png") }]);
    assert.equal(j.state, "completed_with_errors");
    const failed = (await W.ok("GET", `/v1/jobs/${j.id}/items?state=failed`)).data;
    assert.equal(failed.length, 1);
    assert.equal(failed[0].path, "broken.png");
    assert.equal(failed[0].error.code, "UNREADABLE");
    const r = await search(W, s.id, "fuel cell electricity");
    assert.equal(r.results[0].source.path, "good.txt");
    assert.equal((await W("POST", `/v1/jobs/${j.id}/retry`, {})).status, 409);
  });
});

describe("worker reliability", () => {
  test("inference outage → retryable failure; retry as new job publishes once, without duplicate vectors or charges", async () => {
    await stopWorker(worker);
    const broken = startWorker({ KB_INFERENCE_IMPORT_URL: "http://127.0.0.1:9", KB_MAX_ATTEMPTS: "2" });
    const s = await newStore(W);
    const { commit } = await upload(W, s.id, [{ path: "outage.txt", data: Buffer.from("Wind turbines need yaw bearing inspection every six months.") }]);
    const j = await waitJob(W, commit.body.job_id, 120_000);
    assert.equal(j.state, "failed");
    const item = (await W.ok("GET", `/v1/jobs/${j.id}/items`)).data[0];
    assert.equal(item.error.code, "SERVICE_UNAVAILABLE");
    assert.equal(item.retryable, true);
    assert.equal(item.attempts, 2);
    await stopWorker(broken);
    worker = startWorker();
    const rj = await W("POST", `/v1/jobs/${j.id}/retry`, {}, { headers: { "idempotency-key": `r-${j.id}` } });
    assert.equal(rj.status, 202);
    const again = await W("POST", `/v1/jobs/${j.id}/retry`, {}, { headers: { "idempotency-key": `r-${j.id}` } });
    assert.equal(again.body.job_id, rj.body.job_id);
    assert.equal((await waitJob(W, rj.body.job_id)).state, "completed");
    const f = (await W.ok("GET", `/v1/stores/${s.id}/files`)).data[0];
    const c = await counts(f.version.id);
    assert.equal(c.n, c.d);
    const u = (await usageRows(W.ws)).filter((r) => r.idem_key.includes(f.version.id));
    assert.equal(u.length, 1, "one index charge for the version");
  });

  test("worker killed mid-item: lease expires, another worker finishes; no duplicate segments or charges", async () => {
    const s = await newStore(W);
    const { commit } = await upload(W, s.id, [{ path: "long-log.txt", data: bigText(400, "crash") }]);
    // wait until the item is running and inference has started
    for (let i = 0; i < 240; i++) {
      const it = (await W.ok("GET", `/v1/jobs/${commit.body.job_id}/items`)).data[0];
      if (it.state === "running") break;
      await sleep(250);
    }
    await sleep(2500);
    await stopWorker(worker, "SIGKILL");
    const stuck = await W.ok("GET", `/v1/jobs/${commit.body.job_id}`);
    assert.equal(stuck.state, "running");
    worker = startWorker();
    const j = await waitJob(W, commit.body.job_id, 300_000);
    assert.equal(j.state, "completed");
    const item = (await W.ok("GET", `/v1/jobs/${j.id}/items`)).data[0];
    assert.ok(item.attempts >= 2, `attempts ${item.attempts}`);
    const c = await counts(item.file_version_id);
    assert.equal(c.n, c.d, "each ordinal exactly once");
    assert.ok(c.n > 20);
    const u = (await usageRows(W.ws)).filter((r) => r.idem_key.includes(item.file_version_id));
    assert.equal(u.length, 1);
  });

  test("a worker whose registration is removed (pruned by a peer) re-registers and keeps processing", async () => {
    const before = (await owner.query("SELECT count(*)::int n FROM procrastinate_workers")).rows[0].n;
    assert.ok(before >= 1);
    await owner.query("DELETE FROM procrastinate_workers"); // what a misconfigured peer's prune would do
    const s = await newStore(W);
    const j = await ingest(W, s.id, [{ path: "after-prune.txt", data: Buffer.from("Worker recovery check: cooling tower fans are balanced yearly.") }]);
    assert.equal(j.state, "completed");
    for (let i = 0; i < 20 && !(await owner.query("SELECT count(*)::int n FROM procrastinate_workers")).rows[0].n; i++) await sleep(500);
    assert.ok((await owner.query("SELECT count(*)::int n FROM procrastinate_workers")).rows[0].n >= 1, "worker re-registered");
  });

  test("duplicate delivery of a finished task is a no-op", async () => {
    const s = await newStore(W);
    const j = await ingest(W, s.id, [{ path: "dup.txt", data: Buffer.from("Solar inverters must be cleaned of dust quarterly.") }]);
    const item = (await W.ok("GET", `/v1/jobs/${j.id}/items`)).data[0];
    const before = await counts(item.file_version_id);
    const ub = (await usageRows(W.ws)).length;
    await owner.query(`SELECT procrastinate_defer_jobs_v1(ARRAY[ROW('ingest','ingest_item',0,NULL,NULL,$1::jsonb,NULL)::procrastinate_job_to_defer_v1])`, [JSON.stringify({ job_id: j.id, item_id: item.id })]);
    await sleep(3000);
    assert.deepEqual(await counts(item.file_version_id), before);
    assert.equal((await usageRows(W.ws)).length, ub);
    assert.equal((await W.ok("GET", `/v1/jobs/${j.id}`)).state, "completed");
  });

  test("cancellation stops at a safe boundary; published items remain; nothing partial is published", async () => {
    const s = await newStore(W);
    await ingest(W, s.id, [{ path: "keep.txt", data: Buffer.from("Elevator ropes are inspected monthly by a certified technician.") }]);
    const { commit } = await upload(W, s.id, [{ path: "cancel-me.txt", data: bigText(400, "cancel") }]);
    for (let i = 0; i < 240; i++) {
      if ((await W.ok("GET", `/v1/jobs/${commit.body.job_id}/items`)).data[0].state === "running") break;
      await sleep(250);
    }
    const c = await W("POST", `/v1/jobs/${commit.body.job_id}/cancel`, {});
    assert.equal(c.status, 202);
    assert.ok(["cancel_requested", "cancelled"].includes(c.body.state));
    const j = await waitJob(W, commit.body.job_id);
    assert.equal(j.state, "cancelled");
    const paths = (await W.ok("GET", `/v1/stores/${s.id}/files`)).data.map((f) => f.path);
    assert.deepEqual(paths, ["keep.txt"]);
    assert.equal((await W("POST", `/v1/jobs/${j.id}/cancel`, {})).status, 409);
  });
});

describe("atomic replacement", () => {
  test("search shows the old complete version or the new complete version, never a mixture", async () => {
    const s = await newStore(W);
    const v1 = Buffer.from(Array.from({ length: 30 }, (_, i) => `Old procedure step ${i}: lubricate gearbox G${i} with grease type A.`).join("\n\n"));
    await ingest(W, s.id, [{ path: "gearbox.txt", data: v1 }]);
    const file = (await W.ok("GET", `/v1/stores/${s.id}/files`)).data[0];
    const v1id = file.version.id;
    const v2 = bigText(300, "gearbox new procedure grease type B");
    const { commit } = await upload(W, null, [{ path: "gearbox.txt", data: v2, replaces: file.id }]);
    assert.equal(commit.status, 200, "commit without store returns the session");
    const rev = await W("POST", `/v1/files/${file.id}/revisions`, { upload_session_id: commit.body.id });
    assert.equal(rev.status, 202);
    const seen = [];
    let state;
    do {
      const r = await search(W, s.id, "gearbox lubrication procedure grease", { limit: 50 });
      const versions = new Set(r.results.map((x) => x.source.version_id));
      assert.ok(versions.size <= 1, `mixed versions in one response: ${[...versions]}`);
      seen.push([...versions][0]);
      state = (await W.ok("GET", `/v1/jobs/${rev.body.job_id}`)).state;
    } while (!["completed", "failed", "completed_with_errors", "cancelled"].includes(state));
    assert.equal(state, "completed");
    const after = await search(W, s.id, "gearbox lubrication procedure grease", { limit: 50 });
    const v2id = after.results[0].source.version_id;
    assert.notEqual(v2id, v1id);
    assert.ok(seen.includes(v1id), "old version stayed searchable during processing");
    const firstNew = seen.indexOf(v2id);
    if (firstNew >= 0) assert.ok(seen.slice(firstNew).every((v) => v === v2id), "never back to old after publish");
    const total = (await owner.query("SELECT count(*)::int n FROM segments WHERE file_version_id = $1", [v2id])).rows[0].n;
    const f2 = await W.ok("GET", `/v1/files/${file.id}`);
    assert.equal(f2.segment_count, total);
    assert.equal(f2.current_version.version_no, 2);
  });
});

describe("deduplication, deletion and cleanup", () => {
  test("same bytes twice: one blob, storage counted once, vectors copied without new charges", async () => {
    const s = await newStore(W);
    const data = Buffer.from("Compressed air lines are drained of condensate every morning before the shift.");
    await ingest(W, s.id, [{ path: "a/air.txt", data }]);
    const u1 = (await usageRows(W.ws)).length;
    await ingest(W, s.id, [{ path: "b/air.txt", data }]);
    const blobs = (await owner.query("SELECT count(*)::int n FROM blobs WHERE workspace_id = $1 AND sha256 = $2", [W.ws, sha(data)])).rows[0].n;
    assert.equal(blobs, 1);
    assert.equal((await usageRows(W.ws)).length, u1, "identical bytes+filename reuse vectors (no charge)");
    const r = await search(W, s.id, "condensate drain compressed air");
    assert.deepEqual(new Set(r.results.slice(0, 2).map((x) => x.source.path)), new Set(["a/air.txt", "b/air.txt"]));
  });

  test("membership removal vs source deletion; immediate access removal; physical cleanup", async () => {
    const s1 = await newStore(W), s2 = await newStore(W);
    const data = Buffer.from("Boiler feedwater must be tested for hardness and pH every week.");
    const { commit, session } = await upload(W, s1.id, [{ path: "boiler.txt", data }]);
    await waitJob(W, commit.body.job_id);
    const ing = await W("POST", `/v1/stores/${s2.id}/ingestions`, { upload_session_id: session.id });
    assert.equal(ing.status, 202);
    await waitJob(W, ing.body.job_id);
    const f1 = (await W.ok("GET", `/v1/stores/${s1.id}/files`)).data[0], f2 = (await W.ok("GET", `/v1/stores/${s2.id}/files`)).data[0];
    assert.equal(f1.id, f2.id, "committed material reused as the same source");
    // remove from s1 only
    assert.equal((await W("DELETE", `/v1/stores/${s1.id}/files/${f1.id}`)).status, 204);
    assert.equal((await search(W, s1.id, "boiler feedwater")).results.length, 0);
    assert.equal((await search(W, s2.id, "boiler feedwater")).results[0].source.file_id, f1.id);
    // delete the source everywhere
    const prev = await W.ok("POST", `/v1/files/${f1.id}/deletion-previews`, {});
    assert.deepEqual(prev.stores.map((x) => x.id), [s2.id]);
    assert.equal((await W("DELETE", `/v1/files/${f1.id}`)).status, 400, "scope is required");
    const del = await W("DELETE", `/v1/files/${f1.id}?scope=workspace`);
    assert.equal(del.status, 202);
    assert.equal((await search(W, s2.id, "boiler feedwater")).results.length, 0, "inaccessible before cleanup finishes");
    assert.equal((await W("GET", `/v1/files/${f1.id}/content`)).status, 404);
    await waitJob(W, del.body.job_id);
    const key = `ws/${W.ws}/blobs/${sha(data)}`;
    assert.equal((await owner.query("SELECT count(*)::int n FROM file_versions WHERE file_id = $1", [f1.id])).rows[0].n, 0);
    assert.equal(await exists(key), false, "original removed from object storage (retention 0 in dev)");
  });

  test("store deletion: preview, immediate 404, unshared sources deleted, shared bytes kept", async () => {
    const keep = await newStore(W), doomed = await newStore(W);
    const shared = Buffer.from("Shared safety note: wear hearing protection in the press hall.");
    const { session, commit } = await upload(W, keep.id, [{ path: "shared.txt", data: shared }]);
    await waitJob(W, commit.body.job_id);
    await waitJob(W, (await W.ok("POST", `/v1/stores/${doomed.id}/ingestions`, { upload_session_id: session.id })).job_id);
    await ingest(W, doomed.id, [{ path: "only-here.txt", data: Buffer.from("Only in the doomed store: paint booth filters are changed weekly.") }]);
    const p = await W.ok("POST", `/v1/stores/${doomed.id}/deletion-previews`, {});
    assert.equal(p.memberships, 2);
    assert.equal(p.sources_shared_with_other_stores, 1);
    assert.equal((await W("DELETE", `/v1/stores/${doomed.id}`)).status, 400);
    const d = await W("DELETE", `/v1/stores/${doomed.id}?sources=unshared`);
    assert.equal(d.status, 202);
    assert.equal((await W("POST", `/v1/stores/${doomed.id}/search`, { query: { text: "paint booth" } })).status, 404);
    const j = await waitJob(W, d.body.job_id);
    assert.deepEqual(j.result, { memberships_removed: 2, sources_deleted: 1 });
    assert.equal((await search(W, keep.id, "hearing protection press hall")).results[0].source.path, "shared.txt");
    assert.equal(await exists(`ws/${W.ws}/blobs/${sha(shared)}`), true);
  });
});

describe("cleanup never races in-flight imports", () => {
  test("GC keeps a verified blob while an import item is pending, collects it once nothing needs it", async () => {
    const G = await newWorkspace("alice");
    const s = await newStore(G);
    const digest = sha(Buffer.from(`race-${Date.now()}`));
    const { rows: [ids] } = await owner.query(`WITH b AS (INSERT INTO blobs (workspace_id, sha256, size, object_key, created_at) VALUES ($1, $2, 10, 'ws/x/blobs/' || $2, now() - interval '1 day')),
        se AS (INSERT INTO upload_sessions (workspace_id, store_id, state, expires_at) VALUES ($1, $3, 'committed', now() + interval '1 day') RETURNING id),
        uf AS (INSERT INTO upload_files (workspace_id, session_id, path, size, sha256, media_type, part_size, object_key, verified_at) SELECT $1, id, 'r.txt', 10, $2, 'text/plain', 10, 'k', now() FROM se RETURNING id),
        j AS (INSERT INTO jobs (workspace_id, store_id, kind) VALUES ($1, $3, 'ingest') RETURNING id)
      INSERT INTO job_items (workspace_id, job_id, path, upload_file_id, state) SELECT $1, j.id, 'r.txt', uf.id, 'running' FROM j, uf RETURNING id`, [G.ws, digest, s.id]);
    const gc = () => execFileSync(`${ROOT}py/.venv/bin/python`, ["-c", `from kbpy.worker import gc_workspace; gc_workspace("${G.ws}")`], { cwd: `${ROOT}py`, env: { ...process.env, KB_RETENTION_SECONDS: "0" }, stdio: "pipe" });
    const blobs = async () => (await owner.query("SELECT count(*)::int n FROM blobs WHERE workspace_id = $1 AND sha256 = $2", [G.ws, digest])).rows[0].n;
    gc();
    assert.equal(await blobs(), 1, "pending import protects its bytes");
    await owner.query("UPDATE job_items SET state = 'failed' WHERE id = $1", [ids.id]);
    gc();
    assert.equal(await blobs(), 0, "collected once nothing references it");
  });
});

describe("usage and quotas", () => {
  test("usage reconciles with metered events; hard caps return 429", async () => {
    const Q = await newWorkspace("alice");
    const s = await newStore(Q);
    await ingest(Q, s.id, [{ path: "u.txt", data: Buffer.from("Quota test document about laser cutter lens cleaning.") }]);
    await search(Q, s.id, "laser lens");
    const u = await Q.ok("GET", "/v1/usage");
    const ev = (await owner.query("SELECT kind, sum(quantity)::int q FROM usage_events WHERE workspace_id = $1 GROUP BY kind", [Q.ws])).rows;
    const by = Object.fromEntries(ev.map((r) => [r.kind, r.q]));
    assert.equal(u.indexing.text_tokens, by.index_text_tokens);
    assert.equal(u.queries.text_tokens, by.query_text_tokens);
    assert.ok(by.index_text_tokens > 0 && by.query_text_tokens > 0);
    const blobBytes = (await owner.query("SELECT sum(size)::int b FROM blobs WHERE workspace_id = $1", [Q.ws])).rows[0].b;
    assert.equal(u.storage.originals_bytes, blobBytes);
    await owner.query(`UPDATE workspaces SET plan = jsonb_set(jsonb_set(plan, '{limits,query_tokens_month}', '1'), '{limits,storage_bytes}', '10') WHERE id = $1`, [Q.ws]);
    const r = await Q("POST", `/v1/stores/${s.id}/search`, { query: { text: "laser" } });
    assert.equal(r.status, 429);
    assert.equal(r.body.error.code, "QUOTA_EXCEEDED");
    const up = await Q("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path: "more.txt", size: 100, sha256: sha("x") }] });
    assert.equal(up.status, 429);
    await owner.query(`UPDATE workspaces SET plan = jsonb_set(plan, '{limits,index_tokens_month}', '1') || '{"limits":{"storage_bytes":10737418240,"query_tokens_month":1000,"index_tokens_month":1}}' WHERE id = $1`, [Q.ws]);
    const j = await ingest(Q, s.id, [{ path: "over.txt", data: Buffer.from("This import exceeds the indexing allowance.") }]);
    const it = (await Q.ok("GET", `/v1/jobs/${j.id}/items`)).data[0];
    assert.equal(it.error.code, "QUOTA_EXCEEDED");
    assert.equal(it.retryable, true);
  });
  test("storage is metered in GiB-month from time-weighted samples", async () => {
    const G = await newWorkspace("alice");
    await owner.query("INSERT INTO storage_samples (workspace_id, at, bytes) VALUES ($1, date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC', 1073741824)", [G.ws]);
    const u = await G.ok("GET", "/v1/usage");
    const { rows: [f] } = await owner.query(`SELECT extract(epoch FROM now() - (date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')) /
      extract(epoch FROM (date_trunc('month', now() AT TIME ZONE 'UTC') + interval '1 month') - date_trunc('month', now() AT TIME ZONE 'UTC')) AS frac`);
    assert.ok(Math.abs(u.storage.gib_month_to_date - Number(f.frac)) < 0.001, `${u.storage.gib_month_to_date} vs ${f.frac}`);
  });
  test("per-workspace queue is bounded (429 when full)", async () => {
    const Qw = await newWorkspace("alice");
    const s = await newStore(Qw);
    const j = await ingest(Qw, s.id, [{ path: "seed.txt", data: Buffer.from("Seed document for the queue bound test.") }]);
    await owner.query("INSERT INTO job_items (workspace_id, job_id, path, state) SELECT $1, $2, 'filler', 'queued' FROM generate_series(1, 20000)", [Qw.ws, j.id]);
    try {
      const { commit } = await upload(Qw, s.id, [{ path: "more.txt", data: Buffer.from("One more document.") }]);
      assert.equal(commit.status, 429);
      assert.equal(commit.body.error.code, "QUOTA_EXCEEDED");
    } finally { await owner.query("DELETE FROM job_items WHERE job_id = $1 AND path = 'filler'", [j.id]); }
  });
  test("audit events record key, delete and member actions without content", async () => {
    const ev = (await W.ok("GET", "/v1/audit-events?limit=200")).data;
    const actions = new Set(ev.map((e) => e.action));
    for (const a of ["store.create", "upload.commit", "file.delete", "store.delete", "store.remove_file"]) assert.ok(actions.has(a), a);
    assert.ok(!JSON.stringify(ev).includes("Boiler feedwater"));
  });
});

describe("log hygiene", () => {
  test("worker and API logs never contain customer content", async () => {
    const logs = workerLogs();
    assert.ok(logs.length > 0, "workers logged at INFO");
    for (const canary of ["Boiler feedwater", "hearing protection", "Compressed air lines", "gearbox", "Elevator ropes"]) assert.ok(!logs.includes(canary), canary);
  });
});
