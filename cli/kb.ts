#!/usr/bin/env node
// kb — Multimodal Knowledge Store CLI. Calls the HTTP API only; uploads the actual bytes of local files.
// Runs on Node >= 23.6 (built-in TypeScript type stripping). No third-party dependencies.
import { createHash, randomUUID } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, openSync, readFileSync, readSync, closeSync, writeFileSync, createReadStream, lstatSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, relative, sep, basename, dirname } from "node:path";
import { createInterface } from "node:readline/promises";
import { parseArgs } from "node:util";

const VERSION = "0.1.0";
const EXIT = { ok: 0, error: 1, partial: 3, failed: 4, cancelled: 5 } as const;
const CONFIG_DIR = process.env.KB_CONFIG_DIR ?? join(homedir(), ".config", "kb");
const err = (s: string) => process.stderr.write(s + "\n");
const out = (s: string) => process.stdout.write(s + "\n");

class CliError extends Error { exit: number; constructor(msg: string, exit: number = EXIT.error) { super(msg); this.exit = exit; } }

// ------------------------------------------------------------ config & credentials
type Config = { base_url?: string; workspace_id?: string };
type Creds = { access_token?: string; refresh_token?: string; expires_at?: number };
const readJson = <T>(f: string, d: T): T => (existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : d);
function writePrivate(f: string, v: unknown) {
  mkdirSync(dirname(f), { recursive: true, mode: 0o700 });
  writeFileSync(f, JSON.stringify(v, null, 2), { mode: 0o600 });
  chmodSync(f, 0o600);
}
const cfgFile = join(CONFIG_DIR, "config.json"), credFile = join(CONFIG_DIR, "credentials.json");
const cfg = (): Config => readJson(cfgFile, {});
const baseUrl = () => (process.env.KB_BASE_URL || cfg().base_url || "").replace(/\/$/, "") || (() => { throw new CliError("Set the API base URL: kb config set base-url https://… (or KB_BASE_URL)"); })();

// ------------------------------------------------------------ HTTP
type ReqOpts = { method?: string; body?: unknown; raw?: Buffer; headers?: Record<string, string>; auth?: boolean };
async function token(): Promise<string> {
  if (process.env.KB_API_KEY) return process.env.KB_API_KEY;
  const c = readJson<Creds>(credFile, {});
  if (!c.access_token) throw new CliError("Not authenticated: run kb auth login (or set KB_API_KEY for scripts)");
  if (c.expires_at && Date.now() > c.expires_at - 30_000 && c.refresh_token) {
    const r = await fetch(`${baseUrl()}/v1/auth/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ grant_type: "refresh_token", refresh_token: c.refresh_token }) });
    if (!r.ok) throw new CliError("Session expired: run kb auth login");
    const j = await r.json();
    writePrivate(credFile, { access_token: j.access_token, refresh_token: j.refresh_token ?? c.refresh_token, expires_at: Date.now() + j.expires_in * 1000 });
    return j.access_token;
  }
  return c.access_token;
}
async function api(path: string, o: ReqOpts = {}): Promise<any> {
  const headers: Record<string, string> = { ...(o.headers ?? {}), "user-agent": `kb-cli/${VERSION}` };
  if (o.auth !== false) headers.authorization = `Bearer ${await token()}`;
  const ws = process.env.KB_WORKSPACE ?? cfg().workspace_id;
  if (ws && !process.env.KB_API_KEY) headers["x-workspace-id"] = ws;
  if (o.body !== undefined) headers["content-type"] = "application/json";
  let res: Response | undefined;
  for (let attempt = 0; ; attempt++) {
    try {
      res = await fetch(baseUrl() + path, { method: o.method ?? "GET", headers, body: o.raw ?? (o.body !== undefined ? JSON.stringify(o.body) : undefined), signal: AbortSignal.timeout(300_000) });
      if (res.status < 500 || attempt >= 3 || !["GET", "PUT"].includes(o.method ?? "GET")) break;
    } catch (e) {
      if (attempt >= 3) throw new CliError(`Network failure calling ${baseUrl()}: ${(e as Error).message}`);
    }
    await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
  }
  if (res!.status === 204) return null;
  const text = await res!.text();
  const j = text ? JSON.parse(text) : null;
  if (!res!.ok) {
    const e = j?.error ?? {};
    throw new CliError(`${res!.status} ${e.code ?? ""}: ${e.message ?? text}${e.request_id ? ` (request ${e.request_id})` : ""}`);
  }
  return j;
}

// ------------------------------------------------------------ helpers
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
async function storeId(ref: string): Promise<string> {
  if (UUID.test(ref)) return ref;
  const r = await api(`/v1/stores?name=${encodeURIComponent(ref)}`);
  if (r.data.length !== 1) throw new CliError(`No visible store named '${ref}'`);
  return r.data[0].id;
}
async function sha256File(path: string): Promise<string> {
  const h = createHash("sha256");
  for await (const c of createReadStream(path)) h.update(c as Buffer);
  return h.digest("hex");
}
function readPart(path: string, offset: number, len: number): Buffer {
  const fd = openSync(path, "r");
  try { const b = Buffer.alloc(len); let n = 0; while (n < len) { const r = readSync(fd, b, n, len - n, offset + n); if (!r) break; n += r; } return b.subarray(0, n); } finally { closeSync(fd); }
}
async function confirm(q: string, yes: boolean) {
  if (yes) return;
  if (!process.stdin.isTTY) throw new CliError("Confirmation required: re-run with --yes");
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  const a = await rl.question(q + " [y/N] ");
  rl.close();
  if (!/^y(es)?$/i.test(a.trim())) throw new CliError("Aborted");
}
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const fmtBytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KiB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MiB` : `${(n / 1073741824).toFixed(2)} GiB`);

async function waitJob(id: string, json: boolean): Promise<number> {
  let last = "";
  for (;;) {
    const j = await api(`/v1/jobs/${id}`);
    const line = `job ${id}: ${j.state} — ${j.items.succeeded}/${j.items.total} succeeded, ${j.items.failed} failed, ${j.items.running} running`;
    if (line !== last) { err(line); last = line; }
    if (["completed", "completed_with_errors", "failed", "cancelled"].includes(j.state)) {
      if (j.items.failed) {
        const items = await api(`/v1/jobs/${id}/items?state=failed&limit=200`);
        for (const i of items.data) err(`  failed: ${i.path} — ${i.error?.code}: ${i.error?.message}${i.retryable ? " (retryable)" : ""}`);
      }
      if (json) out(JSON.stringify(j, null, 2));
      return { completed: EXIT.ok, completed_with_errors: EXIT.partial, failed: EXIT.failed, cancelled: EXIT.cancelled }[j.state as "completed"];
    }
    await sleep(1000);
  }
}
const accepted = async (r: any, wait: boolean, json: boolean) => {
  if (wait) return waitJob(r.job_id, json);
  if (json) out(JSON.stringify(r, null, 2)); else out(`accepted: job ${r.job_id} (${r.state}) — kb jobs status ${r.job_id}`);
  return EXIT.ok;
};

// ------------------------------------------------------------ ingest
type ScanResult = { files: { abs: string; path: string; size: number }[]; ignored: { path: string; reason: string }[] };
function scan(root: string, exts: Set<string>, maxBytes: number): ScanResult {
  const res: ScanResult = { files: [], ignored: [] };
  const walk = (dir: string) => {
    for (const d of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const abs = join(dir, d.name), rel = relative(root, abs).split(sep).join("/");
      if (d.isSymbolicLink()) { res.ignored.push({ path: rel, reason: "symbolic link" }); continue; }
      if (d.name.startsWith(".")) { res.ignored.push({ path: rel, reason: "hidden" }); continue; }
      if (d.isDirectory()) { walk(abs); continue; }
      if (!d.isFile()) { res.ignored.push({ path: rel, reason: "not a regular file" }); continue; }
      const ext = (/\.[^.]+$/.exec(d.name.toLowerCase()) ?? [""])[0];
      const size = lstatSync(abs).size;
      if (!exts.has(ext)) res.ignored.push({ path: rel, reason: "unsupported format" });
      else if (size === 0) res.ignored.push({ path: rel, reason: "empty file" });
      else if (size > maxBytes) res.ignored.push({ path: rel, reason: `larger than ${fmtBytes(maxBytes)}` });
      else res.files.push({ abs, path: rel, size });
    }
  };
  walk(root);
  return res;
}

const sessFile = (id: string) => join(CONFIG_DIR, "sessions", `${id}.json`);
async function uploadSession(session: any, local: Record<string, string>, concurrency = Number(process.env.KB_UPLOAD_CONCURRENCY || 4)) {
  const todo: { f: any; part: number }[] = [];
  for (const f of session.files) {
    const have = new Set(f.parts_received);
    for (let n = 1; n <= f.parts; n++) if (!have.has(n)) todo.push({ f, part: n });
  }
  let done = 0;
  const worker = async () => {
    for (let t; (t = todo.shift()); ) {
      const off = (t.part - 1) * session.part_bytes;
      const buf = readPart(local[t.f.path], off, Math.min(session.part_bytes, t.f.size - off));
      await api(`/v1/upload-sessions/${session.id}/files/${t.f.id}/parts/${t.part}`, { method: "PUT", raw: buf, headers: { "content-type": "application/octet-stream", "x-part-sha256": createHash("sha256").update(buf).digest("hex") } });
      done++;
      if (process.env.KB_TEST_FAIL_AFTER_PARTS && done >= Number(process.env.KB_TEST_FAIL_AFTER_PARTS)) throw new CliError(`simulated interruption after ${done} parts; resume with: kb ingest --resume ${session.id}`);
      if (done % 10 === 0 || !todo.length) err(`  uploaded ${done} part(s), ${todo.length} remaining`);
    }
  };
  await Promise.all(Array.from({ length: concurrency }, worker));
}

async function ingest(a: Args) {
  const json = !!a.values.json, wait = !!a.values.wait;
  let session: any, local: Record<string, string>, sid: string;
  if (a.values.resume) {
    sid = String(a.values.resume);
    const saved = readJson<any>(sessFile(sid), null);
    if (!saved) throw new CliError(`No local record of session ${sid}`);
    session = await api(`/v1/upload-sessions/${sid}`);
    if (session.state !== "open") throw new CliError(`Session ${sid} is ${session.state}; start a new import`);
    local = saved.local;
    for (const f of session.files) {
      if (!existsSync(local[f.path]) || (await sha256File(local[f.path])) !== f.sha256) throw new CliError(`${f.path} changed since the session started; start a new import`);
    }
    err(`resuming session ${sid}`);
  } else {
    const [storeRef, folder] = a.positionals;
    if (!storeRef || !folder) throw new CliError("usage: kb ingest STORE ./folder [--wait] [--yes]");
    if (!existsSync(folder) || !lstatSync(folder).isDirectory()) throw new CliError(`${folder} is not a local folder`);
    const sid0 = await storeId(storeRef);
    const prof = await api("/v1/embedding-profiles");
    const s = scan(folder, new Set(prof.formats.map((f: any) => f.extension)), prof.limits.max_file_bytes);
    for (const i of s.ignored) err(`  ignored: ${i.path} (${i.reason})`);
    if (!s.files.length) throw new CliError("No supported files to upload");
    const total = s.files.reduce((x, f) => x + f.size, 0);
    err(`manifest: ${s.files.length} file(s), ${fmtBytes(total)}; ${s.ignored.length} ignored`);
    await confirm("Upload these files?", !!a.values.yes);
    const files = [];
    for (const f of s.files) files.push({ path: f.path, size: f.size, sha256: await sha256File(f.abs) });
    session = await api("/v1/upload-sessions", { method: "POST", body: { store_id: sid0, files } });
    sid = session.id;
    local = Object.fromEntries(s.files.map((f) => [f.path, f.abs]));
    writePrivate(sessFile(sid), { local, store_id: sid0 });
    err(`upload session ${sid}`);
  }
  await uploadSession(session, local);
  const r = await api(`/v1/upload-sessions/${sid}/commit`, { method: "POST", body: {}, headers: { "idempotency-key": `commit-${sid}` } });
  err(`committed; job ${r.job_id}`);
  return accepted(r, wait, json);
}

// ------------------------------------------------------------ commands
type Args = ReturnType<typeof parseArgs> & { values: Record<string, any> };
type Cmd = { usage: string; help: string; api: string; opts?: Record<string, { type: "string" | "boolean"; short?: string; multiple?: boolean }>; run: (a: Args) => Promise<number | void> };
const jsonOpt = { json: { type: "boolean" as const } };
const print = (a: Args, v: any, human: (v: any) => string) => out(a.values.json ? JSON.stringify(v, null, 2) : human(v));

const COMMANDS: Record<string, Cmd> = {
  "config set": { usage: "kb config set base-url URL | workspace ID", help: "Store local CLI configuration (no network).", api: "local only",
    run: async (a) => { const [k, v] = a.positionals; const c = cfg(); if (k === "base-url") c.base_url = v; else if (k === "workspace") c.workspace_id = v; else throw new CliError("keys: base-url, workspace"); writePrivate(cfgFile, c); out(`${k} = ${v}`); } },
  "config show": { usage: "kb config show", help: "Show local configuration.", api: "local only", run: async () => out(JSON.stringify({ ...cfg(), config_dir: CONFIG_DIR, api_key_env: !!process.env.KB_API_KEY }, null, 2)) },
  "auth login": { usage: "kb auth login", help: "Authenticate a human user with the browser device flow. Prerequisite: base URL configured; a workspace invitation or account.", api: "POST /v1/auth/device-sessions, POST /v1/auth/token, GET /v1/me",
    run: async () => {
      const d = await api("/v1/auth/device-sessions", { method: "POST", auth: false });
      err(`Open ${d.verification_uri_complete ?? d.verification_uri} and confirm code ${d.user_code}`);
      const until = Date.now() + d.expires_in * 1000;
      while (Date.now() < until) {
        await sleep(d.interval * 1000);
        const r = await fetch(`${baseUrl()}/v1/auth/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ grant_type: "device_code", device_code: d.device_code }) });
        const j = await r.json();
        if (r.ok) {
          writePrivate(credFile, { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Date.now() + j.expires_in * 1000 });
          const me = await api("/v1/me");
          if (me.workspaces.length === 1) writePrivate(cfgFile, { ...cfg(), workspace_id: me.workspaces[0].id });
          out(`Signed in as ${me.email}. Workspaces: ${me.workspaces.map((w: any) => `${w.name} (${w.role})`).join(", ") || "none — run kb workspaces create NAME"}`);
          return;
        }
        if (!["AUTHORIZATION_PENDING", "SLOW_DOWN"].includes(j.error?.code)) throw new CliError(`Login failed: ${j.error?.message}`);
      }
      throw new CliError("The device code expired; run kb auth login again");
    } },
  "auth status": { usage: "kb auth status [--json]", help: "Show the current identity and workspace.", api: "GET /v1/me", opts: jsonOpt,
    run: async (a) => print(a, await api("/v1/me"), (m) => m.kind === "user" ? `${m.email}; workspaces: ${m.workspaces.map((w: any) => `${w.name} ${w.id} (${w.role})`).join(", ")}; selected: ${cfg().workspace_id ?? "-"}` : `API key ${m.key_id}; scopes ${m.scopes.join(",")}`) },
  "auth logout": { usage: "kb auth logout", help: "Remove local credentials.", api: "local only", run: async () => { writePrivate(credFile, {}); out("signed out"); } },
  "workspaces list": { usage: "kb workspaces list [--json]", help: "List accessible workspaces.", api: "GET /v1/workspaces", opts: jsonOpt, run: async (a) => print(a, await api("/v1/workspaces"), (r) => r.data.map((w: any) => `${w.id}  ${w.name}  ${w.role}`).join("\n")) },
  "workspaces create": { usage: "kb workspaces create NAME", help: "Create a workspace (you become owner) and select it.", api: "POST /v1/workspaces", opts: jsonOpt,
    run: async (a) => { const w = await api("/v1/workspaces", { method: "POST", body: { name: a.positionals[0] } }); writePrivate(cfgFile, { ...cfg(), workspace_id: w.id }); print(a, w, (w) => `created workspace ${w.id} (${w.name}); selected`); } },
  "workspaces use": { usage: "kb workspaces use ID", help: "Select the workspace for later commands.", api: "local only", run: async (a) => { writePrivate(cfgFile, { ...cfg(), workspace_id: a.positionals[0] }); out(`selected ${a.positionals[0]}`); } },
  "members list": { usage: "kb members list", help: "List workspace members.", api: "GET /v1/workspaces/{id}/members", opts: jsonOpt, run: async (a) => print(a, await api(`/v1/workspaces/${wsId()}/members`), (r) => r.data.map((m: any) => `${m.id}  ${m.email}  ${m.role}  ${m.status}`).join("\n")) },
  "members add": { usage: "kb members add EMAIL --role owner|editor|viewer", help: "Invite a member (owner only).", api: "POST /v1/workspaces/{id}/members", opts: { role: { type: "string" }, ...jsonOpt }, run: async (a) => print(a, await api(`/v1/workspaces/${wsId()}/members`, { method: "POST", body: { email: a.positionals[0], role: a.values.role } }), (m) => `invited ${m.email} as ${m.role}`) },
  "members update": { usage: "kb members update MEMBER_ID --role ROLE", help: "Change a member role (owner only).", api: "PATCH /v1/workspaces/{id}/members/{member_id}", opts: { role: { type: "string" } }, run: async (a) => { await api(`/v1/workspaces/${wsId()}/members/${a.positionals[0]}`, { method: "PATCH", body: { role: a.values.role } }); out("updated"); } },
  "members remove": { usage: "kb members remove MEMBER_ID", help: "Remove a member (owner only).", api: "DELETE /v1/workspaces/{id}/members/{member_id}", run: async (a) => { await api(`/v1/workspaces/${wsId()}/members/${a.positionals[0]}`, { method: "DELETE" }); out("removed"); } },
  "stores create": { usage: "kb stores create NAME [--profile ID]", help: "Create an empty material store. Prerequisite: editor role.", api: "POST /v1/stores", opts: { profile: { type: "string" }, ...jsonOpt },
    run: async (a) => print(a, await api("/v1/stores", { method: "POST", body: { name: a.positionals[0], ...(a.values.profile ? { profile_id: a.values.profile } : {}) } }), (s) => `created store ${s.name}\n  id: ${s.id}\n  profile: ${s.profile_id}\n  query model: ${s.query_model}`) },
  "stores list": { usage: "kb stores list [--json]", help: "List accessible stores.", api: "GET /v1/stores", opts: jsonOpt, run: async (a) => print(a, await api("/v1/stores?limit=200"), (r) => r.data.map((s: any) => `${s.id}  ${s.name}  ${s.kind}  ${s.file_count} files  ${s.state}`).join("\n") || "no stores") },
  "stores info": { usage: "kb stores info STORE [--json]", help: "Inspect state, profile and size.", api: "GET /v1/stores/{id}, GET /v1/stores/{id}/stats", opts: jsonOpt,
    run: async (a) => { const id = await storeId(a.positionals[0]); const s = await api(`/v1/stores/${id}`), st = await api(`/v1/stores/${id}/stats`); print(a, { ...s, stats: st }, () => `${s.name} (${s.kind})\n  id: ${s.id}\n  profile: ${s.profile_id}\n  index revision: ${s.index_revision}\n  files: ${st.files}  segments: ${st.segments}  source bytes: ${fmtBytes(st.source_bytes)}\n  state: ${s.state}`); } },
  "stores rename": { usage: "kb stores rename STORE NEW_NAME", help: "Rename (ID and connections unchanged).", api: "PATCH /v1/stores/{id}", opts: jsonOpt, run: async (a) => print(a, await api(`/v1/stores/${await storeId(a.positionals[0])}`, { method: "PATCH", body: { name: a.positionals[1] } }), (s) => `renamed to ${s.name} (${s.id})`) },
  "stores delete": { usage: "kb stores delete STORE --sources unshared|keep [--yes] [--wait]", help: "Preview, then delete a store. --sources unshared also deletes sources no other store uses.", api: "POST /v1/stores/{id}/deletion-previews, DELETE /v1/stores/{id}", opts: { sources: { type: "string" }, yes: { type: "boolean" }, wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => {
      const id = await storeId(a.positionals[0]);
      const p = await api(`/v1/stores/${id}/deletion-previews`, { method: "POST", body: {} });
      err(`store ${p.name}: ${p.memberships} memberships, ${p.sources_shared_with_other_stores} shared with other stores, ${p.dependent_views.length} dependent views, ${p.restricted_api_keys.length} restricted keys`);
      if (!a.values.sources) throw new CliError("Choose --sources unshared (delete sources only this store uses) or --sources keep");
      await confirm(`Delete store ${p.name}?`, !!a.values.yes);
      return accepted(await api(`/v1/stores/${id}?sources=${a.values.sources}`, { method: "DELETE" }), !!a.values.wait, !!a.values.json);
    } },
  "stores merge": { usage: "kb stores merge A B [...] --into NAME [--wait]", help: "Later release: combine compatible stores into a new store without re-embedding.", api: "POST /v1/store-merges", opts: { into: { type: "string" }, wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => accepted(await api("/v1/store-merges", { method: "POST", body: { sources: await Promise.all(a.positionals.map(storeId)), target_name: a.values.into } }), !!a.values.wait, !!a.values.json) },
  "stores derive": { usage: "kb stores derive STORE [STORE...] --name NAME --mode view|snapshot --filter @filter.json [--wait]", help: "Later release: create a live view or snapshot over parent stores.", api: "POST /v1/stores/{id}/derivations", opts: { name: { type: "string" }, mode: { type: "string" }, filter: { type: "string" }, wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => {
      const ids = await Promise.all(a.positionals.map(storeId));
      const r = await api(`/v1/stores/${ids[0]}/derivations`, { method: "POST", body: { name: a.values.name, mode: a.values.mode, parents: ids.slice(1), filter: readFilter(a.values.filter) } });
      if (r.job_id) return accepted(r, !!a.values.wait, !!a.values.json);
      print(a, r, (s) => `created ${s.kind} ${s.name} (${s.id})`);
    } },
  "stores split": { usage: "kb stores split STORE --field KEY [--mode view|snapshot] [--prefix NAME]", help: "Create one live view (or snapshot) per value of a metadata field, reusing existing vectors.", api: "POST /v1/stores/{id}/splits", opts: { field: { type: "string" }, mode: { type: "string" }, prefix: { type: "string" }, ...jsonOpt },
    run: async (a) => {
      if (!a.values.field) throw new CliError("--field is required");
      const r = await api(`/v1/stores/${await storeId(a.positionals[0])}/splits`, { method: "POST", body: { field: a.values.field, ...(a.values.mode ? { mode: a.values.mode } : {}), ...(a.values.prefix ? { prefix: a.values.prefix } : {}) } });
      print(a, r, (r) => [...r.created.map((c: any) => `created ${c.store.kind} ${c.store.name} (${c.store.id}) for ${r.field}=${c.value}`), ...r.skipped.map((x: any) => `skipped ${x.name}: ${x.reason}`)].join("\n"));
    } },
  "stores export": { usage: "kb stores export STORE [-o FILE.jsonl] [--no-embeddings]", help: "Export indexed segments (source, location, text, embedding) as NDJSON.", api: "GET /v1/stores/{id}/export", opts: { output: { type: "string", short: "o" }, "no-embeddings": { type: "boolean" } },
    run: async (a) => {
      const id = await storeId(a.positionals[0]);
      const r = await fetch(`${baseUrl()}/v1/stores/${id}/export${a.values["no-embeddings"] ? "?include=content" : ""}`, { headers: { authorization: `Bearer ${await token()}`, ...(cfg().workspace_id && !process.env.KB_API_KEY ? { "x-workspace-id": cfg().workspace_id! } : {}) } });
      if (!r.ok) throw new CliError(`${r.status}: ${await r.text()}`);
      const text = await r.text();
      if (a.values.output) { writeFileSync(a.values.output, text); err(`wrote ${text ? text.trimEnd().split("\n").length : 0} segments (profile ${r.headers.get("x-kb-profile")}) to ${a.values.output}`); } else process.stdout.write(text);
    } },
  "profiles list": { usage: "kb profiles list [--json]", help: "Embedding profiles available to this workspace (global and custom).", api: "GET /v1/embedding-profiles", opts: jsonOpt,
    run: async (a) => print(a, await api("/v1/embedding-profiles"), (r) => r.data.map((p: any) => `${p.id}  ${p.scope}  ${p.name ?? ""}  text ${p.preparation.text.max_chars}/${p.preparation.text.overlap_chars}  audio ${p.preparation.audio.segment_seconds}s  video ${p.preparation.video.segment_seconds}s`).join("\n")) },
  "profiles create": { usage: "kb profiles create NAME --max-chars N --overlap N [--audio-seconds N] [--video-seconds N]", help: "Create an immutable custom segmentation profile; use it with stores create --profile or stores reindex.", api: "POST /v1/embedding-profiles", opts: { "max-chars": { type: "string" }, overlap: { type: "string" }, "audio-seconds": { type: "string" }, "video-seconds": { type: "string" }, ...jsonOpt },
    run: async (a) => {
      const n = (k: string) => (a.values[k] !== undefined ? Number(a.values[k]) : undefined);
      const r = await api("/v1/embedding-profiles", { method: "POST", body: { name: a.positionals[0], text: { max_chars: n("max-chars") ?? 1600, overlap_chars: n("overlap") ?? 200 }, ...(n("audio-seconds") ? { audio: { segment_seconds: n("audio-seconds") } } : {}), ...(n("video-seconds") ? { video: { segment_seconds: n("video-seconds") } } : {}) } });
      print(a, r, (r) => `created profile ${r.id} (${r.name})\n  query alias: ${r.aliases.query}\n  use: kb stores create NAME --profile ${r.id}  or  kb stores reindex STORE --profile ${r.id}`);
    } },
  "stores reindex": { usage: "kb stores reindex STORE --profile ID [--wait]", help: "Later release: build a new index with another profile (not yet active).", api: "POST /v1/stores/{id}/reindex-jobs", opts: { profile: { type: "string" }, wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => accepted(await api(`/v1/stores/${await storeId(a.positionals[0])}/reindex-jobs`, { method: "POST", body: { profile_id: a.values.profile } }), !!a.values.wait, !!a.values.json) },
  "stores promote": { usage: "kb stores promote STORE REVISION_ID", help: "Later release: activate a ready index revision (also used for rollback).", api: "POST /v1/stores/{id}/index-promotions", opts: jsonOpt,
    run: async (a) => print(a, await api(`/v1/stores/${await storeId(a.positionals[0])}/index-promotions`, { method: "POST", body: { index_revision: a.positionals[1] } }), (s) => `active index revision ${s.index_revision} (${s.profile_id})`) },
  ingest: { usage: "kb ingest STORE ./folder [--wait] [--yes] [--json] | kb ingest --resume SESSION_ID [--wait]", help: "Upload the folder's supported files (relative paths kept; symlinks/hidden/unsupported ignored and listed), commit, and start indexing. Interrupted uploads resume with --resume.", api: "POST /v1/upload-sessions, PUT …/parts/{n}, POST …/commit, GET /v1/jobs/{id}", opts: { wait: { type: "boolean" }, yes: { type: "boolean" }, resume: { type: "string" }, ...jsonOpt }, run: ingest },
  "jobs status": { usage: "kb jobs status JOB_ID [--wait] [--json]", help: "Job state and per-item counts. --wait exits nonzero on failure/partial completion.", api: "GET /v1/jobs/{id}", opts: { wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => { if (a.values.wait) return waitJob(a.positionals[0], !!a.values.json); print(a, await api(`/v1/jobs/${a.positionals[0]}`), (j) => `${j.id} ${j.kind} ${j.state}: ${j.items.succeeded}/${j.items.total} succeeded, ${j.items.failed} failed (${j.items.retryable} retryable), ${j.items.cancelled} cancelled`); } },
  "jobs list": { usage: "kb jobs list [--json]", help: "Recent jobs.", api: "GET /v1/jobs", opts: jsonOpt, run: async (a) => print(a, await api("/v1/jobs?limit=50"), (r) => r.data.map((j: any) => `${j.id}  ${j.kind}  ${j.state}  ${j.created_at}`).join("\n")) },
  "jobs items": { usage: "kb jobs items JOB_ID [--state failed] [--json]", help: "Per-file results.", api: "GET /v1/jobs/{id}/items", opts: { state: { type: "string" }, ...jsonOpt },
    run: async (a) => print(a, await api(`/v1/jobs/${a.positionals[0]}/items?limit=200${a.values.state ? `&state=${a.values.state}` : ""}`), (r) => r.data.map((i: any) => `${i.state.padEnd(9)} ${i.path}${i.error ? `  ${i.error.code}: ${i.error.message}` : ""}`).join("\n")) },
  "jobs retry": { usage: "kb jobs retry JOB_ID [--wait]", help: "Retry retryable failed items as a new job.", api: "POST /v1/jobs/{id}/retry", opts: { wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => accepted(await api(`/v1/jobs/${a.positionals[0]}/retry`, { method: "POST", body: {}, headers: { "idempotency-key": `retry-${a.positionals[0]}-${randomUUID()}` } }), !!a.values.wait, !!a.values.json) },
  "jobs cancel": { usage: "kb jobs cancel JOB_ID [--wait]", help: "Request safe cancellation; published items remain.", api: "POST /v1/jobs/{id}/cancel", opts: { wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => { const j = await api(`/v1/jobs/${a.positionals[0]}/cancel`, { method: "POST", body: {} }); if (a.values.wait) return waitJob(j.id, !!a.values.json); print(a, j, (j) => `${j.id}: ${j.state}`); } },
  "files list": { usage: "kb files list STORE [--json]", help: "Sources assigned to a store.", api: "GET /v1/stores/{id}/files", opts: jsonOpt, run: async (a) => print(a, await api(`/v1/stores/${await storeId(a.positionals[0])}/files?limit=200`), (r) => r.data.map((f: any) => `${f.id}  ${f.path}  v${f.version.version_no}  ${f.segment_count} segments`).join("\n") || "no files") },
  "files inspect": { usage: "kb files inspect FILE_ID [--segments] [--json]", help: "Current version, status, stores, segment count (and segments).", api: "GET /v1/files/{id}, GET /v1/files/{id}/segments", opts: { segments: { type: "boolean" }, ...jsonOpt },
    run: async (a) => {
      const f = await api(`/v1/files/${a.positionals[0]}`);
      const segs = a.values.segments ? (await api(`/v1/files/${f.id}/segments?limit=500`)).data : undefined;
      print(a, { ...f, segments: segs }, () => [`${f.path} (${f.status})`, `  id: ${f.id}`, f.current_version && `  version: v${f.current_version.version_no} ${f.current_version.id} ${f.current_version.media_type} ${fmtBytes(f.current_version.size)} sha256 ${f.current_version.sha256}`,
        `  segments: ${f.segment_count}`, `  metadata: ${JSON.stringify(f.metadata)}`, `  stores: ${f.stores.map((s: any) => s.name).join(", ")}`, f.last_error && `  last error: ${f.last_error.code}: ${f.last_error.message}`,
        ...(segs ?? []).map((s: any) => `  [${s.ordinal}] ${s.modality} ${JSON.stringify(s.location)} ${s.content ? JSON.stringify(s.content.slice(0, 80)) : ""}`)].filter(Boolean).join("\n"));
    } },
  "files tag": { usage: "kb files tag FILE_ID --set KEY=VALUE [--set …] [--unset KEY]", help: "Update source metadata (merge).", api: "PATCH /v1/files/{id}", opts: { set: { type: "string", multiple: true }, unset: { type: "string", multiple: true }, ...jsonOpt },
    run: async (a) => {
      const m: Record<string, string | null> = {};
      for (const kv of a.values.set ?? []) { const i = kv.indexOf("="); if (i < 1) throw new CliError(`--set expects KEY=VALUE, got ${kv}`); m[kv.slice(0, i)] = kv.slice(i + 1); }
      for (const k of a.values.unset ?? []) m[k] = null;
      print(a, await api(`/v1/files/${a.positionals[0]}`, { method: "PATCH", body: { metadata: m } }), (f) => `metadata: ${JSON.stringify(f.metadata)}${f.reprocessing_required ? " (reprocessing required)" : ""}`);
    } },
  "files replace": { usage: "kb files replace FILE_ID ./file [--wait]", help: "Upload a replacement version; the old version stays searchable until the new one publishes.", api: "POST /v1/upload-sessions, PUT parts, POST commit, POST /v1/files/{id}/revisions", opts: { wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => {
      const [fid, path] = a.positionals;
      if (!existsSync(path) || !lstatSync(path).isFile()) throw new CliError(`${path} is not a local file`);
      const f = await api(`/v1/files/${fid}`);
      const size = lstatSync(path).size;
      const s = await api("/v1/upload-sessions", { method: "POST", body: { files: [{ path: f.path.replace(/[^/]+$/, basename(path)), size, sha256: await sha256File(path), replaces_file_id: fid }] } });
      writePrivate(sessFile(s.id), { local: { [s.files[0].path]: path } });
      await uploadSession(s, { [s.files[0].path]: path });
      await api(`/v1/upload-sessions/${s.id}/commit`, { method: "POST", body: {}, headers: { "idempotency-key": `commit-${s.id}` } });
      return accepted(await api(`/v1/files/${fid}/revisions`, { method: "POST", body: { upload_session_id: s.id }, headers: { "idempotency-key": `revision-${s.id}` } }), !!a.values.wait, !!a.values.json);
    } },
  "files remove": { usage: "kb files remove STORE FILE_ID", help: "Remove the source from one store only.", api: "DELETE /v1/stores/{id}/files/{file_id}", run: async (a) => { await api(`/v1/stores/${await storeId(a.positionals[0])}/files/${a.positionals[1]}`, { method: "DELETE" }); out("removed from store"); } },
  "files delete": { usage: "kb files delete FILE_ID [--yes] [--wait]", help: "Preview, then delete the source everywhere (including snapshots).", api: "POST /v1/files/{id}/deletion-previews, DELETE /v1/files/{id}?scope=workspace", opts: { yes: { type: "boolean" }, wait: { type: "boolean" }, ...jsonOpt },
    run: async (a) => {
      const p = await api(`/v1/files/${a.positionals[0]}/deletion-previews`, { method: "POST", body: {} });
      err(`${p.path}: in ${p.stores.length} store(s), ${p.snapshots.length} snapshot(s), ${p.live_views.length} live view(s)`);
      await confirm("Delete this source everywhere?", !!a.values.yes);
      return accepted(await api(`/v1/files/${a.positionals[0]}?scope=workspace`, { method: "DELETE" }), !!a.values.wait, !!a.values.json);
    } },
  "files download": { usage: "kb files download FILE_ID [-o PATH]", help: "Download the original bytes (permission required).", api: "GET /v1/files/{id}/content", opts: { output: { type: "string", short: "o" } },
    run: async (a) => {
      const r = await fetch(`${baseUrl()}/v1/files/${a.positionals[0]}/content`, { headers: { authorization: `Bearer ${await token()}`, ...(cfg().workspace_id && !process.env.KB_API_KEY ? { "x-workspace-id": cfg().workspace_id! } : {}) } });
      if (!r.ok) throw new CliError(`${r.status}: ${await r.text()}`);
      const buf = Buffer.from(await r.arrayBuffer());
      if (a.values.output) { writeFileSync(a.values.output, buf); err(`wrote ${buf.length} bytes to ${a.values.output}`); } else process.stdout.write(buf);
    } },
  search: { usage: "kb search STORE QUERY [--limit N] [--filter @filter.json|JSON] [--image|--audio|--video PATH] [--json]", help: "Retrieve ranked evidence with source locations. Scores rank results; they are not answer confidence.", api: "POST /v1/stores/{id}/search (+ POST /v1/query-assets for media)",
    opts: { limit: { type: "string" }, filter: { type: "string" }, image: { type: "string" }, audio: { type: "string" }, video: { type: "string" }, ...jsonOpt },
    run: async (a) => {
      const [ref, ...q] = a.positionals;
      const query: any = {};
      if (q.length) query.text = q.join(" ");
      const media = a.values.image ? ["image", a.values.image] : a.values.audio ? ["audio", a.values.audio] : a.values.video ? ["video", a.values.video] : null;
      if (media) {
        const ext = (/\.[^.]+$/.exec(media[1].toLowerCase()) ?? [""])[0];
        const type = ({ ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4" } as Record<string, string>)[ext];
        if (!type) throw new CliError(`Unsupported query media ${media[1]}`);
        query.asset_id = (await api("/v1/query-assets", { method: "POST", raw: readFileSync(media[1]), headers: { "content-type": type } })).id;
      }
      const r = await api(`/v1/stores/${await storeId(ref)}/search`, { method: "POST", body: { query, limit: Number(a.values.limit ?? 5), ...(a.values.filter ? { filter: readFilter(a.values.filter) } : {}) } });
      if (query.asset_id) await api(`/v1/query-assets/${query.asset_id}`, { method: "DELETE" }).catch(() => {});
      print(a, r, (r) => r.results.length ? r.results.map((x: any, i: number) => `${i + 1}. score ${x.score.toFixed(3)}  ${x.source.path} (v${x.source.version_no}) ${JSON.stringify(x.source.location)}\n   ${typeof x.content === "string" ? x.content.replace(/\s+/g, " ").slice(0, 240) : `[${x.content.type}] ${x.content.media_url}`}`).join("\n") + `\n(request ${r.request_id}, index ${r.index_revision})` : `no results (request ${r.request_id}); check store state, filters and permissions`);
    } },
  connect: { usage: "kb connect STORE [--language python|javascript|curl] [--json]", help: "Print connection details and runnable code for an application. The code reads KNOWLEDGE_API_KEY.", api: "GET /v1/stores/{id}/connection", opts: { language: { type: "string" }, ...jsonOpt },
    run: async (a) => {
      const c = await api(`/v1/stores/${await storeId(a.positionals[0])}/connection`);
      const lang = a.values.language ?? "python";
      if (!c.snippets[lang]) throw new CliError("--language must be python, javascript or curl");
      if (a.values.json) return out(JSON.stringify(c, null, 2));
      err(`store ${c.store_name} (${c.store_id})\nsearch URL: ${c.search_url}\nembeddings base URL: ${c.embeddings_base_url}\nquery model: ${c.query_model}\nrequired key scope: ${c.required_scopes.join(",")} — create with: kb keys create --store ${c.store_id} --scope search\n`);
      out(c.snippets[lang]);
    } },
  "keys create": { usage: "kb keys create --store STORE [--scope search,source:read] [--name NAME]", help: "Create a restricted application key. The secret is shown once.", api: "POST /v1/api-keys", opts: { store: { type: "string", multiple: true }, scope: { type: "string" }, name: { type: "string" }, ...jsonOpt },
    run: async (a) => {
      const stores = a.values.store ? await Promise.all(a.values.store.map(storeId)) : undefined;
      const k = await api("/v1/api-keys", { method: "POST", body: { name: a.values.name ?? `cli-${new Date().toISOString().slice(0, 10)}`, scopes: String(a.values.scope ?? "search").split(","), ...(stores ? { stores } : {}) } });
      print(a, k, (k) => `key ${k.id} (${k.scopes.join(",")})\nsecret (shown once; store it in a secret manager):\n${k.secret}`);
    } },
  "keys list": { usage: "kb keys list [--json]", help: "List API keys (no secrets).", api: "GET /v1/api-keys", opts: jsonOpt, run: async (a) => print(a, await api("/v1/api-keys"), (r) => r.data.map((k: any) => `${k.id}  ${k.name}  ${k.prefix}…  ${k.scopes.join(",")}  ${k.revoked_at ? "revoked" : "active"}`).join("\n")) },
  "keys revoke": { usage: "kb keys revoke KEY_ID", help: "Revoke a key (effective immediately).", api: "DELETE /v1/api-keys/{id}", run: async (a) => { await api(`/v1/api-keys/${a.positionals[0]}`, { method: "DELETE" }); out("revoked"); } },
  "usage show": { usage: "kb usage show [--json]", help: "Storage by category and indexing/query allowances.", api: "GET /v1/usage", opts: jsonOpt,
    run: async (a) => print(a, await api("/v1/usage"), (u) => [`storage: ${fmtBytes(u.storage.total_bytes)} of ${fmtBytes(u.storage.limit_bytes)} (originals ${fmtBytes(u.storage.originals_bytes)}, vectors ${fmtBytes(u.storage.vector_bytes)}, prepared ${fmtBytes(u.storage.prepared_bytes)})`,
      `indexing: ${u.indexing.total_tokens} of ${u.indexing.limit_tokens} tokens this month`, `queries: ${u.queries.total_tokens} of ${u.queries.limit_tokens} tokens this month`, ...u.warnings.map((w: string) => `warning: ${w}`)].join("\n")) },
  "models list": { usage: "kb models list [--json]", help: "Validated model aliases.", api: "GET /v1/models", opts: jsonOpt, run: async (a) => print(a, await api("/v1/models"), (r) => r.data.map((m: any) => `${m.id}  ${m.purpose}  ${m.profile_id}`).join("\n")) },
  "uploads status": { usage: "kb uploads status SESSION_ID [--json]", help: "Inspect an upload session (received parts).", api: "GET /v1/upload-sessions/{id}", opts: jsonOpt, run: async (a) => print(a, await api(`/v1/upload-sessions/${a.positionals[0]}`), (s) => `${s.id} ${s.state} expires ${s.expires_at}\n` + s.files.map((f: any) => `  ${f.path}: ${f.parts_received.length}/${f.parts} parts`).join("\n")) },
  "uploads abandon": { usage: "kb uploads abandon SESSION_ID", help: "Abandon an open upload session.", api: "DELETE /v1/upload-sessions/{id}", run: async (a) => { await api(`/v1/upload-sessions/${a.positionals[0]}`, { method: "DELETE" }); out("abandoned"); } },
};

function wsId() {
  const w = process.env.KB_WORKSPACE ?? cfg().workspace_id;
  if (!w) throw new CliError("No workspace selected: kb workspaces use ID");
  return w;
}
function readFilter(v?: string) {
  if (!v) return undefined;
  try { return JSON.parse(v.startsWith("@") ? readFileSync(v.slice(1), "utf8") : v); } catch { throw new CliError("--filter must be JSON or @file.json"); }
}

function help(cmd?: string) {
  if (cmd && COMMANDS[cmd]) {
    const c = COMMANDS[cmd];
    return `${c.usage}\n\n${c.help}\nAPI: ${c.api}\n\nCommon: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.`;
  }
  const groups = Object.entries(COMMANDS).map(([k, c]) => `  ${c.usage.split(" | ")[0].padEnd(72)} ${c.help.split(".")[0]}`).join("\n");
  return `kb ${VERSION} — Multimodal Knowledge Store CLI\n\nUsage: kb <command> [args]   (kb help <command> for details)\n\n${groups}\n\nEnvironment: KB_BASE_URL, KB_API_KEY (scripts), KB_WORKSPACE, KB_CONFIG_DIR.`;
}

async function main(argv: string[]) {
  if (!argv.length || argv[0] === "help" || argv[0] === "--help" || argv[0] === "-h") { out(help(argv.slice(1).join(" ") || undefined)); return EXIT.ok; }
  if (argv[0] === "--version") { out(VERSION); return EXIT.ok; }
  const two = `${argv[0]} ${argv[1] ?? ""}`;
  const name = COMMANDS[two] ? two : COMMANDS[argv[0]] ? argv[0] : null;
  if (!name) throw new CliError(`Unknown command: ${argv.slice(0, 2).join(" ")}. Run kb help.`);
  const rest = argv.slice(name.split(" ").length);
  if (rest.includes("--help") || rest.includes("-h")) { out(help(name)); return EXIT.ok; }
  const a = parseArgs({ args: rest, options: COMMANDS[name].opts ?? {}, allowPositionals: true, strict: true }) as Args;
  const r = await COMMANDS[name].run(a);
  return typeof r === "number" ? r : EXIT.ok;
}

main(process.argv.slice(2)).then((c) => process.exit(c), (e) => {
  err(e instanceof CliError ? `error: ${e.message}` : `error: ${(e as Error).message}`);
  process.exit(e instanceof CliError ? e.exit : EXIT.error);
});
