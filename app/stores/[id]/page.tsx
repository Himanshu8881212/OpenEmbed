"use client";
import { AlertTriangle, ArrowUpRight, AudioLines, Blend, CheckCircle2, Clock, Download, Eye, FileText, Film, FolderUp, GitMerge, Image as ImageIcon, KeyRound, Layers, ListChecks, Loader2, Plug, RefreshCw, Search as SearchIcon, Settings2, SlidersHorizontal, Snowflake, Trash2, Upload, X } from "lucide-react";
import { use, useEffect, useMemo, useRef, useState } from "react";
import { call, fmtBytes, sha256Hex } from "@/lib/web/api";
import { accessToken } from "@/lib/web/session";
import { Code, CopyButton, Empty, ErrorBox, Loading, Meter, Modal, PageHead, Shell, StateBadge, Tabs, useApp, useLoad } from "@/lib/web/ui";

const TERMINAL = ["completed", "completed_with_errors", "failed", "cancelled"];
const EXT = [".txt", ".md", ".markdown", ".docx", ".pdf", ".jpg", ".jpeg", ".png", ".wav", ".mp3", ".mp4"];

function fmtLocation(l: any): string {
  if (!l) return "";
  const kind = l.kind === "transcript" ? "transcript · " : l.kind === "ocr" ? "OCR · " : l.kind === "soundtrack" ? "soundtrack · " : "";
  return kind + fmtPlace(l);
}
function fmtPlace(l: any): string {
  if (l.start_seconds !== undefined) { const t = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; return `${t(l.start_seconds)}–${t(l.end_seconds)}`; }
  if (l.page !== undefined) return `p. ${l.page}${l.start !== undefined ? ` · ¶ ${l.start}–${l.end}` : ""}`;
  if (l.start !== undefined) return `${l.section ? `§ ${l.section.length > 40 ? l.section.slice(0, 39) + "…" : l.section} · ` : ""}¶ ${l.start}–${l.end}`;
  return "whole image";
}
const typeIcon = (mt: string, size = 16) => mt?.startsWith("image/") ? <ImageIcon size={size} aria-hidden /> : mt?.startsWith("audio/") ? <AudioLines size={size} aria-hidden /> : mt?.startsWith("video/") ? <Film size={size} aria-hidden /> : <FileText size={size} aria-hidden />;
const locIcon = (l: any) => (l?.start_seconds !== undefined ? <Clock aria-hidden /> : <FileText aria-hidden />);

async function fetchOriginal(fileId: string, versionId?: string) {
  const tok = await accessToken();
  const r = await fetch(`/v1/files/${fileId}/content${versionId ? `?version_id=${versionId}` : ""}`, { headers: { authorization: `Bearer ${tok}`, "x-workspace-id": localStorage.getItem("kb.workspace") ?? "" } });
  if (!r.ok) throw new Error(`Could not open the original (${r.status})`);
  return r.blob();
}
async function downloadExport(store: any) {
  const tok = await accessToken();
  const r = await fetch(`/v1/stores/${store.id}/export`, { headers: { authorization: `Bearer ${tok}`, "x-workspace-id": localStorage.getItem("kb.workspace") ?? "" } });
  if (!r.ok) throw new Error(`Export failed (${r.status})`);
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: `${store.name}.jsonl` });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
async function openOriginal(fileId: string, versionId?: string) {
  const url = URL.createObjectURL(await fetchOriginal(fileId, versionId));
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
function Thumb({ fileId, versionId, large = false }: { fileId: string; versionId: string; large?: boolean }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => { let u: string | null = null; fetchOriginal(fileId, versionId).then((b) => { u = URL.createObjectURL(b); setSrc(u); }, () => {}); return () => { if (u) URL.revokeObjectURL(u); }; }, [fileId, versionId]);
  return <span className={`media-thumb ${large ? "lg" : ""}`}>{src ? <img src={src} alt="" /> : <ImageIcon size={18} aria-hidden />}</span>;
}
/** Loads the original on demand and plays the matched segment (#t=start,end). */
function MediaSegment({ r }: { r: any }) {
  const [src, setSrc] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => () => { if (src) URL.revokeObjectURL(src); }, [src]);
  const loc = r.source.location;
  const t = loc?.start_seconds !== undefined ? `#t=${loc.start_seconds},${loc.end_seconds}` : "";
  if (!src) return (
    <span className="media">
      <span className="media-thumb">{typeIcon(r.source.media_type, 20)}</span>
      <button className="btn sm" onClick={() => fetchOriginal(r.source.file_id, r.source.version_id).then((b) => setSrc(URL.createObjectURL(b)), (e) => setErr(e.message))}>Play {r.content.type} segment<span className="sr"> {fmtLocation(loc)} of {r.source.filename}</span></button>
      <span className="muted small">{fmtLocation(loc)}</span>{err && <span className="badge bad">{err}</span>}
    </span>
  );
  return r.content.type === "video"
    ? <video className="media-player" controls autoPlay muted src={src + t} aria-label={`${r.source.filename} ${fmtLocation(loc)}`} />
    : <audio controls autoPlay src={src + t} aria-label={`${r.source.filename} ${fmtLocation(loc)}`} />;
}

function Highlight({ text, q }: { text: string; q: string }) {
  const words = q.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  if (!words.length) return <>{text}</>;
  return <>{text.split(new RegExp(`(\\b(?:${words.join("|")})\\w*)`, "gi")).map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : p))}</>;
}

// ---------------------------------------------------------------- search
function Search({ store }: { store: any }) {
  const [res, setRes] = useState<any>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [media, setMedia] = useState<File | null>(null);
  const [limit, setLimit] = useState(8);
  const [fmt, setFmt] = useState<"all" | "text" | "image" | "video" | "audio">("all");
  const mediaRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const searched = useRef(false);
  useEffect(() => { if (searched.current) formRef.current?.requestSubmit(); }, [fmt]); // re-run with the chosen format
  async function run(e?: React.FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    searched.current = true;
    const d = e ? new FormData(e.currentTarget) : new FormData();
    setBusy(true); setError(null);
    try {
      const query: any = {};
      if (q.trim()) query.text = q;
      let asset: string | null = null;
      if (media) { asset = (await call("POST", "/v1/query-assets", undefined, { raw: media, headers: { "content-type": media.type } })).id; query.asset_id = asset; }
      if (!query.text && !asset) { setBusy(false); return; }
      const filter: any = {};
      if (d.get("fk") && d.get("fv")) filter.metadata = { [String(d.get("fk"))]: String(d.get("fv")) };
      if (d.get("prefix")) filter.path_prefix = String(d.get("prefix"));
      const shape = fmt === "all" ? { balance: true } : { modalities: [fmt] };
      setRes({ ...(await call("POST", `/v1/stores/${store.id}/search`, { query, limit, ...shape, ...(Object.keys(filter).length ? { filter } : {}) })), q });
      if (asset) call("DELETE", `/v1/query-assets/${asset}`).catch(() => {});
    } catch (err) { setError(err); setRes(null); } finally { setBusy(false); }
  }
  const top = res?.results?.[0]?.score ?? 1;
  return (
    <section aria-label="Search">
      <form onSubmit={run} ref={formRef}>
        <div className="ask">
          <SearchIcon aria-hidden />
          <label className="sr" htmlFor="q">Question or keywords</label>
          <input id="q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Ask ${store.name} anything, e.g. “How do I replace the pressure sensor?”`} autoComplete="off" />
          <button className="btn primary" disabled={busy}>{busy ? <Loader2 className="spin" aria-hidden /> : null}{busy ? "Searching…" : "Search"}</button>
        </div>
        <div className="ask-tools">
          <span role="group" aria-label="Formats" className="row" style={{ gap: 6 }}>
            {([["all", "All formats"], ["text", "Text"], ["image", "Images"], ["video", "Video"], ["audio", "Audio"]] as const).map(([k, l]) => (
              <button key={k} type="button" className="chip" aria-pressed={fmt === k} onClick={() => setFmt(k)}>{l}</button>
            ))}
          </span>
          <span aria-hidden style={{ width: 1, height: 20, background: "var(--rule-2)" }} />
          <button type="button" className="chip" aria-pressed={showFilters} onClick={() => setShowFilters((x) => !x)}><SlidersHorizontal aria-hidden />Filters</button>
          <span className="file-picker">
            <input ref={mediaRef} type="file" aria-label="Image, audio or video query" accept="image/png,image/jpeg,audio/wav,audio/mpeg,video/mp4" onChange={(e) => setMedia(e.target.files?.[0] ?? null)} />
            <span className={`chip ${media ? "on" : ""}`}><ImageIcon aria-hidden />{media ? media.name : "Search with media"}</span>
          </span>
          {media && <button type="button" className="chip" onClick={() => { setMedia(null); if (mediaRef.current) mediaRef.current.value = ""; }} aria-label="Remove media query"><X aria-hidden />Clear</button>}
          <label className="chip" style={{ cursor: "default" }}>Results
            <select aria-label="Results" value={limit} onChange={(e) => setLimit(Number(e.target.value))} style={{ border: 0, background: "transparent", font: "inherit", color: "inherit" }}>{[8, 12, 20].map((n) => <option key={n}>{n}</option>)}</select>
          </label>
        </div>
        {showFilters && (
          <div className="filters row reveal">
            <label className="field grow">Metadata key<input name="fk" placeholder="department" /></label>
            <label className="field grow">Metadata value<input name="fv" placeholder="service" /></label>
            <label className="field grow">Path starts with<input name="prefix" placeholder="manuals/" /></label>
          </div>
        )}
      </form>
      <ErrorBox error={error} />
      <div aria-live="polite">
        {!res && !busy && (
          <div style={{ marginTop: 28 }}>
            <Empty icon={<SearchIcon />} title="Ask in your own words">Results come from {store.name}’s active index. Each one links to the exact file, page, passage or time range it came from.</Empty>
          </div>
        )}
        {res && (res.results.length === 0 ? (
          <div style={{ marginTop: 24 }}><Empty icon={<SearchIcon />} title="No matching evidence">Check that imports have finished, loosen the filters, or confirm you can access this material.</Empty></div>
        ) : (
          <>
            <div className="result-meta">
              <strong style={{ color: "var(--text)" }}>{res.results.length} results</strong>
              <span>·</span><span className="mono">{res.profile_id}</span>
              <span className="badge" title={`index ${res.index_revision} · request ${res.request_id}`}>ref {res.request_id.slice(4, 12)}</span>
              {res.ranking === "balanced" && <span className="badge" title="Best matches of each format, interleaved">balanced across formats</span>}
              <span style={{ marginLeft: "auto" }}>Relevance ranks results within a format. It is not answer confidence.</span>
            </div>
            <ol className="results">{res.results.map((r: any) => (
              <li key={r.segment_id} className="result">
                <h3>{typeIcon(r.source.media_type, 15)}{r.source.path} <span className="ver">v{r.source.version_no}</span><span className="cite">{locIcon(r.source.location)}{fmtLocation(r.source.location)}</span>{r.match?.keyword_rank && <span className="badge ok" title="Contains the exact identifier from your query">exact match</span>}</h3>
                {typeof r.content === "string" ? <><p className="passage"><Highlight text={r.content} q={res.q ?? ""} /></p>
                  {r.source.location?.start_seconds !== undefined && /^(audio|video)\//.test(r.source.media_type) && <div className="media"><MediaSegment r={{ ...r, content: { type: r.source.media_type.split("/")[0] } }} /></div>}</>
                  : r.content.type === "image" ? <div className="media"><Thumb fileId={r.source.file_id} versionId={r.source.version_id} large /><span className="muted small">image · {fmtLocation(r.source.location)}</span></div>
                  : <div className="media"><MediaSegment r={r} /></div>}
                <div className="result-foot">
                  <span className="relevance"><Meter value={r.score} max={Math.max(top, 0.0001)} tone="accent" label={`Relevance ${r.score.toFixed(3)}`} />relevance {r.score.toFixed(3)}</span>
                  <button className="btn sm" onClick={() => openOriginal(r.source.file_id, r.source.version_id).catch(setError)}><ArrowUpRight aria-hidden />Open original<span className="sr"> of {r.source.filename}</span></button>
                </div>
              </li>
            ))}</ol>
          </>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- import
type Planned = { file: File; path: string };
async function entriesToFiles(items: DataTransferItemList): Promise<Planned[]> {
  const out: Planned[] = [];
  const walk = async (entry: any, prefix: string): Promise<void> => {
    if (entry.isFile) { const f: File = await new Promise((r, j) => entry.file(r, j)); out.push({ file: f, path: prefix + f.name }); return; }
    const reader = entry.createReader();
    for (;;) { const batch: any[] = await new Promise((r, j) => reader.readEntries(r, j)); if (!batch.length) break; for (const e of batch) await walk(e, `${prefix}${entry.name}/`); }
  };
  const roots = Array.from(items).map((i) => i.webkitGetAsEntry?.()).filter(Boolean);
  for (const r of roots) await walk(r, "");
  // a single dropped folder: paths are relative to it (as with the folder picker)
  if (roots.length === 1 && (roots[0] as any).isDirectory) for (const p of out) p.path = p.path.split("/").slice(1).join("/");
  return out;
}

function Import({ store, onJob }: { store: any; onJob: (id: string) => void }) {
  const { toast, reloadStores } = useApp();
  const [plan, setPlan] = useState<{ files: Planned[]; ignored: { path: string; reason: string }[] } | null>(null);
  const [status, setStatus] = useState<Record<string, string>>({});
  const [progress, setProgress] = useState<{ done: number; total: number; phase: string } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [over, setOver] = useState(false);
  const [maxBytes, setMaxBytes] = useState(512 * 1024 * 1024);
  useEffect(() => { call("GET", "/v1/embedding-profiles").then((p) => setMaxBytes(p.limits.max_file_bytes), () => {}); }, []);
  const key = `kb.upload.${store.id}`;

  function choose(list: Planned[]) {
    const files: Planned[] = [], ignored: { path: string; reason: string }[] = [];
    for (const { file: f, path } of list) {
      const ext = (/\.[^.]+$/.exec(f.name.toLowerCase()) ?? [""])[0];
      if (path.split("/").some((s) => s.startsWith("."))) ignored.push({ path, reason: "hidden" });
      else if (!EXT.includes(ext)) ignored.push({ path, reason: "unsupported format" });
      else if (f.size === 0) ignored.push({ path, reason: "empty file" });
      else if (f.size > maxBytes) ignored.push({ path, reason: `larger than ${fmtBytes(maxBytes)}` });
      else files.push({ file: f, path });
    }
    setPlan({ files, ignored }); setStatus({}); setError(null);
  }
  const fromInput = (l: FileList | null) => l && choose(Array.from(l).map((f) => ({ file: f, path: (f.webkitRelativePath || f.name).split("/").slice(f.webkitRelativePath ? 1 : 0).join("/") })));

  async function start() {
    if (!plan) return;
    setError(null);
    try {
      setProgress({ done: 0, total: plan.files.length, phase: "Checking files" });
      const manifest: { path: string; size: number; sha256: string }[] = [];
      for (const [i, p] of plan.files.entries()) { manifest.push({ path: p.path, size: p.file.size, sha256: await sha256Hex(p.file) }); setProgress({ done: i + 1, total: plan.files.length, phase: "Checking files" }); }
      let session: any = null;
      const saved = localStorage.getItem(key);
      if (saved) {
        const s = await call("GET", `/v1/upload-sessions/${saved}`).catch(() => null);
        if (s && s.state === "open" && s.files.length === manifest.length && s.files.every((f: any) => manifest.some((m) => m.path === f.path && m.sha256 === f.sha256))) { session = s; toast("Resuming your previous upload"); }
      }
      session ??= await call("POST", "/v1/upload-sessions", { store_id: store.id, files: manifest });
      localStorage.setItem(key, session.id);
      const parts: { f: any; n: number; file: File }[] = [];
      const remaining: Record<string, number> = {};
      for (const f of session.files) {
        const local = plan.files.find((p) => p.path === f.path)!.file;
        for (let n = 1; n <= f.parts; n++) if (!f.parts_received.includes(n)) { parts.push({ f, n, file: local }); remaining[f.path] = (remaining[f.path] ?? 0) + 1; }
        setStatus((s) => ({ ...s, [f.path]: remaining[f.path] ? "uploading" : "uploaded" }));
      }
      let done = 0;
      const total = parts.length;
      setProgress({ done, total, phase: "Uploading" });
      const worker = async () => { for (let t; (t = parts.shift()); ) {
        const blob = t.file.slice((t.n - 1) * session.part_bytes, t.n * session.part_bytes);
        await call("PUT", `/v1/upload-sessions/${session.id}/files/${t.f.id}/parts/${t.n}`, undefined, { raw: blob, headers: { "content-type": "application/octet-stream", "x-part-sha256": await sha256Hex(blob) } });
        if (--remaining[t.f.path] === 0) setStatus((s) => ({ ...s, [t.f.path]: "uploaded" }));
        setProgress({ done: ++done, total, phase: "Uploading" });
      } };
      await Promise.all([worker(), worker(), worker()]);
      const r = await call("POST", `/v1/upload-sessions/${session.id}/commit`, {}, { headers: { "idempotency-key": `commit-${session.id}` } });
      localStorage.removeItem(key);
      setProgress(null); setPlan(null);
      toast(`Upload complete. Indexing ${plan.files.length} file(s)`);
      reloadStores();
      onJob(r.job_id);
    } catch (e) { setError(e); setProgress(null); }
  }
  const step = progress ? 2 : plan ? 1 : 0;
  return (
    <section aria-label="Import">
      <ol className="steps" aria-label="Import steps">
        {["Choose a folder", "Review", "Upload", "Index"].map((s, i) => <li key={s} className={i < step ? "done" : i === step ? "on" : ""} aria-current={i === step ? "step" : undefined}>{s}</li>)}
      </ol>
      {!plan && (
        <div className={`drop ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={async (e) => { e.preventDefault(); setOver(false); choose(await entriesToFiles(e.dataTransfer.items)); }}>
          <div>
            <div className="glyph" aria-hidden><FolderUp /></div>
            <h3>Drop a folder here</h3>
            <p>Files upload straight from this browser. The service never reads paths on your computer.<br />Text, Markdown, Word (.docx), PDF, JPEG/PNG, WAV/MP3 and MP4, up to {fmtBytes(maxBytes)} each.</p>
            <span className="file-picker">
              <input type="file" multiple aria-label="Folder to import" onChange={(e) => fromInput(e.target.files)} ref={(el) => { if (el) el.setAttribute("webkitdirectory", ""); }} />
              <span className="btn primary"><FolderUp aria-hidden />Choose folder</span>
            </span>
          </div>
        </div>
      )}
      {plan && (
        <div className="card pad reveal">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h2 className="display" style={{ fontSize: 22, fontWeight: 500 }}>{plan.files.length} file(s) to upload</h2>
              <p className="muted" style={{ margin: "4px 0 0" }}>{fmtBytes(plan.files.reduce((a, p) => a + p.file.size, 0))} · {plan.ignored.length} ignored · interrupted uploads resume when you choose the same folder again</p>
            </div>
            <div className="row">
              {!progress && <button className="btn ghost" onClick={() => setPlan(null)}>Choose another folder</button>}
              <button className="btn primary" onClick={start} disabled={!plan.files.length || !!progress}><Upload aria-hidden />Upload and index {plan.files.length} file(s)</button>
            </div>
          </div>
          {progress && (
            <div role="status" aria-live="polite" style={{ margin: "18px 0 4px" }}>
              <div className="row small" style={{ justifyContent: "space-between" }}><span>{progress.phase}</span><span className="num">{progress.done} of {progress.total}</span></div>
              <div style={{ marginTop: 6 }}><Meter value={progress.done} max={progress.total || 1} tone="accent" label={progress.phase} /></div>
            </div>
          )}
          <ul className="upload-list" style={{ marginTop: 14 }}>
            {plan.files.map((p) => (
              <li key={p.path}>{typeIcon(p.file.type)}<span>{p.path} <span className="muted small">· {fmtBytes(p.file.size)}</span></span>
                <span>{status[p.path] === "uploaded" ? <span className="badge ok"><CheckCircle2 aria-hidden />uploaded</span> : status[p.path] === "uploading" ? <span className="badge busy">uploading</span> : <span className="badge">ready</span>}</span></li>
            ))}
          </ul>
          {plan.ignored.length > 0 && <details style={{ marginTop: 12 }}><summary className="muted small" style={{ cursor: "pointer" }}>Ignored files ({plan.ignored.length})</summary><ul className="upload-list">{plan.ignored.map((i) => <li key={i.path}><AlertTriangle aria-hidden /><span>{i.path} — {i.reason}</span><span /></li>)}</ul></details>}
        </div>
      )}
      <ErrorBox error={error} />
    </section>
  );
}

// ---------------------------------------------------------------- jobs
const KIND_ICON: Record<string, React.ReactNode> = { ingest: <Upload aria-hidden />, revision: <RefreshCw aria-hidden />, merge: <GitMerge aria-hidden />, reindex: <Layers aria-hidden />, connector_sync: <Plug aria-hidden />, store_delete: <Trash2 aria-hidden />, file_delete: <Trash2 aria-hidden /> };
const KIND_LABEL: Record<string, string> = { ingest: "Import", revision: "Replacement", merge: "Merge", reindex: "Index build", connector_sync: "Scheduled sync", store_delete: "Store deletion", file_delete: "Source deletion" };
const ago = (d: string) => { const s = (Date.now() - new Date(d).getTime()) / 1000; return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : new Date(d).toLocaleDateString(); };

function Jobs({ store, focus }: { store: any; focus: string | null }) {
  const { toast, reloadStores } = useApp();
  const jobs = useLoad(() => call("GET", `/v1/jobs?store_id=${store.id}&limit=50`), [store.id, focus]);
  const [sel, setSel] = useState<string | null>(focus);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => setSel(focus), [focus]);
  const job = useLoad(() => (sel ? call("GET", `/v1/jobs/${sel}`) : Promise.resolve(null)), [sel]);
  const items = useLoad(() => (sel ? call("GET", `/v1/jobs/${sel}/items?limit=200`) : Promise.resolve(null)), [sel, job.data?.state, job.data?.items?.succeeded]);
  const live = (jobs.data?.data ?? []).some((j: any) => !TERMINAL.includes(j.state)) || (job.data && !TERMINAL.includes(job.data.state));
  useEffect(() => {
    if (!live) return;
    const t = setTimeout(() => { job.reload(); jobs.reload(); }, 1500);
    return () => clearTimeout(t);
  });
  const wasLive = useRef(false);
  useEffect(() => { if (job.data && TERMINAL.includes(job.data.state) && wasLive.current) { toast(`${KIND_LABEL[job.data.kind] ?? "Job"} ${job.data.state.replaceAll("_", " ")}`, job.data.state === "completed" ? "ok" : "bad"); reloadStores(); } wasLive.current = !!job.data && !TERMINAL.includes(job.data.state); }, [job.data?.state]); // eslint-disable-line
  const act = async (path: string, msg: string) => { try { const r = await call("POST", path, {}, { headers: { "idempotency-key": crypto.randomUUID() } }); setSel(r.job_id ?? r.id); setError(null); jobs.reload(); toast(msg); } catch (e) { setError(e); } };
  return (
    <section aria-label="Jobs">
      <ErrorBox error={error ?? jobs.error} />
      {sel && job.data && (
        <div className="card pad reveal" aria-live="polite" style={{ marginBottom: 16 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ display: "flex", gap: 10, alignItems: "center" }}><span className="job-icon">{KIND_ICON[job.data.kind]}</span>{KIND_LABEL[job.data.kind] ?? job.data.kind} <span className="mono muted small">{job.data.id.slice(0, 8)}</span> <StateBadge state={job.data.state} /></h2>
            <div className="row">
              {!TERMINAL.includes(job.data.state) && <button className="btn" onClick={() => act(`/v1/jobs/${sel}/cancel`, "Cancellation requested")}>Cancel job</button>}
              {TERMINAL.includes(job.data.state) && job.data.items.retryable > 0 && <button className="btn primary" onClick={() => act(`/v1/jobs/${sel}/retry`, "Retry started")}><RefreshCw aria-hidden />Retry {job.data.items.retryable} failed item(s)</button>}
            </div>
          </div>
          <p className="muted" style={{ margin: "10px 0 6px" }}>{job.data.items.succeeded} of {job.data.items.total} items succeeded, {job.data.items.failed} failed, {job.data.items.cancelled} cancelled</p>
          <Meter value={job.data.items.succeeded + job.data.items.failed + job.data.items.cancelled} max={job.data.items.total || 1} tone={job.data.items.failed ? "warn" : "accent"} label="Job progress" />
          {job.data.result && <p className="muted small mono" style={{ marginTop: 10 }}>{Object.entries(job.data.result).filter(([, v]) => typeof v !== "object").map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" · ")}</p>}
          {items.data && items.data.data.some((i: any) => i.error) && (
            <div className="table-wrap" style={{ marginTop: 14 }}>
              <table className="t"><caption>Failed items</caption><thead><tr><th scope="col">File</th><th scope="col">Problem</th><th scope="col">What to do</th></tr></thead>
                <tbody>{items.data.data.filter((i: any) => i.error).map((i: any) => <tr key={i.id}><td>{i.path}</td><td><span className="badge bad">{i.error.code}</span> {i.error.message}</td><td className="small">{i.retryable ? "Retry the job" : "Correct the file and upload it again"}</td></tr>)}</tbody></table>
            </div>
          )}
        </div>
      )}
      {!jobs.data ? <Loading what="Loading jobs" /> : jobs.data.data.length === 0 ? <Empty icon={<ListChecks />} title="No jobs yet">Imports, replacements and index builds appear here with live progress.</Empty> : (
        <div className="card">
          {jobs.data.data.map((j: any) => (
            <div key={j.id} className={`job ${sel === j.id ? "sel" : ""}`}>
              <span className="job-icon">{KIND_ICON[j.kind]}</span>
              <div>
                <div className="title"><button className="cell-btn" onClick={() => setSel(j.id)} aria-label={`Show job ${j.id.slice(0, 8)}`}>{KIND_LABEL[j.kind] ?? j.kind}</button><StateBadge state={j.state} /></div>
                <div className="sub">{j.items.succeeded}/{j.items.total} items · {ago(j.created_at)} · <span className="mono">{j.id.slice(0, 8)}</span></div>
                {!TERMINAL.includes(j.state) && j.items.total > 0 && <Meter value={j.items.succeeded + j.items.failed} max={j.items.total} tone="accent" label={`Progress of ${j.id.slice(0, 8)}`} />}
              </div>
              <button className="btn sm ghost" onClick={() => setSel(j.id)} tabIndex={-1} aria-hidden>Details</button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- files
function FileDrawer({ fileId, store, onClose, onJob, onChanged }: { fileId: string | null; store: any; onClose: () => void; onJob: (id: string) => void; onChanged: () => void }) {
  const { toast } = useApp();
  const file = useLoad(() => (fileId ? call("GET", `/v1/files/${fileId}`) : Promise.resolve(null)), [fileId]);
  const segs = useLoad(() => (fileId ? call("GET", `/v1/files/${fileId}/segments?limit=50`) : Promise.resolve(null)), [fileId, file.data?.current_version?.id]);
  const [error, setError] = useState<unknown>(null);
  const [confirm, setConfirm] = useState<any>(null);
  const act = async (f: () => Promise<any>, msg?: string) => { try { const r = await f(); setError(null); file.reload(); onChanged(); if (msg) toast(msg); return r; } catch (e) { setError(e); } };
  async function replace(input: HTMLInputElement) {
    const f = input.files?.[0];
    if (!f || !file.data) return;
    await act(async () => {
      const s = await call("POST", "/v1/upload-sessions", { files: [{ path: file.data.path.replace(/[^/]+$/, f.name), size: f.size, sha256: await sha256Hex(f), replaces_file_id: file.data.id }] });
      for (let n = 1; n <= s.files[0].parts; n++) { const b = f.slice((n - 1) * s.part_bytes, n * s.part_bytes); await call("PUT", `/v1/upload-sessions/${s.id}/files/${s.files[0].id}/parts/${n}`, undefined, { raw: b }); }
      await call("POST", `/v1/upload-sessions/${s.id}/commit`, {});
      const r = await call("POST", `/v1/files/${file.data.id}/revisions`, { upload_session_id: s.id });
      onClose(); onJob(r.job_id);
    }, "Replacement uploaded. The new version publishes when indexing finishes");
  }
  const d = file.data;
  return (
    <Modal drawer open={!!fileId} onClose={onClose} title={d?.path ?? "Source"} subtitle={d && <>{d.path} — {d.status}</>}>
      <ErrorBox error={error ?? file.error} />
      {!d ? <Loading /> : (
        <div className="stack" style={{ gap: 22 }}>
          {d.last_error && <div className="alert" role="alert"><AlertTriangle aria-hidden /><div>Last error: {d.last_error.code}: {d.last_error.message}</div></div>}
          {d.current_version && (
            <dl className="kv">
              <div><dt>Version</dt><dd>v{d.current_version.version_no} · {d.current_version.media_type}</dd></div>
              <div><dt>Size</dt><dd>{fmtBytes(d.current_version.size)}</dd></div>
              <div><dt>Segments</dt><dd>{d.segment_count}</dd></div>
              <div><dt>In stores</dt><dd>{d.stores.map((s: any) => s.name).join(", ")}</dd></div>
              <div><dt>SHA-256</dt><dd>{d.current_version.sha256.slice(0, 16)}…<CopyButton text={d.current_version.sha256} label="Copy checksum" className="btn sm ghost icon" /></dd></div>
            </dl>
          )}
          <div>
            <h3 style={{ marginBottom: 8 }}>Metadata</h3>
            <div className="row" style={{ gap: 6, marginBottom: 10 }}>
              {Object.entries(d.metadata).length === 0 && <span className="muted small">No metadata yet. Tags power filters and live views.</span>}
              {Object.entries(d.metadata).map(([k, v]) => <span key={k} className="badge" style={{ height: 26 }}>{k} = {String(v)}<button className="btn ghost icon" style={{ width: 18, height: 18 }} onClick={() => act(() => call("PATCH", `/v1/files/${fileId}`, { metadata: { [k]: null } }), `Removed ${k}`)} aria-label={`Remove ${k}`}><X size={12} aria-hidden /></button></span>)}
            </div>
            <form className="row" onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); const f = e.currentTarget; act(() => call("PATCH", `/v1/files/${fileId}`, { metadata: { [String(fd.get("k"))]: String(fd.get("v")) } }), "Metadata saved").then(() => f.reset()); }}>
              <label className="field grow">Key<input name="k" required /></label><label className="field grow">Value<input name="v" required /></label><button className="btn">Set metadata</button>
            </form>
          </div>
          <div className="row">
            <button className="btn" onClick={() => openOriginal(fileId!).catch(setError)}><Download aria-hidden />Open original</button>
            <span className="file-picker"><input type="file" aria-label="Replace with a new version" onChange={(e) => replace(e.currentTarget)} /><span className="btn"><RefreshCw aria-hidden />Replace with new version</span></span>
          </div>
          {segs.data && (
            <div>
              <h3 style={{ marginBottom: 8 }}>Segments <span className="muted small">({segs.data.data.length}{segs.data.next_cursor ? "+" : ""})</span></h3>
              <ol className="stack" style={{ gap: 8, listStyle: "none", padding: 0, margin: 0 }}>
                {segs.data.data.map((s: any) => <li key={s.id} className="card" style={{ padding: "10px 12px" }}><span className="cite">{fmtLocation(s.location)}</span> <span className="muted small">{s.modality} · {s.token_count} tokens</span>{s.content && <p className="small" style={{ margin: "6px 0 0" }}>{s.content.slice(0, 220)}{s.content.length > 220 ? "…" : ""}</p>}</li>)}
              </ol>
            </div>
          )}
          <div className="card pad" style={{ borderColor: "color-mix(in srgb, var(--bad) 30%, transparent)" }}>
            <h3 style={{ color: "var(--bad)" }}>Danger zone</h3>
            <p className="muted small">Removing affects only this store. Deleting removes the source everywhere, including snapshots.</p>
            <div className="row">
              {store.kind !== "view" && <button className="btn" onClick={() => act(() => call("DELETE", `/v1/stores/${store.id}/files/${fileId}`), "Removed from this store").then(onClose)}>Remove from this store</button>}
              <button className="btn danger" onClick={() => act(() => call("POST", `/v1/files/${fileId}/deletion-previews`, {})).then((p) => p && setConfirm(p))}><Trash2 aria-hidden />Delete everywhere…</button>
            </div>
            {confirm && (
              <div className="callout" role="alertdialog" aria-label="Confirm deletion" style={{ marginTop: 12 }}>
                <p style={{ marginTop: 0 }}><strong>{confirm.path}</strong> is in {confirm.stores.length} store(s), {confirm.snapshots.length} snapshot(s) and {confirm.live_views.length} live view(s). It becomes inaccessible immediately. Physical removal follows the retention policy.</p>
                <div className="row"><button className="btn danger-solid" onClick={async () => { const r = await act(() => call("DELETE", `/v1/files/${confirm.file_id}?scope=workspace`), "Source deleted everywhere"); setConfirm(null); onClose(); if (r) onJob(r.job_id); }}>Delete everywhere</button><button className="btn ghost" onClick={() => setConfirm(null)}>Keep it</button></div>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

function Files({ store, onJob }: { store: any; onJob: (id: string) => void }) {
  const files = useLoad(() => call("GET", `/v1/stores/${store.id}/files?limit=200`), [store.id]);
  const [sel, setSel] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const rows = (files.data?.data ?? []).filter((f: any) => f.path.toLowerCase().includes(filter.toLowerCase()));
  return (
    <section aria-label="Files">
      <ErrorBox error={files.error} />
      <FileDrawer fileId={sel} store={store} onClose={() => setSel(null)} onJob={onJob} onChanged={files.reload} />
      {!files.data ? <Loading what="Loading files" rows={5} /> : files.data.data.length === 0 ? <Empty icon={<FileText />} title="No files in this store yet">Use Import to add a folder. Each file is checked, split into segments and indexed.</Empty> : (
        <>
          <div className="row" style={{ marginBottom: 12, justifyContent: "space-between" }}>
            <label className="field" style={{ minWidth: 260 }}><span className="sr">Filter files</span><input placeholder="Filter by path…" value={filter} onChange={(e) => setFilter(e.target.value)} /></label>
            <span className="muted small">{rows.length} of {files.data.data.length} sources</span>
          </div>
          <div className="table-wrap">
            <table className="t"><thead><tr><th scope="col">Source</th><th scope="col">Version</th><th scope="col">Type</th><th scope="col" className="num">Size</th><th scope="col" className="num">Segments</th></tr></thead>
              <tbody>{rows.map((f: any) => (
                <tr key={f.id}>
                  <td><button className="cell-btn" onClick={() => setSel(f.id)} aria-label={`Inspect ${f.path}`}>{typeIcon(f.version.media_type)}{f.path}</button>{Object.keys(f.metadata).length > 0 && <span className="muted small"> · {Object.entries(f.metadata).map(([k, v]) => `${k}=${v}`).join(", ")}</span>}</td>
                  <td><span className="mono small">v{f.version.version_no}</span></td><td className="muted small">{f.version.media_type}</td><td className="num">{fmtBytes(f.version.size)}</td><td className="num">{f.segment_count}</td>
                </tr>
              ))}</tbody></table>
          </div>
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- composition
function Connectors({ store, onJob }: { store: any; onJob: (id: string) => void }) {
  const list = useLoad(() => call("GET", "/v1/connectors"));
  const [error, setError] = useState<unknown>(null);
  const act = async (f: () => Promise<any>) => { try { const r = await f(); setError(null); list.reload(); if (r?.job_id) onJob(r.job_id); } catch (e) { setError(e); } };
  const mine = list.data?.data.filter((c: any) => c.store_id === store.id) ?? [];
  return (
    <div className="card pad">
      <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><Plug size={17} aria-hidden />Scheduled sync</h2>
      <p className="muted small">Mirror a JSON manifest (<code>{'{"files":[{"path","url"}]}'}</code>) from an allowlisted host. New and changed files import automatically. Removed files leave the store.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", "/v1/connectors", { store_id: store.id, type: "http_manifest", url: d.get("url"), interval_minutes: Number(d.get("interval")) })); }}>
        <label className="field grow">Manifest URL<input name="url" type="url" required placeholder="https://docs.example.com/manifest.json" /></label>
        <label className="field" style={{ width: 130 }}>Every (minutes)<input name="interval" type="number" min={5} defaultValue={60} required /></label>
        <button className="btn">Add connector</button>
      </form>
      <ErrorBox error={error ?? list.error} />
      {mine.length > 0 && <div className="table-wrap" style={{ marginTop: 12 }}><table className="t"><thead><tr><th scope="col">Manifest</th><th scope="col">Interval</th><th scope="col">Next run</th><th scope="col"><span className="sr">Actions</span></th></tr></thead>
        <tbody>{mine.map((c: any) => <tr key={c.id}><td className="mono small">{c.url}</td><td>{c.interval_minutes} min</td><td className="small">{new Date(c.next_run_at).toLocaleString()}</td>
          <td><div className="row" style={{ justifyContent: "flex-end" }}><button className="btn sm" onClick={() => act(() => call("POST", `/v1/connectors/${c.id}/syncs`, {}))}>Sync now<span className="sr"> {c.url}</span></button><button className="btn sm danger" onClick={() => act(() => call("DELETE", `/v1/connectors/${c.id}`))} aria-label={`Remove connector ${c.url}`}><Trash2 aria-hidden /></button></div></td></tr>)}</tbody></table></div>}
    </div>
  );
}

function Compose({ store, onJob, reload }: { store: any; onJob: (id: string) => void; reload: () => void }) {
  const { stores, reloadStores, toast } = useApp();
  const stats = useLoad(() => call("GET", `/v1/stores/${store.id}/stats`), [store.id, store.index_revision]);
  const profiles = useLoad(() => call("GET", "/v1/embedding-profiles"));
  const sub = useLoad(() => call("GET", "/v1/subscription"));
  const customChunking = !!sub.data?.plan?.features?.custom_profiles;
  const [mode, setMode] = useState<"view" | "snapshot">("view");
  const [error, setError] = useState<unknown>(null);
  const act = async (f: () => Promise<any>, ok: (r: any) => string) => { try { const r = await f(); toast(ok(r)); setError(null); if (r?.job_id) onJob(r.job_id); stats.reload(); reload(); reloadStores(); } catch (e) { setError(e); } };
  return (
    <section aria-label="Composition" className="stack" style={{ gap: 16 }}>
      <ErrorBox error={error} />
      <p className="muted" style={{ margin: 0 }}>Build new stores from this one without re-uploading or re-embedding. Derived stores reuse the existing vectors and get their own ID, search and connection.</p>
      <div className="card pad">
        <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><Blend size={17} aria-hidden />Derive a store</h2>
        <div role="radiogroup" aria-label="Type" className="tabs pills" style={{ marginTop: 12 }}>
          <button type="button" role="radio" aria-checked={mode === "view"} className="chip" style={{ border: 0 }} onClick={() => setMode("view")}><Eye aria-hidden />Live view</button>
          <button type="button" role="radio" aria-checked={mode === "snapshot"} className="chip" style={{ border: 0 }} onClick={() => setMode("snapshot")}><Snowflake aria-hidden />Snapshot</button>
        </div>
        <p className="muted small" style={{ marginTop: 0 }}>{mode === "view" ? "Follows this store: new files, tag changes, new versions and deletions flow through automatically." : "Freezes the matching files at their current versions. Later changes here do not alter it."}</p>
        <form className="row" onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", `/v1/stores/${store.id}/derivations`, { name: d.get("name"), mode, ...(d.get("fk") || d.get("prefix") ? { filter: { ...(d.get("fk") ? { metadata: { [String(d.get("fk"))]: String(d.get("fv")) } } : {}), ...(d.get("prefix") ? { path_prefix: String(d.get("prefix")) } : {}) } } : {}) }), (s) => `Created ${s.kind} ${s.name}`); }}>
          <label className="field grow">New store name<input name="name" required placeholder={`${store.name}-service`} /></label>
          <label className="field">Metadata key<input name="fk" placeholder="department" /></label>
          <label className="field">Metadata value<input name="fv" placeholder="service" /></label>
          <label className="field">Path starts with<input name="prefix" placeholder="manuals/" /></label>
          <button className="btn primary">Create {mode === "view" ? "live view" : "snapshot"}</button>
        </form>
      </div>
      <div className="card pad">
        <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><Layers size={17} aria-hidden />Split by field</h2>
        <p className="muted small">One click, many stores: creates a live view (or snapshot) for every value of a metadata field, e.g. one store per <code>department</code>.</p>
        <form className="row" onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", `/v1/stores/${store.id}/splits`, { field: d.get("field"), mode: d.get("smode"), ...(d.get("sprefix") ? { prefix: d.get("sprefix") } : {}) }), (r) => `Created ${r.created.length} store(s)${r.skipped.length ? `, skipped ${r.skipped.length}` : ""}`); }}>
          <label className="field grow">Metadata field<input name="field" required placeholder="department" /></label>
          <label className="field">Each as<select name="smode"><option value="view">Live view</option><option value="snapshot">Snapshot</option></select></label>
          <label className="field">Name prefix<input name="sprefix" placeholder={store.name} /></label>
          <button className="btn">Split</button>
        </form>
      </div>
      <div className="card pad">
        <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><GitMerge size={17} aria-hidden />Merge into a new store</h2>
        <p className="muted small">Combines compatible stores. Duplicate sources are removed and existing vectors are reused.</p>
        <form className="row" onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", "/v1/store-merges", { sources: [store.id, ...d.getAll("other")], target_name: d.get("target") }), (r) => `Merge started into ${String(d.get("target"))}`); }}>
          <label className="field grow">Other stores<select name="other" multiple size={3} style={{ height: "auto", padding: 6 }}>{stores?.filter((s: any) => s.id !== store.id).map((s: any) => <option key={s.id} value={s.id}>{s.name} ({s.profile_id})</option>)}</select></label>
          <label className="field grow">Target store name<input name="target" required /></label>
          <button className="btn">Merge</button>
        </form>
      </div>
      {store.kind === "material" && <Connectors store={store} onJob={onJob} />}
      <div className="card pad">
        <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><Layers size={17} aria-hidden />Index revisions</h2>
        <p className="muted small">Build an index with another profile alongside the active one, check it, then activate it. The previous index stays current, so rollback is instant.</p>
        {stats.data && <div className="table-wrap" style={{ margin: "10px 0 14px" }}><table className="t"><thead><tr><th scope="col">Revision</th><th scope="col">Profile</th><th scope="col">State</th><th scope="col"><span className="sr">Actions</span></th></tr></thead>
          <tbody>{stats.data.index_revisions.map((r: any) => <tr key={r.id}><td className="mono small">{r.id.slice(0, 8)}</td><td className="mono small">{r.profile_id}</td><td><StateBadge state={r.state} /></td>
            <td style={{ textAlign: "right" }}>{r.state === "ready" && <button className="btn sm" onClick={() => act(() => call("POST", `/v1/stores/${store.id}/index-promotions`, { index_revision: r.id }), (s) => `Active profile is now ${s.profile_id}`)}>Activate {r.profile_id}</button>}</td></tr>)}</tbody></table></div>}
        {!customChunking && <p className="muted small">Segmentation is managed by the provider. New profiles are rolled out here as index builds you can activate or roll back.</p>}
        {customChunking && <><details style={{ margin: "4px 0 14px" }}>
          <summary className="small" style={{ cursor: "pointer", fontWeight: 600 }}>Create a custom chunking profile</summary>
          <form className="row" style={{ marginTop: 10 }} onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", "/v1/embedding-profiles", { name: d.get("pname"), text: { max_chars: Number(d.get("max")), overlap_chars: Number(d.get("ovl")) }, audio: { segment_seconds: Number(d.get("aud")) }, video: { segment_seconds: Number(d.get("vid")) } }).then((r) => { profiles.reload(); return r; }), (r) => `Profile ${r.name} created (${r.id})`); }}>
            <label className="field grow">Profile name<input name="pname" required placeholder="short passages" /></label>
            <label className="field" style={{ width: 120 }}>Passage chars<input name="max" type="number" min={200} max={6000} defaultValue={800} required /></label>
            <label className="field" style={{ width: 110 }}>Overlap chars<input name="ovl" type="number" min={0} max={2000} defaultValue={100} required /></label>
            <label className="field" style={{ width: 110 }}>Audio seconds<input name="aud" type="number" min={5} max={300} defaultValue={30} required /></label>
            <label className="field" style={{ width: 110 }}>Video seconds<input name="vid" type="number" min={5} max={32} defaultValue={30} required /></label>
            <button className="btn">Create profile</button>
          </form>
        </details>
        <form className="row" onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", `/v1/stores/${store.id}/reindex-jobs`, { profile_id: d.get("profile") }, { headers: { "idempotency-key": crypto.randomUUID() } }), () => "Index build started"); }}>
          <label className="field grow">Build index with profile<select name="profile">{profiles.data?.data.filter((p: any) => p.id !== store.profile_id).map((p: any) => <option key={p.id} value={p.id}>{p.name ? `${p.name} · ` : ""}{p.id} · {p.preparation.text.max_chars}-char passages</option>)}</select></label>
          <button className="btn">Start build</button>
        </form></>}
      </div>
    </section>
  );
}

function StoreSettings({ store, reload }: { store: any; reload: () => void }) {
  const { toast, reloadStores } = useApp();
  const [preview, setPreview] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const del = async (scope: string) => { try { await call("DELETE", `/v1/stores/${store.id}?sources=${scope}`); reloadStores(); location.assign("/"); } catch (e) { setError(e); } };
  return (
    <section aria-label="Store settings" className="stack" style={{ gap: 16, maxWidth: 760 }}>
      <ErrorBox error={error} />
      <div className="card pad">
        <h2>Name</h2>
        <form className="row" style={{ marginTop: 12 }} onSubmit={async (e) => { e.preventDefault(); try { await call("PATCH", `/v1/stores/${store.id}`, { name: new FormData(e.currentTarget).get("name") }); reload(); reloadStores(); toast("Store renamed"); } catch (err) { setError(err); } }}>
          <label className="field grow">Store name<input name="name" defaultValue={store.name} required /></label><button className="btn">Rename</button>
        </form>
        <p className="muted small">The store ID <code>{store.id}</code> never changes, so connected applications keep working after a rename.</p>
      </div>
      <div className="card pad" style={{ borderColor: "color-mix(in srgb, var(--bad) 30%, transparent)" }}>
        <h2 style={{ color: "var(--bad)" }}>Delete store</h2>
        <p className="muted small">Searches to this store fail immediately. You choose what happens to its sources.</p>
        <button className="btn danger" onClick={async () => { try { setPreview(await call("POST", `/v1/stores/${store.id}/deletion-previews`, {})); } catch (e) { setError(e); } }}><Trash2 aria-hidden />Delete store…</button>
      </div>
      <Modal open={!!preview} onClose={() => setPreview(null)} title={`Delete store ${store.name}?`} subtitle="Review what this affects before you choose.">
        {preview && <>
          <div className="stats" style={{ marginBottom: 16 }}>
            <div className="stat"><div className="k">Sources</div><div className="v">{preview.memberships}</div></div>
            <div className="stat"><div className="k">Shared</div><div className="v">{preview.sources_shared_with_other_stores}</div></div>
            <div className="stat"><div className="k">Live views</div><div className="v">{preview.dependent_views.length}</div></div>
            <div className="stat"><div className="k">Keys</div><div className="v">{preview.restricted_api_keys.length}</div></div>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <button className="btn danger-solid" onClick={() => del("unshared")}>Delete store and sources used only here</button>
            <button className="btn danger" onClick={() => del("keep")}>Delete store, keep sources</button>
          </div>
        </>}
      </Modal>
    </section>
  );
}

// ---------------------------------------------------------------- connect
function Connect({ store, open, onClose }: { store: any; open: boolean; onClose: () => void }) {
  const c = useLoad(() => (open ? call("GET", `/v1/stores/${store.id}/connection`) : Promise.resolve(null)), [open]);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  return (
    <Modal open={open} onClose={() => { setSecret(null); onClose(); }} title={`Connect an application to ${store.name}`} subtitle="Three steps. Your application calls the search API from its backend.">
      <ErrorBox error={error ?? c.error} />
      {!c.data ? <Loading /> : (
        <ol className="steps-v">
          <li>
            <h3>Create a search key for this store</h3>
            {secret ? <div role="status"><p className="small" style={{ marginTop: 0 }}>Store this key in your secret manager now. It is shown only once.</p><div className="row" style={{ alignItems: "center" }}><p className="secret grow" style={{ margin: 0 }}>{secret}</p><CopyButton text={secret} label="Copy key" /></div></div>
              : <button className="btn primary" onClick={async () => { try { setSecret((await call("POST", "/v1/api-keys", { name: `${store.name}-app`, scopes: ["search"], stores: [store.id] })).secret); } catch (e) { setError(e); } }}><KeyRound aria-hidden />Create a search key for this store</button>}
          </li>
          <li>
            <h3>Configure your backend</h3>
            <dl className="kv">
              <div><dt>Store ID</dt><dd>{c.data.store_id}<CopyButton text={c.data.store_id} label="Copy store ID" className="btn sm ghost icon" /></dd></div>
              <div><dt>Search URL</dt><dd>{c.data.search_url}<CopyButton text={c.data.search_url} label="Copy search URL" className="btn sm ghost icon" /></dd></div>
              <div><dt>Embeddings base URL</dt><dd>{c.data.embeddings_base_url}<CopyButton text={c.data.embeddings_base_url} label="Copy embeddings base URL" className="btn sm ghost icon" /></dd></div>
              <div><dt>Query model alias</dt><dd>{c.data.query_model}<CopyButton text={c.data.query_model} label="Copy query model alias" className="btn sm ghost icon" /></dd></div>
              <div><dt>Environment</dt><dd>KNOWLEDGE_API_KEY=…</dd></div>
            </dl>
          </li>
          <li>
            <h3>Run the code</h3>
            <Tabs label="Connection code" variant="pills" tabs={[
              { id: "py", title: "Python", render: () => <Code code={c.data.snippets.python} label="Python code" /> },
              { id: "js", title: "JavaScript", render: () => <Code code={c.data.snippets.javascript} label="JavaScript code" /> },
              { id: "curl", title: "cURL", render: () => <Code code={c.data.snippets.curl} label="cURL code" /> },
            ]} />
            <p className="muted small">Keep the key on your server. Never put it in browser code.</p>
          </li>
        </ol>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- page
const KIND_TITLE: Record<string, string> = { material: "Material store", view: "Live view", snapshot: "Snapshot" };
function StorePage({ id }: { id: string }) {
  const s = useLoad(() => call("GET", `/v1/stores/${id}`), [id]);
  const stats = useLoad(() => call("GET", `/v1/stores/${id}/stats`), [id, s.data?.file_count, s.data?.index_revision]);
  const [connect, setConnect] = useState(false);
  const [focusJob, setFocusJob] = useState<string | null>(null);
  const [tab, setTab] = useState(-1);
  const tabsKey = useRef(0);
  if (s.error) return <><PageHead crumbs={[{ href: "/", label: "Stores" }, { label: "Not found" }]} title="Store unavailable" /><ErrorBox error={s.error} /></>;
  if (!s.data) return <Loading what="Loading store" rows={4} />;
  const store = s.data;
  const order = ["search", "files", "import", "jobs", "compose", "settings"];
  const go = (t: string) => { setTab(order.indexOf(t)); tabsKey.current++; const u = new URL(location.href); u.searchParams.set("tab", t); history.replaceState(null, "", u); };
  const onJob = (j: string) => { setFocusJob(j); go("jobs"); s.reload(); };
  const initial = tab >= 0 ? tab : Math.max(0, order.indexOf(new URLSearchParams(typeof location !== "undefined" ? location.search : "").get("tab") ?? "search"));
  return (
    <>
      <PageHead crumbs={[{ href: "/", label: "Stores" }, { label: store.name }]}
        title={<span style={{ display: "inline-flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>{store.name}<StateBadge state={store.state} /></span>}
        desc={<>{KIND_TITLE[store.kind]}{store.kind === "view" ? " · follows its parent stores" : store.kind === "snapshot" ? " · fixed versions" : ""}</>}
        actions={<><button className="btn ghost" onClick={() => downloadExport(store).catch((e) => alert(e.message))} title="NDJSON: source, location, text and 768-d embedding per segment"><Download aria-hidden />Export embeddings</button>{store.kind === "material" && <button className="btn" onClick={() => go("import")}><FolderUp aria-hidden />Import</button>}<button className="btn primary" onClick={() => setConnect(true)}><Plug aria-hidden />Connect application</button></>} />
      <div className="stats reveal reveal-2">
        <div className="stat"><div className="k">Sources</div><div className="v">{store.file_count}</div></div>
        <div className="stat"><div className="k">Segments</div><div className="v">{store.segment_count}</div></div>
        <div className="stat"><div className="k">Source size</div><div className="v" style={{ fontSize: 22 }}>{stats.data ? fmtBytes(stats.data.source_bytes) : "–"}</div></div>
        <div className="stat"><div className="k">Profile</div><div className="v mono" style={{ fontSize: 13, fontFamily: "var(--font-mono)", marginTop: 10 }}>{store.profile_id}</div></div>
      </div>
      <Connect store={store} open={connect} onClose={() => setConnect(false)} />
      <Tabs key={tabsKey.current} label="Store sections" initial={initial} param="tab" tabs={[
        { id: "search", title: "Search", icon: <SearchIcon aria-hidden />, render: () => <Search store={store} /> },
        { id: "files", title: "Files", icon: <FileText aria-hidden />, render: () => <Files store={store} onJob={onJob} /> },
        { id: "import", title: "Import", icon: <FolderUp aria-hidden />, render: () => store.kind === "material" ? <Import store={store} onJob={onJob} /> : <Empty icon={<FolderUp />} title="Import into a material store">{store.kind === "view" ? "Live views show matching files from their parent stores." : "Snapshots are fixed."} Add material to a parent store instead.</Empty> },
        { id: "jobs", title: "Jobs", icon: <ListChecks aria-hidden />, render: () => <Jobs store={store} focus={focusJob} /> },
        { id: "compose", title: "Composition", icon: <Blend aria-hidden />, render: () => <Compose store={store} onJob={onJob} reload={s.reload} /> },
        { id: "settings", title: "Settings", icon: <Settings2 aria-hidden />, render: () => <StoreSettings store={store} reload={s.reload} /> },
      ]} />
    </>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Shell><StorePage id={id} /></Shell>;
}
