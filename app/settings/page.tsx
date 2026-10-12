"use client";
import { Activity, KeyRound, ScrollText, ShieldCheck, Trash2, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { call, fmtBytes } from "@/lib/web/api";
import { CopyButton, Empty, ErrorBox, Loading, Meter, PageHead, Shell, StateBadge, Tabs, useApp, useLoad } from "@/lib/web/ui";

function Usage() {
  const u = useLoad(() => call("GET", "/v1/usage"));
  if (u.error) return <ErrorBox error={u.error} />;
  if (!u.data) return <Loading rows={4} />;
  const d = u.data;
  const Tile = ({ title, used, limit, fmt = (n: number) => n.toLocaleString(), children }: { title: string; used: number; limit: number; fmt?: (n: number) => string; children?: React.ReactNode }) => (
    <div className="card pad">
      <div className="k muted small" style={{ textTransform: "uppercase", letterSpacing: ".1em", fontSize: 11 }}>{title}</div>
      <div className="display" style={{ fontSize: 30, margin: "4px 0 2px" }}>{fmt(used)}</div>
      <p className="muted small" style={{ margin: "0 0 10px" }}>{title}: {fmt(used)} of {fmt(limit)} · {Math.round((used / limit) * 100)}% used</p>
      <Meter value={used} max={limit} label={title} />
      {children}
    </div>
  );
  return (
    <section aria-label="Usage" className="stack" style={{ gap: 16 }}>
      <div className="grid-cards">
        <Tile title="Storage" used={d.storage.total_bytes} limit={d.storage.limit_bytes} fmt={fmtBytes}>
          <p className="muted small" style={{ margin: "10px 0 0" }}>{d.storage.gib_month_to_date.toFixed(4)} GiB-month accrued this month</p>
        </Tile>
        <Tile title="Indexing this month (tokens)" used={d.indexing.total_tokens} limit={d.indexing.limit_tokens} />
        <Tile title="Queries this month (tokens)" used={d.queries.total_tokens} limit={d.queries.limit_tokens} />
      </div>
      <div className="card pad">
        <h2>Storage by category</h2>
        <div className="stats" style={{ margin: "12px 0 0" }}>
          <div className="stat"><div className="k">Originals</div><div className="v" style={{ fontSize: 20 }}>{fmtBytes(d.storage.originals_bytes)}</div></div>
          <div className="stat"><div className="k">Vectors</div><div className="v" style={{ fontSize: 20 }}>{fmtBytes(d.storage.vector_bytes)}</div></div>
          <div className="stat"><div className="k">Prepared text</div><div className="v" style={{ fontSize: 20 }}>{fmtBytes(d.storage.prepared_bytes)}</div></div>
          <div className="stat"><div className="k">Metadata</div><div className="v" style={{ fontSize: 20 }}>{fmtBytes(d.storage.metadata_bytes)}</div></div>
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>Identical files are stored once per workspace. {d.hard_caps ? "Hard caps are on: work stops at the allowance." : "Excess use is enabled."}</p>
      </div>
      {d.warnings.map((w: string) => <div key={w} role="alert" className="alert">{w}</div>)}
    </section>
  );
}

function Keys() {
  const { toast, stores } = useApp();
  const k = useLoad(() => call("GET", "/v1/api-keys"));
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    try {
      const r = await call("POST", "/v1/api-keys", { name: d.get("name"), scopes: d.getAll("scope").map(String), ...(d.get("store") ? { stores: [d.get("store")] } : {}) });
      setSecret(r.secret); setError(null); k.reload(); toast(`Key ${r.name} created`);
    } catch (err) { setError(err); }
  }
  return (
    <section aria-label="API keys" className="stack" style={{ gap: 16 }}>
      <div className="card pad">
        <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><KeyRound size={17} aria-hidden />Create an application key</h2>
        <p className="muted small">Keys belong in your backend's secret manager. The secret is shown once and is never stored in this browser.</p>
        <form className="row" onSubmit={create}>
          <label className="field grow">Key name<input name="name" required placeholder="support-bot-prod" /></label>
          <label className="field grow">Store<select name="store" defaultValue=""><option value="">All stores</option>{stores?.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          <fieldset className="row" style={{ border: 0, padding: 0, margin: 0, gap: 6 }}><legend className="sr">Scopes</legend>
            {["search", "source:read", "source:write", "embeddings"].map((s) => <label key={s} className="chip" style={{ cursor: "pointer" }}><input type="checkbox" name="scope" value={s} defaultChecked={s === "search"} /> {s}</label>)}
          </fieldset>
          <button className="btn primary">Create key</button>
        </form>
        {secret && <div role="status" style={{ marginTop: 14 }}><p className="small">Copy this secret now. It will not be shown again:</p><div className="row" style={{ alignItems: "center" }}><p className="secret grow" style={{ margin: 0 }}>{secret}</p><CopyButton text={secret} label="Copy key" /><button className="btn ghost" onClick={() => setSecret(null)}>I have stored it</button></div></div>}
        <ErrorBox error={error} />
      </div>
      <ErrorBox error={k.error} />
      {!k.data ? <Loading /> : k.data.data.length === 0 ? <Empty icon={<KeyRound />} title="No keys yet">Create one above, or from a store's Connect dialog.</Empty> : (
        <div className="table-wrap"><table className="t"><thead><tr><th scope="col">Name</th><th scope="col">Key</th><th scope="col">Scopes</th><th scope="col">Last used</th><th scope="col">Status</th><th scope="col"><span className="sr">Actions</span></th></tr></thead>
          <tbody>{k.data.data.map((x: any) => (
            <tr key={x.id}><td><strong>{x.name}</strong></td><td><code>{x.prefix}…</code></td><td><div className="row" style={{ gap: 4 }}>{x.scopes.map((s: string) => <span key={s} className="badge">{s}</span>)}</div></td>
              <td className="small muted">{x.last_used_at ? new Date(x.last_used_at).toLocaleString() : "never"}</td><td>{x.revoked_at ? <span className="badge bad">revoked</span> : <span className="badge ok">active</span>}</td>
              <td style={{ textAlign: "right" }}>{!x.revoked_at && <button className="btn sm danger" onClick={async () => { try { await call("DELETE", `/v1/api-keys/${x.id}`); k.reload(); toast(`Key ${x.name} revoked`); } catch (e) { setError(e); } }}>Revoke<span className="sr"> {x.name}</span></button>}</td></tr>
          ))}</tbody></table></div>
      )}
    </section>
  );
}

function Members() {
  const { ws, toast } = useApp();
  const m = useLoad(() => call("GET", `/v1/workspaces/${ws}/members`), [ws]);
  const [error, setError] = useState<unknown>(null);
  const act = async (f: () => Promise<unknown>, msg: string) => { try { await f(); setError(null); m.reload(); toast(msg); } catch (e) { setError(e); } };
  return (
    <section aria-label="Members" className="stack" style={{ gap: 16 }}>
      <div className="card pad">
        <h2 style={{ display: "flex", gap: 8, alignItems: "center" }}><UserPlus size={17} aria-hidden />Invite a member</h2>
        <p className="muted small">Owners manage members, keys and plans. Editors manage stores and material. Viewers search and read.</p>
        <form className="row" onSubmit={(e) => { e.preventDefault(); const d = new FormData(e.currentTarget); act(() => call("POST", `/v1/workspaces/${ws}/members`, { email: d.get("email"), role: d.get("role") }), `Invited ${d.get("email")}`); }}>
          <label className="field grow">Email<input name="email" type="email" required placeholder="colleague@company.com" /></label>
          <label className="field">Role<select name="role" defaultValue="viewer"><option>viewer</option><option>editor</option><option>owner</option></select></label>
          <button className="btn primary">Invite member</button>
        </form>
      </div>
      <ErrorBox error={error ?? m.error} />
      {!m.data ? <Loading /> : (
        <div className="table-wrap"><table className="t"><thead><tr><th scope="col">Member</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col"><span className="sr">Actions</span></th></tr></thead>
          <tbody>{m.data.data.map((x: any) => (
            <tr key={x.id}><td><span className="row" style={{ alignItems: "center", gap: 10 }}><span className="avatar" aria-hidden style={{ background: "var(--ink-3)" }}>{x.email.slice(0, 2).toUpperCase()}</span>{x.email}</span></td>
              <td><label className="field" style={{ maxWidth: 150 }}><span className="sr">Role for {x.email}</span><select value={x.role} onChange={(e) => act(() => call("PATCH", `/v1/workspaces/${ws}/members/${x.id}`, { role: e.target.value }), "Role updated")}><option>viewer</option><option>editor</option><option>owner</option></select></label></td>
              <td><StateBadge state={x.status === "active" ? "active" : "invited"} /></td>
              <td style={{ textAlign: "right" }}><button className="btn sm danger" onClick={() => act(() => call("DELETE", `/v1/workspaces/${ws}/members/${x.id}`), `Removed ${x.email}`)} aria-label={`Remove ${x.email}`}><Trash2 aria-hidden /></button></td></tr>
          ))}</tbody></table></div>
      )}
    </section>
  );
}

function Audit() {
  const a = useLoad(() => call("GET", "/v1/audit-events?limit=100"));
  if (a.error) return <ErrorBox error={a.error} />;
  if (!a.data) return <Loading rows={6} />;
  if (!a.data.data.length) return <Empty icon={<ScrollText />} title="No events yet">Key, member, store and deletion actions are recorded here.</Empty>;
  return <div className="table-wrap"><table className="t"><thead><tr><th scope="col">When</th><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Target</th></tr></thead>
    <tbody>{a.data.data.map((e: any) => <tr key={e.id}><td className="small">{new Date(e.created_at).toLocaleString()}</td><td><span className="badge">{e.action}</span></td><td className="mono small muted">{e.actor}</td><td className="mono small muted">{e.target}</td></tr>)}</tbody></table></div>;
}

function Access() {
  const { role } = useApp();
  return (
    <>
      <PageHead title="Access and usage" desc="Allowances, application keys, members and the audit trail for this workspace." />
      <Tabs label="Access and usage" param="tab" tabs={[
        { id: "usage", title: "Usage", icon: <Activity aria-hidden />, render: () => <Usage /> },
        { id: "keys", title: "API keys", icon: <KeyRound aria-hidden />, render: () => (role === "viewer" ? <Empty icon={<ShieldCheck />} title="Editors and owners manage keys" /> : <Keys />) },
        { id: "members", title: "Members", icon: <Users aria-hidden />, render: () => <Members /> },
        { id: "audit", title: "Audit log", icon: <ScrollText aria-hidden />, render: () => (role === "owner" ? <Audit /> : <Empty icon={<ShieldCheck />} title="Owners can view the audit log" />) },
      ]} />
    </>
  );
}

export default function Settings() { return <Shell><Access /></Shell>; }
