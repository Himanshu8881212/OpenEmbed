// CLI customer journey against the real service (T01–T19 paths that the CLI covers), plus generated snippets.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, describe, test } from "node:test";
import { BASE, owner, ROOT, startWorker, stopAllWorkers, token } from "./helpers.mjs";

const dir = mkdtempSync(join(tmpdir(), "kb-cli-"));
const cfgDir = join(dir, "cfg");
function kb(args, env = {}) {
  const r = spawnSync(process.execPath, [`${ROOT}cli/kb.ts`, ...args], { env: { ...process.env, KB_CONFIG_DIR: cfgDir, KB_BASE_URL: "", ...env }, encoding: "utf8", timeout: 600_000 });
  return { code: r.status, out: r.stdout, err: r.stderr };
}
/** 16 kHz mono 16-bit PCM WAV (440 Hz tone) of about `bytes` bytes. */
function wav(bytes) {
  const n = Math.floor((bytes - 44) / 2), b = Buffer.alloc(44 + n * 2);
  b.write("RIFF", 0); b.writeUInt32LE(36 + n * 2, 4); b.write("WAVEfmt ", 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(16000, 24); b.writeUInt32LE(32000, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write("data", 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(8000 * Math.sin((2 * Math.PI * 440 * i) / 16000)), 44 + i * 2);
  return b;
}
const json = (args, env) => { const r = kb([...args, "--json"], env); assert.equal(r.code, 0, r.err); return JSON.parse(r.out); };

before(async () => {
  startWorker();
  mkdirSync(cfgDir, { recursive: true });
  writeFileSync(join(cfgDir, "credentials.json"), JSON.stringify({ access_token: await token("alice") }), { mode: 0o600 });
  const m = join(dir, "company-material");
  mkdirSync(join(m, "manuals"), { recursive: true });
  writeFileSync(join(m, "manuals/pressure.md"), "# Pressure sensor\n\nTo replace the pressure sensor remove the four M6 bolts and disconnect connector P7, then run CAL-22.");
  writeFileSync(join(m, "canteen.txt"), "The canteen serves lunch from 11:30 to 14:00.");
  writeFileSync(join(m, "recording.wav"), wav(9 * 1024 * 1024)); // > 1 upload part
  writeFileSync(join(m, ".env"), "SECRET=1");
  writeFileSync(join(m, "tool.exe"), "MZ");
  symlinkSync("/etc/hosts", join(m, "hosts.txt"));
  const bad = join(dir, "partial");
  mkdirSync(bad);
  writeFileSync(join(bad, "ok.txt"), "Forklift batteries are charged overnight.");
  writeFileSync(join(bad, "corrupt.jpg"), "not a jpeg");
});
after(async () => { await stopAllWorkers(); await owner.end(); rmSync(dir, { recursive: true, force: true }); });

describe("CLI journey", () => {
  let storeId, fileId, keySecret, keyId;
  test("help works offline and lists prerequisites + API mapping", () => {
    const top = kb(["help"]);
    assert.equal(top.code, 0);
    assert.match(top.out, /kb ingest STORE/);
    const sub = kb(["ingest", "--help"]);
    assert.match(sub.out, /API: POST \/v1\/upload-sessions/);
    assert.equal(kb(["nonsense"]).code, 1);
  });
  test("T01: configure base URL and workspace", () => {
    assert.equal(kb(["config", "set", "base-url", BASE]).code, 0);
    const w = json(["workspaces", "create", "cli-acme"]);
    assert.ok(w.id);
    const me = json(["auth", "status"]);
    assert.equal(me.email, "alice@example.com");
  });
  test("T02/T03/T04: create store; interrupted ingest resumes; ignored files listed; --wait exit 0", () => {
    storeId = json(["stores", "create", "manuals"]).id;
    const first = kb(["ingest", "manuals", join(dir, "company-material"), "--yes", "--wait"], { KB_TEST_FAIL_AFTER_PARTS: "2", KB_UPLOAD_CONCURRENCY: "1" });
    assert.equal(first.code, 1);
    assert.match(first.err, /ignored: \.env \(hidden\)/);
    assert.match(first.err, /ignored: hosts\.txt \(symbolic link\)/);
    assert.match(first.err, /ignored: tool\.exe \(unsupported format\)/);
    const sid = /--resume ([0-9a-f-]{36})/.exec(first.err)[1];
    const st = json(["uploads", "status", sid]);
    assert.ok(st.files.some((f) => f.parts_received.length < f.parts));
    const resumed = kb(["ingest", "--resume", sid, "--wait"]);
    assert.equal(resumed.code, 0, resumed.err);
    assert.match(resumed.err, /completed — 3\/3 succeeded/);
  });
  test("T15: search returns source-linked evidence (JSON on stdout, progress on stderr)", () => {
    const r = json(["search", "manuals", "Replace the pressure sensor", "--limit", "5"]);
    assert.equal(r.results[0].source.path, "manuals/pressure.md");
    assert.ok(r.request_id && r.index_revision && r.profile_id);
    fileId = r.results[0].source.file_id;
    const human = kb(["search", "manuals", "when is lunch"]);
    assert.match(human.out.split("\n")[0], /canteen\.txt/);
  });
  test("T07/T08: inspect and tag", () => {
    const f = json(["files", "inspect", fileId, "--segments"]);
    assert.equal(f.status, "published");
    assert.ok(f.segments.length >= 1);
    const t = json(["files", "tag", fileId, "--set", "department=service"]);
    assert.equal(t.metadata.department, "service");
    assert.equal(t.reprocessing_required, false);
    const filtered = json(["search", "manuals", "lunch", "--filter", '{"metadata":{"department":"service"}}']);
    assert.ok(filtered.results.every((x) => x.source.file_id === fileId));
  });
  test("T09: replace content", () => {
    const v2 = join(dir, "pressure-v2.md");
    writeFileSync(v2, "# Pressure sensor v2\n\nNew procedure: use sensor PS-500 and torque the bolts to 11 Nm.");
    const r = kb(["files", "replace", fileId, v2, "--wait"]);
    assert.equal(r.code, 0, r.err);
    const s = json(["search", "manuals", "PS-500 torque", "--limit", "1"]);
    assert.equal(s.results[0].source.version_no, 2);
  });
  test("T16: key + connect; generated Python, JavaScript and cURL code run against the service", () => {
    const k = json(["keys", "create", "--store", "manuals", "--scope", "search"]);
    keySecret = k.secret; keyId = k.id;
    for (const [lang, cmd] of [["python", [`${ROOT}py/.venv/bin/python`, "-"]], ["javascript", [process.execPath, "--input-type=module", "-"]], ["curl", ["bash", "-s"]]]) {
      const code = kb(["connect", "manuals", "--language", lang]);
      assert.equal(code.code, 0);
      assert.match(code.err, /query model: eg2-/);
      assert.ok(!code.out.includes(keySecret), "secret never embedded in code");
      const run = spawnSync(cmd[0], cmd.slice(1), { input: code.out, env: { ...process.env, KNOWLEDGE_API_KEY: keySecret }, encoding: "utf8", timeout: 60_000 });
      assert.equal(run.status, 0, `${lang}: ${run.stderr}`);
      assert.match(run.stdout, /pressure/, lang);
    }
    const c = json(["connect", "manuals"]);
    const run = spawnSync(`${ROOT}py/.venv/bin/python`, ["-"], { input: c.snippets.embeddings_python, env: { ...process.env, KNOWLEDGE_API_KEY: keySecret }, encoding: "utf8" });
    assert.equal(run.stdout.trim(), "768", run.stderr);
  });
  test("partial import exits nonzero (3) and reports item errors", () => {
    const r = kb(["ingest", "manuals", join(dir, "partial"), "--yes", "--wait"]);
    assert.equal(r.code, 3, r.err);
    assert.match(r.err, /failed: corrupt\.jpg — UNREADABLE/);
  });
  test("T17/T19: usage; key revocation", () => {
    const u = json(["usage", "show"]);
    assert.ok(u.indexing.total_tokens > 0);
    assert.equal(kb(["keys", "revoke", keyId]).code, 0);
    const r = kb(["search", "manuals", "x"], { KB_API_KEY: keySecret });
    assert.equal(r.code, 1);
    assert.match(r.err, /401 AUTHENTICATION_REQUIRED/);
  });
  test("T10/T14: remove membership; delete store with preview and explicit scope", () => {
    assert.equal(kb(["files", "remove", "manuals", fileId]).code, 0);
    assert.ok(json(["search", "manuals", "pressure sensor"]).results.every((x) => x.source.file_id !== fileId));
    const noScope = kb(["stores", "delete", "manuals", "--yes"]);
    assert.equal(noScope.code, 1);
    assert.match(noScope.err, /memberships/);
    assert.equal(kb(["stores", "delete", "manuals", "--sources", "unshared", "--yes", "--wait"]).code, 0);
    const gone = kb(["search", "manuals", "x"]);
    assert.equal(gone.code, 1);
  });
  test("credentials file is private", () => {
    assert.equal(statSync(join(cfgDir, "credentials.json")).mode & 0o777, 0o600);
  });
});
