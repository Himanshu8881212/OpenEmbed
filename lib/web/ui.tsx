"use client";
import { AlertTriangle, Boxes, Check, CheckCircle2, ChevronRight, Copy, Database, FileText, KeyRound, LayoutGrid, LogOut, Menu, Plus, Search, Settings, Sparkles, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ApiErr, call, workspace } from "./api";
import { login, logout, signedIn } from "./session";

// ------------------------------------------------------------------ data hook
/** Load data with loading/error state; `reload` re-runs. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    setError(null);
    fn().then((d) => live && setData(d), (e) => live && setError(e));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { data, error, reload: () => setN((x) => x + 1), loading: data === null && !error };
}

// ------------------------------------------------------------------ app context (identity, workspace, stores, toasts)
type Ctx = {
  me: any; ws: string | null; role: string | null; stores: any[] | null;
  setWs: (id: string) => void; reloadMe: () => void; reloadStores: () => void;
  toast: (msg: string, kind?: "ok" | "bad") => void; openPalette: () => void;
};
const AppCtx = createContext<Ctx | null>(null);
export const useApp = () => useContext(AppCtx)!;

// ------------------------------------------------------------------ primitives
export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiErr;
  return (
    <div role="alert" className="alert">
      <AlertTriangle aria-hidden />
      <div><strong>{e.code && e.code !== "ERROR" ? `${humanCode(e.code)}. ` : ""}</strong>{e.message ?? String(error)}{e.requestId ? <div className="rid">Reference {e.requestId}</div> : null}</div>
    </div>
  );
}
const humanCode = (c: string) => c.charAt(0) + c.slice(1).toLowerCase().replaceAll("_", " ");

export const Loading = ({ what = "Loading", rows = 3 }: { what?: string; rows?: number }) => (
  <div role="status" aria-live="polite" className="stack" style={{ gap: 10 }}>
    <span className="sr">{what}…</span>
    {Array.from({ length: rows }, (_, i) => <div key={i} className="skel" style={{ height: 18 + (i === 0 ? 10 : 0), width: `${90 - i * 14}%` }} />)}
  </div>
);

export function Empty({ icon = <Sparkles />, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty reveal"><div className="glyph" aria-hidden>{icon}</div><h3>{title}</h3>{children && <p>{children}</p>}{action}</div>;
}

export function Meter({ value, max, tone, label }: { value: number; max: number; tone?: "ok" | "warn" | "bad" | "accent"; label?: string }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  const t = tone ?? (pct >= 90 ? "bad" : pct >= 75 ? "warn" : "ok");
  return <div className={`meter ${t}`} role="progressbar" aria-label={label} aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={max}><i style={{ width: `${pct}%` }} /></div>;
}

export function StateBadge({ state }: { state: string }) {
  const tone = state === "completed" || state === "ready" || state === "published" || state === "active" ? "ok"
    : ["failed", "cancelled"].includes(state) ? "bad" : state === "completed_with_errors" ? "warn"
    : ["queued", "running", "cancel_requested", "processing", "building"].includes(state) ? "busy" : "";
  return <span className={`badge ${tone}`} data-state={state}>{state.replaceAll("_", " ")}</span>;
}

export function CopyButton({ text, label = "Copy", className = "btn sm" }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className={className} onClick={async () => { await navigator.clipboard?.writeText(text).catch(() => {}); setDone(true); setTimeout(() => setDone(false), 1400); }} aria-label={label}>
      {done ? <Check aria-hidden /> : <Copy aria-hidden />}<span>{done ? "Copied" : label === "Copy" ? "Copy" : ""}</span>
    </button>
  );
}

/** Minimal code highlighter: strings, keywords, comments. */
function highlight(src: string) {
  const re = /(#.*$|\/\/.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)|\b(import|from|const|await|for|of|in|if|throw|new|return|def|print|async|curl)\b/gm;
  const out: ReactNode[] = [];
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(src))) {
    if (m.index > last) out.push(src.slice(last, m.index));
    out.push(<span key={i++} className={m[1] ? "tok-c" : m[2] ? "tok-s" : "tok-k"}>{m[0]}</span>);
    last = m.index + m[0].length;
  }
  out.push(src.slice(last));
  return out;
}
export function Code({ code, label }: { code: string; label: string }) {
  return <div className="code"><div className="copy"><CopyButton text={code} label={`Copy ${label}`} className="btn sm dark" /></div><pre tabIndex={0} aria-label={label}>{highlight(code)}</pre></div>;
}

/** WAI-ARIA tabs (arrow keys / Home / End). Optional `param` mirrors the selection in the URL (?tab=). */
export function Tabs({ tabs, label, initial = 0, param, variant = "line", onChange }: { tabs: { id: string; title: string; icon?: ReactNode; render: () => ReactNode }[]; label: string; initial?: number; param?: string; variant?: "line" | "pills"; onChange?: (id: string) => void }) {
  const fromUrl = () => { if (!param || typeof window === "undefined") return -1; return tabs.findIndex((t) => t.id === new URLSearchParams(location.search).get(param)); };
  const [sel, setSelState] = useState(() => { const u = fromUrl(); return u >= 0 ? u : initial; });
  useEffect(() => { setSelState(initial); }, [initial]);
  const setSel = (i: number) => {
    setSelState(i);
    onChange?.(tabs[i].id);
    if (param) { const u = new URL(location.href); u.searchParams.set(param, tabs[i].id); history.replaceState(null, "", u); }
  };
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (i: number) => { const n = (i + tabs.length) % tabs.length; setSel(n); refs.current[n]?.focus(); };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") move(sel + 1); else if (e.key === "ArrowLeft") move(sel - 1);
    else if (e.key === "Home") move(0); else if (e.key === "End") move(tabs.length - 1); else return;
    e.preventDefault();
  };
  return (
    <>
      <div role="tablist" aria-label={label} onKeyDown={onKey} className={`tabs ${variant === "pills" ? "pills" : ""}`}>
        {tabs.map((t, i) => (
          <button key={t.id} ref={(el) => { refs.current[i] = el; }} role="tab" id={`tab-${t.id}`} aria-controls={`panel-${t.id}`} aria-selected={sel === i} tabIndex={sel === i ? 0 : -1} onClick={() => setSel(i)}>{t.icon}{t.title}</button>
        ))}
      </div>
      {tabs.map((t, i) => <div key={t.id} role="tabpanel" id={`panel-${t.id}`} aria-labelledby={`tab-${t.id}`} hidden={sel !== i} tabIndex={0}>{sel === i ? t.render() : null}</div>)}
    </>
  );
}

/** Native modal dialog (focus containment + Escape by the browser). `drawer` slides in from the right. */
export function Modal({ open, onClose, title, subtitle, children, drawer = false, footer }: { open: boolean; onClose: () => void; title: string; subtitle?: ReactNode; children: ReactNode; drawer?: boolean; footer?: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const d = ref.current; if (!d) return; if (open && !d.open) d.showModal(); if (!open && d.open) d.close(); }, [open]);
  return (
    <dialog ref={ref} className={drawer ? "drawer" : ""} aria-labelledby="dialog-title" onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="sheet">
        <div className="sheet-head">
          <div><h2 id="dialog-title">{title}</h2>{subtitle && <p className="muted small" style={{ margin: "4px 0 0" }}>{subtitle}</p>}</div>
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><X aria-hidden /></button>
        </div>
        <div className="sheet-body">{open ? children : null}{footer && <div className="row" style={{ justifyContent: "flex-end", marginTop: 20 }}>{footer}</div>}</div>
      </div>
    </dialog>
  );
}

export function PageHead({ crumbs, title, desc, actions }: { crumbs?: { href?: string; label: string }[]; title: ReactNode; desc?: ReactNode; actions?: ReactNode }) {
  return (
    <>
      {crumbs && <nav aria-label="Breadcrumb" className="crumbs">{crumbs.map((c, i) => <span key={i} style={{ display: "contents" }}>{i > 0 && <ChevronRight size={13} aria-hidden />}{c.href ? <Link href={c.href}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}</span>)}</nav>}
      <header className="head reveal"><div><h1>{title}</h1>{desc && <p>{desc}</p>}</div>{actions && <div className="head-actions">{actions}</div>}</header>
    </>
  );
}

// ------------------------------------------------------------------ command palette
function Palette({ open, onClose, stores }: { open: boolean; onClose: () => void; stores: any[] }) {
  const router = useRouter();
  const ref = useRef<HTMLDialogElement>(null);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  useEffect(() => { const d = ref.current; if (!d) return; if (open && !d.open) { setQ(""); setI(0); d.showModal(); } if (!open && d.open) d.close(); }, [open]);
  const items = useMemo(() => {
    const all = [
      ...stores.map((s) => ({ label: `Search ${s.name}`, grp: "Store", icon: <Search />, go: `/stores/${s.id}?tab=search` })),
      ...stores.map((s) => ({ label: `Import into ${s.name}`, grp: "Store", icon: <Plus />, go: `/stores/${s.id}?tab=import` })),
      { label: "All stores", grp: "Go to", icon: <LayoutGrid />, go: "/" },
      { label: "Usage", grp: "Go to", icon: <Database />, go: "/settings?tab=usage" },
      { label: "API keys", grp: "Go to", icon: <KeyRound />, go: "/settings?tab=keys" },
      { label: "Members", grp: "Go to", icon: <Users />, go: "/settings?tab=members" },
    ];
    const t = q.toLowerCase().trim();
    return t ? all.filter((x) => x.label.toLowerCase().includes(t)) : all;
  }, [q, stores]);
  const pick = (k: number) => { const it = items[k]; if (!it) return; onClose(); router.push(it.go); };
  return (
    <dialog ref={ref} className="cmd" aria-label="Command palette" onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="palette">
        <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setI(0); }} placeholder="Jump to a store, import, keys…" aria-label="Command" role="combobox" aria-expanded="true" aria-controls="cmd-list" aria-activedescendant={`cmd-${i}`}
          onKeyDown={(e) => { if (e.key === "ArrowDown") { setI((x) => Math.min(items.length - 1, x + 1)); e.preventDefault(); } else if (e.key === "ArrowUp") { setI((x) => Math.max(0, x - 1)); e.preventDefault(); } else if (e.key === "Enter") pick(i); }} />
        <ul id="cmd-list" role="listbox">
          {items.map((it, k) => <li key={it.label} id={`cmd-${k}`} role="option" aria-selected={k === i} onMouseEnter={() => setI(k)} onClick={() => pick(k)}>{it.icon}{it.label}<span className="grp">{it.grp}</span></li>)}
          {!items.length && <li aria-disabled>No matches</li>}
        </ul>
      </div>
    </dialog>
  );
}

// ------------------------------------------------------------------ shell
function SignIn() {
  // No intermediate landing page: the provider's themed form (sign in, register, reset password) is the first screen.
  useEffect(() => { login(); }, []);
  return <main id="main" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><p role="status" className="muted">Redirecting to sign in…</p></main>;
}

export function Shell({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  useEffect(() => { setAuthed(signedIn()); setReady(true); }, []);
  if (!ready) return null;
  if (!authed) return <SignIn />;
  return <AppFrame>{children}</AppFrame>;
}

function AppFrame({ children }: { children: ReactNode }) {
  const path = usePathname();
  const me = useLoad(() => call("GET", "/v1/me"));
  const [ws, setWsState] = useState<string | null>(null);
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([]);
  const [palette, setPalette] = useState(false);
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (!me.data) return;
    const ids = me.data.workspaces.map((w: any) => w.id);
    const cur = workspace.get();
    const pick = cur && ids.includes(cur) ? cur : ids[0] ?? null;
    if (pick) workspace.set(pick);
    setWsState(pick);
  }, [me.data]);
  const stores = useLoad(() => (ws ? call("GET", "/v1/stores?limit=200").then((r) => r.data) : Promise.resolve(null)), [ws]);
  useEffect(() => {
    const k = (e: globalThis.KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  useEffect(() => setMenu(false), [path]);
  const toast = useCallback((msg: string, kind: "ok" | "bad" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);
  const role = me.data?.workspaces.find((w: any) => w.id === ws)?.role ?? null;
  const ctx: Ctx = { me: me.data, ws, role, stores: stores.data, setWs: (id) => { workspace.set(id); setWsState(id); }, reloadMe: me.reload, reloadStores: stores.reload, toast, openPalette: () => setPalette(true) };
  const initials = (me.data?.email ?? "?").slice(0, 2).toUpperCase();

  return (
    <AppCtx.Provider value={ctx}>
      <div className="mobile-top"><button className="btn ghost icon" style={{ color: "#fff" }} onClick={() => setMenu(true)} aria-label="Open navigation"><Menu aria-hidden /></button><span className="brand-name">Knowledge Store</span></div>
      <div className="app">
        <aside className={`side ${menu ? "open" : ""}`} aria-label="Workspace navigation">
          <Link href="/" className="brand"><span className="brand-mark" aria-hidden>K</span><span className="brand-name">Knowledge Store<small>Workbench</small></span></Link>
          <button className="kbd-hint" onClick={() => setPalette(true)}><Search size={14} aria-hidden />Quick jump<kbd>⌘K</kbd></button>
          {me.data && me.data.workspaces.length > 0 && (
            <label className="ws-switch"><span className="sr">Workspace</span>
              <select value={ws ?? ""} onChange={(e) => ctx.setWs(e.target.value)}>
                {me.data.workspaces.map((w: any) => <option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}
              </select>
            </label>
          )}
          <nav aria-label="Main" style={{ display: "contents" }}>
            <div className="side-label">Library</div>
            <Link className="nav" href="/" aria-current={path === "/" ? "page" : undefined}><LayoutGrid size={16} aria-hidden />All stores<span className="count">{stores.data?.length ?? ""}</span></Link>
            <div className="stores">
              {stores.data?.map((s: any) => (
                <Link key={s.id} className="nav" href={`/stores/${s.id}`} aria-current={path === `/stores/${s.id}` ? "page" : undefined}>
                  <span className={`dot ${s.kind !== "material" ? s.kind : s.state}`} aria-hidden /><span className="ellipsis">{s.name}</span><span className="count">{s.file_count}</span>
                </Link>
              ))}
            </div>
            <div className="side-label">Workspace</div>
            <Link className="nav" href="/settings" aria-current={path === "/settings" ? "page" : undefined}><Settings size={16} aria-hidden />Access and usage</Link>
          </nav>
          <div className="side-foot">
            <span className="avatar" aria-hidden>{initials}</span>
            <div className="who">{me.data?.email ?? "…"}<span>{role ?? ""}</span></div>
            <button className="btn ghost icon" style={{ marginLeft: "auto", color: "#c9c8c2" }} onClick={() => logout()} aria-label="Sign out" title="Sign out"><LogOut aria-hidden /></button>
          </div>
        </aside>
        <main id="main" className="main">
          <div className="page">{me.error ? <ErrorBox error={me.error} /> : !me.data ? <Loading what="Loading workspace" /> : children}</div>
        </main>
      </div>
      <Palette open={palette} onClose={() => setPalette(false)} stores={stores.data ?? []} />
      <div className="toasts" role="status" aria-live="polite">{toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.kind === "bad" ? <AlertTriangle aria-hidden /> : <CheckCircle2 aria-hidden />}{t.msg}</div>)}</div>
    </AppCtx.Provider>
  );
}

export const Icons = { Boxes, FileText, KeyRound, Users, Database, Plus, Search };
