// Backup/restore drill (runs last: it rolls the whole database back to the backup point).
// Proves: sources, permissions, memberships and active index references come back; material deleted and
// keys revoked after the backup stay deleted/revoked after restore (deletion ledger replay).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { after, before, test } from "node:test";
import { api, ingest, newStore, newWorkspace, owner, ROOT, search, startWorker, stopAllWorkers, waitJob } from "./helpers.mjs";

const sh = (cmd, args) => execFileSync(cmd, args, { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
let dir;
before(() => startWorker());
after(async () => { await stopAllWorkers(); await owner.end(); if (dir) rmSync(`${ROOT}${dir}`, { recursive: true, force: true }); });

test("restore brings back data but never deleted material or revoked keys", async () => {
  const W = await newWorkspace("alice");
  const s = await newStore(W);
  await ingest(W, s.id, [{ path: "keep.txt", data: Buffer.from("Kept document: the boiler room key is held by facilities.") },
    { path: "gone.txt", data: Buffer.from("Deleted document: the old alarm code was 4242.") }]);
  const files = (await W.ok("GET", `/v1/stores/${s.id}/files`)).data;
  const gone = files.find((f) => f.path === "gone.txt");
  const key = await W.ok("POST", "/v1/api-keys", { name: "restore-test", scopes: ["search"], stores: [s.id] });
  const revBefore = (await W.ok("GET", `/v1/stores/${s.id}`)).index_revision;

  dir = sh("bash", ["scripts/backup.sh"]).split("\n").pop();

  await waitJob(W, (await W.ok("DELETE", `/v1/files/${gone.id}?scope=workspace`)).job_id);
  await W.ok("DELETE", `/v1/api-keys/${key.id}`);
  assert.equal((await api(key.secret, "POST", `/v1/stores/${s.id}/search`, { query: { text: "x" } })).status, 401);

  await stopAllWorkers();
  // restore the database + objects only (to show what a naive restore would expose), then replay the ledger
  execFileSync("bash", ["-c", `docker compose exec -T postgres pg_restore --clean --if-exists --single-transaction -U kb_owner -d kb < "${dir}/db.dump" && node scripts/objects.mjs import "${dir}/objects"`], { cwd: ROOT, stdio: "ignore" });
  assert.equal((await W("GET", `/v1/files/${gone.id}`)).status, 200, "naive restore resurrects the deleted source");
  assert.equal((await api(key.secret, "POST", `/v1/stores/${s.id}/search`, { query: { text: "x" } })).status, 200, "…and the revoked key");
  sh("node", ["scripts/reapply-deletions.mjs", sh("cat", [`${dir}/TIMESTAMP`])]);

  assert.equal((await W("GET", `/v1/files/${gone.id}`)).status, 404);
  assert.equal((await W("GET", `/v1/files/${gone.id}/content`)).status, 404);
  assert.equal((await api(key.secret, "POST", `/v1/stores/${s.id}/search`, { query: { text: "x" } })).status, 401);
  const r = await search(W, s.id, "alarm code boiler room key");
  assert.deepEqual(r.results.map((x) => x.source.path), ["keep.txt"]);
  assert.equal(r.index_revision, revBefore, "active index reference restored");
  const kept = files.find((f) => f.path === "keep.txt");
  const content = await fetch(`${process.env.KB_TEST_BASE_URL ?? "http://localhost:3000"}/v1/files/${kept.id}/content`, { headers: { authorization: `Bearer ${W.tok}`, "x-workspace-id": W.ws } });
  assert.equal(await content.text(), "Kept document: the boiler room key is held by facilities.");

  // the restarted worker resumes the queue and the cleanup removes the deleted source physically
  startWorker();
  const del = await W.ok("DELETE", `/v1/files/${kept.id}?scope=workspace`);
  await waitJob(W, del.job_id);
  assert.equal((await owner.query("SELECT count(*)::int n FROM files WHERE id = ANY($1)", [[gone.id, kept.id]])).rows[0].n, 0);
});
