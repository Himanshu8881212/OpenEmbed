// Integration test helpers. Real services: API (KB_TEST_BASE_URL), PostgreSQL/pgvector, S3, Keycloak, inference.
// Workers are spawned by the tests themselves so they can be killed/restarted.
import { spawn } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";
import pg from "pg";

process.loadEnvFile?.(new URL("../.env", import.meta.url).pathname);
export const BASE = process.env.KB_TEST_BASE_URL ?? "http://localhost:3000";
export const ROOT = new URL("..", import.meta.url).pathname;
export { sleep, randomUUID };

const tokens = new Map();
/** Dev-IdP password grant for the DEV ONLY `kb-test` client (production uses the device flow). */
export async function token(user) {
  if (tokens.has(user) && tokens.get(user).exp > Date.now() + 60_000) return tokens.get(user).t;
  const r = await fetch(`${process.env.KB_OIDC_ISSUER}/protocol/openid-connect/token`, {
    method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "password", client_id: "kb-test", username: `${user}@example.com`, password: `dev-${user}-password`, scope: "openid email" }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(`token for ${user}: ${JSON.stringify(j)}`);
  tokens.set(user, { t: j.access_token, exp: Date.now() + j.expires_in * 1000 });
  return j.access_token;
}

/** HTTP call; returns { status, body, headers }. `ws` sets X-Workspace-Id. */
export async function api(auth, method, path, body, opts = {}) {
  const headers = { ...(opts.headers ?? {}) };
  if (auth) headers.authorization = `Bearer ${auth}`;
  if (opts.ws) headers["x-workspace-id"] = opts.ws;
  let payload;
  if (opts.raw) payload = opts.raw;
  else if (body !== undefined) { headers["content-type"] = "application/json"; payload = JSON.stringify(body); }
  let r;
  for (let attempt = 0; ; attempt++) {
    try { r = await fetch(BASE + path, { method, headers, body: payload }); break; }
    catch (e) {
      // a keep-alive socket closed by the server while the test was blocked (e.g. execFileSync) resets once
      if (attempt === 0 && ["GET", "PUT", "DELETE"].includes(method) && ["ECONNRESET", "UND_ERR_SOCKET"].includes(e.cause?.code)) continue; // idempotent methods only
      throw new Error(`${method} ${path}: ${e.cause?.code ?? e.message}`);
    }
  }
  const text = await r.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch { json = text; }
  return { status: r.status, body: json, headers: r.headers };
}

/** A user client bound to a workspace. */
export function client(tok, ws) {
  const c = (m, p, b, o = {}) => api(tok, m, p, b, { ws, ...o });
  c.ok = async (m, p, b, o) => {
    const r = await c(m, p, b, o);
    if (r.status >= 400) throw new Error(`${m} ${p} -> ${r.status} ${JSON.stringify(r.body)}`);
    return r.body;
  };
  c.tok = tok; c.ws = ws;
  return c;
}

export async function newWorkspace(user, name = `ws-${randomUUID().slice(0, 8)}`) {
  const tok = await token(user);
  const w = await api(tok, "POST", "/v1/workspaces", { name });
  if (w.status !== 201) throw new Error(JSON.stringify(w.body));
  return client(tok, w.body.id);
}

export async function newStore(c, name = `s-${randomUUID().slice(0, 8)}`) {
  return c.ok("POST", "/v1/stores", { name });
}

export const sha = (b) => createHash("sha256").update(b).digest("hex");

/** Upload files through a resumable session. files: [{path, data:Buffer}]. Returns {session, commit}. */
export async function upload(c, storeId, files, { commit = true, partSha = true, skipParts = [] } = {}) {
  const r = await c("POST", "/v1/upload-sessions", { ...(storeId ? { store_id: storeId } : {}), files: files.map((f) => ({ path: f.path, size: f.data.length, sha256: f.manifestSha ?? sha(f.data), ...(f.replaces ? { replaces_file_id: f.replaces } : {}) })) });
  if (r.status !== 201) throw new Error(`session ${r.status} ${JSON.stringify(r.body)}`);
  const s = r.body;
  for (const sf of s.files) {
    const data = files.find((f) => f.path === sf.path).data;
    for (let n = 1; n <= sf.parts; n++) {
      if (skipParts.includes(`${sf.path}:${n}`)) continue;
      const part = data.subarray((n - 1) * s.part_bytes, n * s.part_bytes);
      const pr = await c("PUT", `/v1/upload-sessions/${s.id}/files/${sf.id}/parts/${n}`, undefined, { raw: part, headers: { "content-type": "application/octet-stream", ...(partSha ? { "x-part-sha256": sha(part) } : {}) } });
      if (pr.status !== 200) throw new Error(`part ${pr.status} ${JSON.stringify(pr.body)}`);
    }
  }
  if (!commit) return { session: s };
  const cm = await c("POST", `/v1/upload-sessions/${s.id}/commit`, {}, { headers: { "idempotency-key": `commit-${s.id}` } });
  return { session: s, commit: cm };
}

export async function waitJob(c, id, timeoutMs = 240_000) {
  const end = Date.now() + timeoutMs;
  for (;;) {
    const j = await c.ok("GET", `/v1/jobs/${id}`);
    if (["completed", "completed_with_errors", "failed", "cancelled"].includes(j.state)) return j;
    if (Date.now() > end) throw new Error(`job ${id} still ${j.state}: ${JSON.stringify(j.items)}`);
    await sleep(500);
  }
}

export async function ingest(c, storeId, files) {
  const { commit } = await upload(c, storeId, files);
  if (commit.status !== 202) throw new Error(`commit ${commit.status} ${JSON.stringify(commit.body)}`);
  return waitJob(c, commit.body.job_id);
}

export const search = (c, storeId, text, extra = {}) => c.ok("POST", `/v1/stores/${storeId}/search`, { query: { text }, limit: 10, ...extra });

// ---------------------------------------------------------------- database access
export const owner = new pg.Pool({ connectionString: process.env.KB_MIGRATE_DATABASE_URL, max: 3 });
export const apiRole = (max = 1) => new pg.Pool({ connectionString: process.env.KB_DATABASE_URL, max });
export const workerRole = (max = 1) => new pg.Pool({ connectionString: process.env.KB_WORKER_DATABASE_URL, max });

// ---------------------------------------------------------------- worker processes
const workers = new Set();
let allWorkerLogs = "";
/** Everything spawned workers wrote (INFO level), for log-hygiene assertions. */
export const workerLogs = () => allWorkerLogs + [...workers].map((w) => w.log).join("");
export function startWorker(env = {}) {
  const p = spawn(`${ROOT}py/.venv/bin/python`, ["-m", "kbpy.worker"], {
    cwd: `${ROOT}py`, env: { ...process.env, KB_LEASE_SECONDS: "6", KB_WORKER_CONCURRENCY: "2", KB_LOG_LEVEL: "INFO", ...env }, stdio: ["ignore", "ignore", "pipe"],
  });
  p.log = "";
  p.stderr.on("data", (d) => { p.log += d; if (p.log.length > 100_000) p.log = p.log.slice(-50_000); });
  workers.add(p);
  p.on("exit", () => { allWorkerLogs += p.log; workers.delete(p); });
  return p;
}
export async function stopWorker(p, signal = "SIGTERM") {
  if (p.exitCode !== null) return;
  const done = new Promise((r) => p.once("exit", r));
  p.kill(signal);
  await Promise.race([done, sleep(15_000)]);
}
export async function stopAllWorkers() {
  for (const p of [...workers]) await stopWorker(p);
}

export function corpusFiles(dir = `${ROOT}tests/fixtures/corpus`) {
  const out = [];
  const walk = (d, rel = "") => {
    for (const n of readdirSync(d).sort()) {
      const abs = `${d}/${n}`, r = rel ? `${rel}/${n}` : n;
      if (statSync(abs).isDirectory()) walk(abs, r); else out.push({ path: r, data: readFileSync(abs) });
    }
  };
  walk(dir);
  return out;
}

export const norm = (v) => Math.sqrt(v.reduce((a, x) => a + x * x, 0));
export const dot = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);
