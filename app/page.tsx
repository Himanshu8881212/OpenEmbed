"use client";
import { Boxes, Dices, Eye, Layers, Library, Plus, Snowflake } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { call } from "@/lib/web/api";
import { names } from "@/lib/wordlist";

const gen = names((n) => Math.floor(Math.random() * n));
/** Text field pre-filled with a readable random name; the dice button suggests another. */
function NameField({ label, name, make, pattern }: { label: string; name: string; make: () => string; pattern?: string }) {
  const [v, setV] = useState("");
  const id = useId();
  useEffect(() => setV(make()), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="field grow">
      <label htmlFor={id}>{label}</label>
      <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
        <input id={id} name={name} value={v} onChange={(e) => setV(e.target.value)} required maxLength={100} pattern={pattern} style={{ flex: 1 }} />
        <button type="button" className="btn icon" onClick={() => setV(make())} aria-label={`Suggest another ${label.toLowerCase()}`} title="Suggest another name"><Dices aria-hidden /></button>
      </span>
    </div>
  );
}
import { Empty, ErrorBox, Loading, PageHead, Shell, StateBadge, useApp } from "@/lib/web/ui";

const KIND = { material: { icon: <Library size={14} aria-hidden />, label: "Material" }, view: { icon: <Eye size={14} aria-hidden />, label: "Live view" }, snapshot: { icon: <Snowflake size={14} aria-hidden />, label: "Snapshot" } } as Record<string, { icon: React.ReactNode; label: string }>;

function CreateWorkspace() {
  const { reloadMe, setWs, toast } = useApp();
  const [error, setError] = useState<unknown>(null);
  return (
    <form className="row" onSubmit={async (e) => {
      e.preventDefault();
      try { const w = await call("POST", "/v1/workspaces", { name: String(new FormData(e.currentTarget).get("name")) }); setWs(w.id); reloadMe(); toast(`Workspace ${w.name} created`); } catch (err) { setError(err); }
    }}>
      <NameField label="Workspace name" name="name" make={gen.workspace} />
      <button className="btn primary">Create workspace</button>
      <div style={{ flexBasis: "100%" }}><ErrorBox error={error} /></div>
    </form>
  );
}

function Stores() {
  const { me, ws, role, stores, reloadStores, toast } = useApp();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (!ws) {
    return (
      <>
        <PageHead title="Set up your workspace" desc={`Signed in as ${me.email}. A workspace is your team's boundary for stores, members, keys and usage.`} />
        <div className="card pad reveal" style={{ maxWidth: 620 }}><CreateWorkspace /></div>
      </>
    );
  }
  const totals = (stores ?? []).reduce((a, s) => ({ files: a.files + s.file_count, segs: a.segs + s.segment_count }), { files: 0, segs: 0 });
  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = e.currentTarget;
    setBusy(true);
    const fd = new FormData(f);
    try { const s = await call("POST", "/v1/stores", { name: String(fd.get("name")) }); f.reset(); setError(null); reloadStores(); toast(`Store ${s.name} created`); } catch (err) { setError(err); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHead title="Stores" desc="Named collections of company material. Each store has a stable ID, its own search, and its own connection for applications." />
      <div className="stats reveal reveal-2" aria-label="Workspace totals">
        <div className="stat"><div className="k">Stores</div><div className="v">{stores?.length ?? "–"}</div></div>
        <div className="stat"><div className="k">Sources</div><div className="v">{totals.files}</div></div>
        <div className="stat"><div className="k">Segments indexed</div><div className="v">{totals.segs}</div></div>
        <div className="stat"><div className="k">Your role</div><div className="v" style={{ fontSize: 20, textTransform: "capitalize" }}>{role}</div></div>
      </div>
      <ErrorBox error={error} />
      {!stores ? <Loading what="Loading stores" /> : (
        <div className="grid-cards">
          {role !== "viewer" && (
            <form className="new-card reveal" onSubmit={create} aria-label="New store">
              <div className="row" style={{ alignItems: "center", gap: 8 }}><span className="badge"><Plus size={12} aria-hidden />New</span><strong>Create a store</strong></div>
              <NameField label="Store name" name="name" make={gen.store} pattern="[A-Za-z0-9][A-Za-z0-9._\-]{0,99}" />
              <button className="btn primary" disabled={busy}>Create store</button>
            </form>
          )}
          {stores.map((s, i) => (
            <Link key={s.id} href={`/stores/${s.id}`} className="store-card" style={{ animationDelay: `${0.03 * (i + 1)}s` }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <span className="badge">{KIND[s.kind]?.icon}{KIND[s.kind]?.label}</span>
                <StateBadge state={s.state} />
              </div>
              <div className="name">{s.name}</div>
              <div className="figs"><div><b>{s.file_count}</b>sources</div><div><b>{s.segment_count}</b>segments</div></div>
              <div className="foot"><span className="mono">{s.profile_id}</span><span aria-hidden>Open →</span></div>
            </Link>
          ))}
        </div>
      )}
      {stores && stores.length === 0 && role === "viewer" && <Empty icon={<Boxes />} title="No stores yet">Ask an editor to create a store and import material.</Empty>}
      {stores && stores.length > 0 && (
        <p className="muted small" style={{ marginTop: 24, display: "flex", gap: 8, alignItems: "center" }}><Layers size={14} aria-hidden />Build focused stores without re-uploading: open a store → <strong>Composition</strong> to derive a live view, a snapshot or a merge.</p>
      )}
      <details style={{ marginTop: 28 }}><summary className="muted small" style={{ cursor: "pointer" }}>New workspace</summary><div className="card pad" style={{ marginTop: 10, maxWidth: 620 }}><CreateWorkspace /></div></details>
    </>
  );
}

export default function Home() { return <Shell><Stores /></Shell>; }
