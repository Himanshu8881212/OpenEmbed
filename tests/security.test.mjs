// Identity, roles, keys, workspace isolation (API + RLS with the real non-owner roles and pooled connections).
import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { api, apiRole, client, ingest, newStore, newWorkspace, owner, search, startWorker, stopAllWorkers, token, upload, workerRole } from "./helpers.mjs";

let A, B, storeA, storeA2, fileA, keySearch;
before(async () => {
  startWorker();
  A = await newWorkspace("alice");
  B = await newWorkspace("bob");
  storeA = await newStore(A);
  storeA2 = await newStore(A);
  const job = await ingest(A, storeA.id, [{ path: "secret/plan.txt", data: Buffer.from("The confidential turbine redesign plan uses titanium blades.") }]);
  assert.equal(job.state, "completed");
  fileA = (await A.ok("GET", `/v1/stores/${storeA.id}/files`)).data[0].id;
  keySearch = (await A.ok("POST", "/v1/api-keys", { name: "search", scopes: ["search"], stores: [storeA.id] })).secret;
});
after(async () => { await stopAllWorkers(); await owner.end(); });

describe("authentication", () => {
  test("missing, malformed and forged credentials → 401 with request id", async () => {
    for (const auth of [null, "garbage", "eyJhbGciOiJSUzI1NiJ9.e30.sig", "kb_notakey"]) {
      const r = await api(auth, "GET", "/v1/stores");
      assert.equal(r.status, 401, String(auth));
      assert.equal(r.body.error.code, "AUTHENTICATION_REQUIRED");
      assert.match(r.body.error.request_id, /^req_/);
      assert.match(r.headers.get("x-request-id"), /^req_/);
    }
  });
  test("device flow session starts at the real IdP; unknown device code is rejected", async () => {
    const d = await api(null, "POST", "/v1/auth/device-sessions");
    assert.equal(d.status, 200);
    assert.match(d.body.user_code, /\w/);
    assert.match(d.body.verification_uri, /^http/);
    const pending = await api(null, "POST", "/v1/auth/token", { grant_type: "device_code", device_code: d.body.device_code });
    assert.equal(pending.status, 400);
    assert.equal(pending.body.error.code, "AUTHORIZATION_PENDING");
    const bad = await api(null, "POST", "/v1/auth/token", { grant_type: "device_code", device_code: "nope" });
    assert.ok([400, 401].includes(bad.status));
  });
  test("API keys cannot use human-only endpoints", async () => {
    assert.equal((await api(keySearch, "GET", "/v1/workspaces")).status, 403);
  });
});

describe("roles", () => {
  let C, viewer, editor;
  before(async () => {
    C = await newWorkspace("alice");
    await C.ok("POST", `/v1/workspaces/${C.ws}/members`, { email: "carol@example.com", role: "viewer" });
    await C.ok("POST", `/v1/workspaces/${C.ws}/members`, { email: "dave@example.com", role: "editor" });
    viewer = client(await token("carol"), C.ws);
    editor = client(await token("dave"), C.ws);
  });
  test("invitation activates on sign-in", async () => {
    const me = await api(viewer.tok, "GET", "/v1/me");
    assert.ok(me.body.workspaces.some((w) => w.id === C.ws && w.role === "viewer"));
  });
  test("viewer: read/search only", async () => {
    const s = await newStore(C);
    assert.equal((await viewer("GET", `/v1/stores/${s.id}`)).status, 200);
    assert.equal((await viewer("POST", "/v1/stores", { name: "nope" })).status, 403);
    assert.equal((await viewer("POST", "/v1/api-keys", { name: "k", scopes: ["search"] })).status, 403);
    assert.equal((await viewer("DELETE", `/v1/stores/${s.id}?sources=keep`)).status, 403);
    assert.equal((await viewer("POST", "/v1/upload-sessions", { store_id: s.id, files: [{ path: "a.txt", size: 1, sha256: "0".repeat(64) }] })).status, 403);
  });
  test("editor: material and keys, not members or audit", async () => {
    const s = await newStore(editor);
    assert.ok(s.id);
    assert.equal((await editor("POST", `/v1/workspaces/${C.ws}/members`, { email: "x@example.com", role: "viewer" })).status, 403);
    assert.equal((await editor("GET", "/v1/audit-events")).status, 403);
    assert.equal((await editor("POST", "/v1/api-keys", { name: "k", scopes: ["search"] })).status, 201);
  });
  test("the last active owner cannot be demoted or removed", async () => {
    const members = (await C.ok("GET", `/v1/workspaces/${C.ws}/members`)).data;
    const me = members.find((m) => m.email === "alice@example.com");
    assert.equal((await C("PATCH", `/v1/workspaces/${C.ws}/members/${me.id}`, { role: "viewer" })).status, 409);
    assert.equal((await C("DELETE", `/v1/workspaces/${C.ws}/members/${me.id}`)).status, 409);
  });
  test("removed member loses access immediately", async () => {
    const members = (await C.ok("GET", `/v1/workspaces/${C.ws}/members`)).data;
    const d = members.find((m) => m.email === "dave@example.com");
    await C.ok("DELETE", `/v1/workspaces/${C.ws}/members/${d.id}`);
    assert.equal((await editor("GET", "/v1/stores")).status, 404);
  });
});

describe("API keys", () => {
  test("search key: search allowed; uploads, source reads, deletion denied", async () => {
    const k = client(keySearch);
    assert.equal((await k("POST", `/v1/stores/${storeA.id}/search`, { query: { text: "turbine" } })).status, 200);
    assert.equal((await k("GET", `/v1/files/${fileA}`)).status, 403);
    assert.equal((await k("GET", `/v1/files/${fileA}/content`)).status, 403);
    assert.equal((await k("DELETE", `/v1/stores/${storeA.id}?sources=keep`)).status, 403);
    assert.equal((await k("DELETE", `/v1/files/${fileA}?scope=workspace`)).status, 403);
    assert.equal((await k("POST", "/v1/upload-sessions", { store_id: storeA.id, files: [{ path: "a.txt", size: 1, sha256: "0".repeat(64) }] })).status, 403);
    assert.equal((await k("POST", "/v1/api-keys", { name: "x", scopes: ["search"] })).status, 403);
  });
  test("store-restricted key cannot see other stores in the same workspace", async () => {
    const k = client(keySearch);
    assert.equal((await k("GET", `/v1/stores/${storeA2.id}`)).status, 404);
    const list = await k.ok("GET", "/v1/stores");
    assert.deepEqual(list.data.map((s) => s.id), [storeA.id]);
  });
  test("store-restricted key reads only versions its stores expose", async () => {
    const s = await newStore(A);
    await ingest(A, s.id, [{ path: "v.txt", data: Buffer.from("Version one of the compressor manual.") }]);
    const f = (await A.ok("GET", `/v1/stores/${s.id}/files`)).data[0];
    const v1 = f.version.id;
    const { commit } = await upload(A, null, [{ path: "v.txt", data: Buffer.from("Version two of the compressor manual."), replaces: f.id }]);
    const rev = await A.ok("POST", `/v1/files/${f.id}/revisions`, { upload_session_id: commit.body.id });
    for (let i = 0; i < 240 && (await A.ok("GET", `/v1/jobs/${rev.job_id}`)).state !== "completed"; i++) await new Promise((r) => setTimeout(r, 500));
    const k = client((await A.ok("POST", "/v1/api-keys", { name: "reader", scopes: ["source:read"], stores: [s.id] })).secret);
    assert.equal((await k("GET", `/v1/files/${f.id}/content`)).status, 200);
    assert.equal((await k("GET", `/v1/files/${f.id}/content?version_id=${v1}`)).status, 404);
    assert.equal((await A("GET", `/v1/files/${f.id}/content?version_id=${v1}`)).status, 200, "workspace users may read retained versions");
  });
  test("source:write keys must be store-restricted", async () => {
    assert.equal((await A("POST", "/v1/api-keys", { name: "w", scopes: ["source:write"] })).status, 400);
  });
  test("revocation is effective on the next request (delay 0)", async () => {
    const k = await A.ok("POST", "/v1/api-keys", { name: "temp", scopes: ["search"], stores: [storeA.id] });
    assert.equal((await api(k.secret, "POST", `/v1/stores/${storeA.id}/search`, { query: { text: "x" } })).status, 200);
    await A.ok("DELETE", `/v1/api-keys/${k.id}`);
    const r = await api(k.secret, "POST", `/v1/stores/${storeA.id}/search`, { query: { text: "x" } });
    assert.equal(r.status, 401);
    const listed = (await A.ok("GET", "/v1/api-keys")).data.find((x) => x.id === k.id);
    assert.ok(listed.revoked_at);
    assert.equal(listed.secret, undefined);
  });
  test("only the hash of a key is stored", async () => {
    const { rows } = await owner.query("SELECT token_hash, prefix FROM api_keys WHERE workspace_id = $1", [A.ws]);
    for (const r of rows) { assert.equal(r.token_hash.length, 32); assert.equal(r.prefix.length, 10); }
  });
});

describe("cross-workspace isolation via the API", () => {
  test("another workspace's ids are concealed as 404 (users and keys)", async () => {
    const bobKey = (await B.ok("POST", "/v1/api-keys", { name: "b", scopes: ["search", "source:read"] })).secret;
    const job = (await A.ok("GET", "/v1/jobs")).data[0].id;
    for (const c of [B, client(bobKey)]) {
      for (const [m, p, b] of [["GET", `/v1/stores/${storeA.id}`], ["POST", `/v1/stores/${storeA.id}/search`, { query: { text: "turbine" } }],
        ["GET", `/v1/files/${fileA}`], ["GET", `/v1/files/${fileA}/content`], ["GET", `/v1/files/${fileA}/segments`], ["GET", `/v1/jobs/${job}`],
        ["GET", `/v1/stores/${storeA.id}/connection`], ["DELETE", `/v1/stores/${storeA.id}/files/${fileA}`]]) {
        const r = await c(m, p, b);
        assert.equal(r.status, 404, `${m} ${p} -> ${r.status}`);
        assert.equal(r.body.error.code, "RESOURCE_NOT_FOUND");
      }
    }
  });
  test("selecting a workspace you are not a member of → 404", async () => {
    const r = await api(B.tok, "GET", "/v1/stores", undefined, { ws: A.ws });
    assert.equal(r.status, 404);
  });
  test("identical content in another workspace never appears in results", async () => {
    const sB = await newStore(B);
    await ingest(B, sB.id, [{ path: "secret/plan.txt", data: Buffer.from("The confidential turbine redesign plan uses titanium blades.") }]);
    const rB = await search(B, sB.id, "turbine redesign titanium");
    const rA = await search(A, storeA.id, "turbine redesign titanium");
    const idsA = new Set(rA.results.map((r) => r.source.file_id));
    assert.ok(rB.results.length && rB.results.every((r) => !idsA.has(r.source.file_id)));
  });
  test("cross-workspace query assets and upload sessions are invisible", async () => {
    const asset = await api(A.tok, "POST", "/v1/query-assets", undefined, { ws: A.ws, raw: Buffer.from(await (await import("node:fs/promises")).readFile(new URL("./fixtures/red.png", import.meta.url))), headers: { "content-type": "image/png" } });
    assert.equal(asset.status, 201);
    const prof = (await B.ok("GET", "/v1/embedding-profiles")).data[0].id;
    const r = await B("POST", "/v1/multimodal-embeddings", { profile_id: prof, purpose: "query", inputs: [{ parts: [{ type: "image", asset_id: asset.body.id }] }] });
    assert.equal(r.status, 404);
    assert.equal((await B("DELETE", `/v1/query-assets/${asset.body.id}`)).status, 404);
    const { session } = await upload(A, storeA.id, [{ path: "x.txt", data: Buffer.from("x content") }], { commit: false });
    assert.equal((await B("GET", `/v1/upload-sessions/${session.id}`)).status, 404);
    assert.equal((await B("POST", `/v1/upload-sessions/${session.id}/commit`, {})).status, 404);
  });
  test("object storage keys are workspace-prefixed and never exposed", async () => {
    const f = await A.ok("GET", `/v1/files/${fileA}`);
    assert.ok(!JSON.stringify(f).includes("ws/"));
    const { rows } = await owner.query("SELECT object_key FROM blobs WHERE workspace_id = $1", [A.ws]);
    assert.ok(rows.every((r) => r.object_key.startsWith(`ws/${A.ws}/`)));
  });
});

describe("row security with the real service roles", () => {
  test("kb_api / kb_worker see nothing without a workspace context", async () => {
    for (const pool of [apiRole(), workerRole()]) {
      const { rows } = await pool.query("SELECT count(*)::int n FROM stores");
      assert.equal(rows[0].n, 0);
      const { rows: seg } = await pool.query("SELECT count(*)::int n FROM segments");
      assert.equal(seg[0].n, 0);
      await pool.end();
    }
  });
  test("context is transaction-local: a pooled connection does not keep the previous tenant", async () => {
    const pool = apiRole(1);
    const c = await pool.connect();
    await c.query("BEGIN");
    await c.query("SELECT set_config('app.workspace_id', $1, true)", [A.ws]);
    const inTx = (await c.query("SELECT count(*)::int n FROM stores")).rows[0].n;
    await c.query("COMMIT");
    c.release();
    assert.ok(inTx >= 2);
    const reused = await pool.connect(); // same physical connection (max 1)
    assert.equal((await reused.query("SELECT count(*)::int n FROM stores")).rows[0].n, 0);
    assert.equal((await reused.query("SELECT kb_ws() w")).rows[0].w, null);
    reused.release();
    await pool.end();
  });
  test("tenant A context cannot read or write tenant B rows", async () => {
    const pool = workerRole(1);
    const c = await pool.connect();
    try {
      await c.query("BEGIN");
      await c.query("SELECT set_config('app.workspace_id', $1, true)", [A.ws]);
      const { rows } = await c.query("SELECT DISTINCT workspace_id::text w FROM stores");
      assert.deepEqual(rows.map((r) => r.w), [A.ws]);
      await assert.rejects(c.query("INSERT INTO stores (workspace_id, name) VALUES ($1, 'evil')", [B.ws]), /row-level security/);
      await c.query("ROLLBACK");
      await c.query("BEGIN");
      await c.query("SELECT set_config('app.workspace_id', $1, true)", [A.ws]);
      const upd = await c.query("UPDATE files SET metadata = '{\"x\":1}' WHERE workspace_id = $1", [B.ws]);
      assert.equal(upd.rowCount, 0);
      await c.query("ROLLBACK");
    } finally { c.release(); await pool.end(); }
  });
  test("roles cannot bypass: no owner rights, no profile edits, narrow definer functions", async () => {
    const a = apiRole(), w = workerRole();
    await assert.rejects(a.query("UPDATE embedding_profiles SET dims = 768"), /permission denied/);
    await assert.rejects(a.query("ALTER TABLE stores DISABLE ROW LEVEL SECURITY"), /must be owner/);
    await assert.rejects(w.query("SELECT * FROM kb_lookup_api_key('\\x00')"), /permission denied/);
    await assert.rejects(a.query("SELECT kb_maintenance_workspaces()"), /permission denied/);
    await assert.rejects(a.query("SELECT kb_job_workspace(gen_random_uuid())"), /permission denied/);
    await assert.rejects(w.query("SELECT * FROM identities"), /permission denied/);
    const { rows } = await a.query("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user");
    assert.deepEqual(rows[0], { rolbypassrls: false, rolsuper: false });
    await a.end(); await w.end();
  });
  test("profiles and aliases are immutable even for the owner", async () => {
    await assert.rejects(owner.query("UPDATE embedding_profiles SET query_prompt = 'x'"), /immutable/);
    await assert.rejects(owner.query("UPDATE model_aliases SET profile_id = profile_id"), /immutable/);
  });
});
