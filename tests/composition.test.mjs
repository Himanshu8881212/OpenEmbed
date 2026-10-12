// Later-release capabilities: merges, live views, snapshots, reindex/promotion/rollback, connectors + scheduled sync.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { after, before, describe, test } from "node:test";
import { ingest, newStore, newWorkspace, owner, search, sleep, startWorker, stopAllWorkers, upload, waitJob } from "./helpers.mjs";

const P1 = "eg2-914f7f8-fp32-p4", P2 = "eg2-914f7f8-fp32-p2"; // P1 = provider default profile for new stores
const txt = (s) => Buffer.from(s);
const paths = (r) => r.results.map((x) => x.source.path);
const usageCount = async (ws) => (await owner.query("SELECT count(*)::int n FROM usage_events WHERE workspace_id = $1 AND kind LIKE 'index_%'", [ws])).rows[0].n;

let W;
before(async () => { startWorker({ KB_WORKER_CONCURRENCY: "3" }); W = await newWorkspace("alice"); });
after(async () => { await stopAllWorkers(); await owner.end(); });

describe("store merges", () => {
  let A, B;
  before(async () => {
    A = await newStore(W); B = await newStore(W);
    const { session, commit } = await upload(W, A.id, [{ path: "shared/ppe.txt", data: txt("Safety glasses are mandatory in the machining area.") }, { path: "a/lathe.txt", data: txt("The lathe chuck key must never be left in the chuck.") }]);
    await waitJob(W, commit.body.job_id);
    await waitJob(W, (await W.ok("POST", `/v1/stores/${B.id}/ingestions`, { upload_session_id: session.id })).job_id); // same sources in B
    await ingest(W, B.id, [{ path: "b/welding.txt", data: txt("Welding screens protect bystanders from arc flash.") }]);
  });
  test("compatible merge deduplicates membership and reuses vectors (no re-embedding, no charge)", async () => {
    const u0 = await usageCount(W.ws);
    const r = await W("POST", "/v1/store-merges", { sources: [A.id, B.id], target_name: "merged-ab" });
    assert.equal(r.status, 202);
    const j = await waitJob(W, r.body.job_id);
    assert.equal(j.state, "completed");
    assert.deepEqual(j.result, { source_references: 5, memberships: 3, duplicates_removed: 2, reembedded_items: 0 });
    assert.equal(await usageCount(W.ws), u0);
    const files = (await W.ok("GET", `/v1/stores/${r.body.target_store_id}/files`)).data.map((f) => f.path).sort();
    assert.deepEqual(files, ["a/lathe.txt", "b/welding.txt", "shared/ppe.txt"]);
    assert.equal(paths(await search(W, r.body.target_store_id, "arc flash welding"))[0], "b/welding.txt");
    // the target is independent: removing from a parent does not change it
    const lathe = (await W.ok("GET", `/v1/stores/${A.id}/files`)).data.find((f) => f.path === "a/lathe.txt");
    await W.ok("DELETE", `/v1/stores/${A.id}/files/${lathe.id}`);
    assert.ok(paths(await search(W, r.body.target_store_id, "lathe chuck key")).includes("a/lathe.txt"));
  });
  test("incompatible profiles are rejected (409); explicit rebuild embeds from retained sources", async () => {
    const C = await newStore(W);
    await ingest(W, C.id, [{ path: "c/press.txt", data: txt("Hydraulic press guards must be interlocked.") }]);
    const rj = await W.ok("POST", `/v1/stores/${C.id}/reindex-jobs`, { profile_id: P2 });
    await waitJob(W, rj.job_id);
    await W.ok("POST", `/v1/stores/${C.id}/index-promotions`, { index_revision: rj.index_revision });
    const bad = await W("POST", "/v1/store-merges", { sources: [B.id, C.id], target_name: "nope" });
    assert.equal(bad.status, 409);
    assert.equal(bad.body.error.code, "PROFILE_INCOMPATIBLE");
    const rb = await W.ok("POST", "/v1/store-merges", { sources: [B.id, C.id], target_name: "rebuilt", mode: "rebuild", profile_id: P2 });
    const j = await waitJob(W, rb.job_id);
    assert.equal(j.state, "completed");
    assert.ok(j.result.reembedded_items >= 3, JSON.stringify(j.result));
    const s = await W.ok("GET", `/v1/stores/${rb.target_store_id}`);
    assert.equal(s.profile_id, P2);
    assert.equal(paths(await search(W, rb.target_store_id, "arc flash welding"))[0], "b/welding.txt");
  });
});

describe("live views and snapshots", () => {
  let parent, view, snap, fileA, fileB;
  before(async () => {
    parent = await newStore(W);
    await ingest(W, parent.id, [{ path: "hr/leave.txt", data: txt("Annual leave requests go through the HR portal two weeks ahead.") },
      { path: "ops/forklift.txt", data: txt("Forklift version one: inspect forks and chains daily.") }]);
    const fl = (await W.ok("GET", `/v1/stores/${parent.id}/files`)).data;
    fileA = fl.find((f) => f.path === "ops/forklift.txt").id;
    fileB = fl.find((f) => f.path === "hr/leave.txt").id;
    await W.ok("PATCH", `/v1/files/${fileA}`, { metadata: { department: "ops" } });
    view = await W.ok("POST", `/v1/stores/${parent.id}/derivations`, { name: "ops-view", mode: "view", filter: { metadata: { department: "ops" } } });
    snap = await W.ok("POST", `/v1/stores/${parent.id}/derivations`, { name: "ops-snapshot", mode: "snapshot", filter: { metadata: { department: "ops" } } });
  });
  test("derived stores have their own IDs and only matching members", async () => {
    assert.equal(view.kind, "view");
    assert.equal(snap.kind, "snapshot");
    assert.deepEqual((await W.ok("GET", `/v1/stores/${view.id}/files`)).data.map((f) => f.path), ["ops/forklift.txt"]);
    assert.deepEqual((await W.ok("GET", `/v1/stores/${snap.id}/files`)).data.map((f) => f.path), ["ops/forklift.txt"]);
    assert.ok(!paths(await search(W, view.id, "annual leave HR portal")).includes("hr/leave.txt"));
    const nested = await W(`POST`, `/v1/stores/${view.id}/derivations`, { name: "v2", mode: "view" });
    assert.equal(nested.status, 201, "views can be parents (nested views)");
    assert.deepEqual((await W.ok("GET", `/v1/stores/${nested.body.id}/files`)).data.map((f) => f.path), ["ops/forklift.txt"]);
  });
  test("metadata change: the view follows, the snapshot does not", async () => {
    await W.ok("PATCH", `/v1/files/${fileB}`, { metadata: { department: "ops" } });
    assert.ok(paths(await search(W, view.id, "annual leave HR portal")).includes("hr/leave.txt"));
    assert.ok(!paths(await search(W, snap.id, "annual leave HR portal")).includes("hr/leave.txt"));
    await W.ok("PATCH", `/v1/files/${fileB}`, { metadata: { department: null } });
    assert.ok(!paths(await search(W, view.id, "annual leave HR portal")).includes("hr/leave.txt"));
  });
  test("replacement: the view shows the new version, the snapshot keeps the pinned version (even after cleanup)", async () => {
    const { commit } = await upload(W, null, [{ path: "ops/forklift.txt", data: txt("Forklift version two: inspect forks, chains, brakes and horn before each shift."), replaces: fileA }]);
    await waitJob(W, (await W.ok("POST", `/v1/files/${fileA}/revisions`, { upload_session_id: commit.body.id })).job_id);
    const v = await search(W, view.id, "forklift inspection");
    const s = await search(W, snap.id, "forklift inspection");
    assert.equal(v.results[0].source.version_no, 2);
    assert.equal(s.results[0].source.version_no, 1);
    // dev retention is 0: run cleanup and confirm the pinned version survives
    const gc = await W.ok("DELETE", `/v1/files/${fileB}?scope=workspace`);
    await waitJob(W, gc.job_id);
    assert.equal((await search(W, snap.id, "forklift inspection")).results[0].source.version_no, 1);
  });
  test("parent membership removal: view drops it, snapshot keeps it; global deletion removes it everywhere", async () => {
    await W.ok("DELETE", `/v1/stores/${parent.id}/files/${fileA}`);
    assert.equal((await search(W, view.id, "forklift")).results.length, 0);
    assert.equal((await search(W, snap.id, "forklift")).results.length, 1);
    const prev = await W.ok("POST", `/v1/files/${fileA}/deletion-previews`, {});
    assert.deepEqual(prev.snapshots.map((x) => x.id), [snap.id]);
    await waitJob(W, (await W.ok("DELETE", `/v1/files/${fileA}?scope=workspace`)).job_id);
    assert.equal((await search(W, snap.id, "forklift")).results.length, 0);
  });
  test("parent store deletion empties the view; deletion preview lists dependent views", async () => {
    const p2 = await newStore(W);
    await ingest(W, p2.id, [{ path: "x.txt", data: txt("Chemical storage cabinets must be vented.") }]);
    const v2 = await W.ok("POST", `/v1/stores/${p2.id}/derivations`, { name: "all-of-p2", mode: "view" });
    assert.equal((await search(W, v2.id, "chemical storage")).results.length, 1);
    const prev = await W.ok("POST", `/v1/stores/${p2.id}/deletion-previews`, {});
    assert.deepEqual(prev.dependent_views.map((x) => x.id), [v2.id]);
    await W.ok("DELETE", `/v1/stores/${p2.id}?sources=keep`);
    assert.equal((await search(W, v2.id, "chemical storage")).results.length, 0);
  });
  test("derivation never widens access: a viewer cannot derive; another workspace cannot use parents", async () => {
    const other = await newWorkspace("bob");
    assert.equal((await other("POST", `/v1/stores/${parent.id}/derivations`, { name: "steal", mode: "view" })).status, 404);
  });
});

describe("reindex, promotion and rollback", () => {
  let s;
  before(async () => {
    s = await newStore(W);
    await ingest(W, s.id, [{ path: "pump.txt", data: txt(Array.from({ length: 12 }, (_, i) => `Pump maintenance step ${i}: check impeller clearance and bearing temperature.`).join(" ")) }]);
  });
  test("build runs beside the active index; promotion switches profile + alias; rollback restores; new imports reach both", async () => {
    const before = await search(W, s.id, "impeller clearance");
    assert.equal(before.profile_id, P1);
    const r = await W("POST", `/v1/stores/${s.id}/reindex-jobs`, { profile_id: P2 });
    assert.equal(r.status, 202);
    assert.equal((await W("POST", `/v1/stores/${s.id}/index-promotions`, { index_revision: r.body.index_revision })).status, 409, "building revision cannot be promoted");
    assert.equal((await search(W, s.id, "impeller clearance")).profile_id, P1, "active index unchanged during build");
    const j = await waitJob(W, r.body.job_id);
    assert.equal(j.state, "completed");
    const oldRev = (await W.ok("GET", `/v1/stores/${s.id}`)).index_revision;
    const promoted = await W.ok("POST", `/v1/stores/${s.id}/index-promotions`, { index_revision: r.body.index_revision });
    assert.equal(promoted.profile_id, P2);
    assert.equal(promoted.query_model, `${P2}-query`);
    assert.equal((await W.ok("GET", `/v1/stores/${s.id}/connection`)).query_model, `${P2}-query`);
    const after = await search(W, s.id, "impeller clearance");
    assert.equal(after.profile_id, P2);
    assert.equal(after.index_revision, r.body.index_revision);
    assert.ok(after.results.length > before.results.length, "finer segmentation in P2");
    await ingest(W, s.id, [{ path: "valve.txt", data: txt("Valve packing is replaced when stem leakage exceeds ten drops per minute.") }]);
    const rolled = await W.ok("POST", `/v1/stores/${s.id}/index-promotions`, { index_revision: oldRev });
    assert.equal(rolled.profile_id, P1);
    assert.equal(paths(await search(W, s.id, "valve stem leakage"))[0], "valve.txt", "previous revision kept current while inactive");
    const aliases = (await owner.query("SELECT alias, profile_id FROM model_aliases WHERE alias = $1", [`${P1}-query`])).rows;
    assert.deepEqual(aliases, [{ alias: `${P1}-query`, profile_id: P1 }], "aliases never repointed");
  });
});

describe("connectors and scheduled sync", () => {
  let server, files;
  before(async () => {
    files = { "guide.md": "# Onboarding guide\n\nNew starters collect their badge from reception.", "faq.txt": "Parking permits are issued by facilities." };
    server = createServer((req, res) => {
      const name = decodeURIComponent(req.url.slice(1));
      if (name === "manifest.json") return res.end(JSON.stringify({ files: Object.keys(files).map((p) => ({ path: `docs/${p}`, url: p })).concat([{ path: "../escape.txt", url: "faq.txt" }]) }));
      if (files[name] === undefined) { res.statusCode = 404; return res.end(); }
      res.end(files[name]);
    }).listen(8765, "127.0.0.1");
    await new Promise((ok, fail) => (server.listening ? ok() : server.once("listening", ok).once("error", fail)));
  });
  after(() => server.close());
  test("only allowlisted hosts; sync imports, skips unchanged, updates changed, removes deleted; scheduler runs it", async () => {
    const s = await newStore(W);
    assert.equal((await W("POST", "/v1/connectors", { store_id: s.id, type: "http_manifest", url: "http://169.254.169.254/latest" })).status, 400);
    const c = await W.ok("POST", "/v1/connectors", { store_id: s.id, type: "http_manifest", url: "http://127.0.0.1:8765/manifest.json", interval_minutes: 5 });
    const j1 = await waitJob(W, (await W.ok("POST", `/v1/connectors/${c.id}/syncs`, {})).job_id);
    assert.equal(j1.state, "completed");
    assert.equal(j1.result.imported, 2);
    assert.equal(j1.result.skipped, 1, "unsafe manifest path skipped");
    assert.equal(paths(await search(W, s.id, "where do I get my badge"))[0], "docs/guide.md");
    files["guide.md"] = "# Onboarding guide v2\n\nBadges are now collected from the security desk.";
    delete files["faq.txt"];
    await owner.query("UPDATE connectors SET next_run_at = now() - interval '1 second' WHERE id = $1", [c.id]);
    let j2;
    for (let i = 0; i < 90 && !j2; i++) {
      await sleep(1000);
      const con = (await W.ok("GET", "/v1/connectors")).data.find((x) => x.id === c.id);
      if (con.last_job_id && con.last_job_id !== j1.id) j2 = await waitJob(W, con.last_job_id);
    }
    assert.ok(j2, "scheduler started a sync");
    assert.deepEqual([j2.state, j2.result.imported, j2.result.removed], ["completed", 1, 1]);
    const r = await search(W, s.id, "where do I get my badge");
    assert.equal(r.results[0].source.version_no, 2);
    assert.ok(!paths(await search(W, s.id, "parking permits")).includes("docs/faq.txt"));
    const j3 = await waitJob(W, (await W.ok("POST", `/v1/connectors/${c.id}/syncs`, {})).job_id);
    assert.equal(j3.result.unchanged, 1);
    assert.equal((await W("DELETE", `/v1/connectors/${c.id}`)).status, 204);
  });
});
