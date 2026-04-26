import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  BrowserRouter, Routes, Route, Link, NavLink,
  useNavigate, useParams, useSearchParams,
} from 'react-router-dom';
import './index.css';
import {
  getStores, getStore, createStore, deleteStore, deleteDocument,
  embedFile, embedBatch,
  searchText,
  healthCheck, getFileUrl, getApiBase,
  saveVaultKey, getVaultKey, removeVaultKey, rotateVaultKey,
  StoreFile, CreateStoreResponse, VectorStore,
} from './services/api';

// ─── Helpers ──────────────────────────────────────────────────────

const EXT_MOD: Record<string, string> = {
  txt: 'text', md: 'text',
  jpg: 'image', jpeg: 'image', png: 'image', gif: 'image', webp: 'image',
  mp4: 'video', mov: 'video',
  mp3: 'audio', wav: 'audio', flac: 'audio', m4a: 'audio', ogg: 'audio',
  pdf: 'document',
};
const getMod = (name: string) => EXT_MOD[name.split('.').pop()?.toLowerCase() || ''] || 'unknown';
const fmtSize = (b: number) => b < 1024 ? `${b}B` : b < 1048576 ? `${(b / 1024).toFixed(1)}KB` : `${(b / 1048576).toFixed(1)}MB`;

const MOD_TONE: Record<string, PillTone> = {
  image: 'image', audio: 'audio', video: 'video',
  text: 'text', document: 'document', unknown: 'neutral',
};

// ─── Toast plumbing ─────────────────────────────────────────────

type Toast = { id: number; msg: string; type: 'success' | 'error' };
let toastCounter = 0;
type ToastFn = (msg: string, type?: 'success' | 'error') => void;

// ─── Reusable Pill ──────────────────────────────────────────────

type PillTone = 'neutral' | 'accent' | 'image' | 'audio' | 'video' | 'text' | 'document' | 'success' | 'error';

interface PillProps {
  label: React.ReactNode;
  icon?: React.ReactNode;
  selected?: boolean;
  onClick?: () => void;
  tone?: PillTone;
  size?: 'sm' | 'md';
  title?: string;
}

function Pill({ label, icon, selected, onClick, tone = 'neutral', size = 'sm', title }: PillProps) {
  const cls = [
    'pill',
    `pill-${size}`,
    onClick ? 'pill-clickable' : '',
    selected ? 'pill-selected' : '',
    tone !== 'neutral' ? `tone-${tone}` : '',
  ].filter(Boolean).join(' ');

  return (
    <span
      className={cls}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      title={title}
      onClick={onClick}
      onKeyDown={(e) => {
        if (!onClick) return;
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); }
      }}
    >
      {icon}<span>{label}</span>
    </span>
  );
}

// ─── Root ─────────────────────────────────────────────────────────

export default function App() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast: ToastFn = useCallback((msg, type = 'success') => {
    const id = ++toastCounter;
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  return (
    <BrowserRouter>
      <div className="app-root">
        <AppHeader online={false} vaultCount={null} />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<SearchPage onToast={showToast} />} />
            <Route path="/dashboard" element={<DashboardPage onToast={showToast} />} />
            <Route path="/vaults" element={<VaultsListPage onToast={showToast} onChange={() => {}} />} />
            <Route path="/vaults/:name" element={<VaultDetailPage onToast={showToast} />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <div className="toast-container">
          {toasts.map(t => <div key={t.id} className={`toast ${t.type}`}>{t.msg}</div>)}
        </div>
      </div>
    </BrowserRouter>
  );
}

// ─── Header ───────────────────────────────────────────────────────

function AppHeader(_: { online: boolean; vaultCount: number | null }) {
  return (
    <nav className="top-nav app-header">
      <div className="header-left">
        <Link to="/" className="brand-wordmark" aria-label="EMBED home">
          <span>EMBED</span>
        </Link>
      </div>
      <div className="header-center">
        <NavLink to="/" end className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>Search</NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>Dashboard</NavLink>
        <NavLink to="/vaults" className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>Vaults</NavLink>
      </div>
      <div className="header-right" />
    </nav>
  );
}

function NotFound() {
  return (
    <div className="page-container view-enter" style={{ textAlign: 'center', paddingTop: 80 }}>
      <h1 className="hero-title" style={{ fontSize: 56 }}>Not Found</h1>
      <Link to="/" className="btn btn-primary" style={{ marginTop: 24 }}>Back to Search</Link>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SEARCH PAGE (home / "/")
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function SearchPage({ onToast }: { onToast: ToastFn }) {
  const [stores, setStores] = useState<VectorStore[]>([]);
  const [loadingStores, setLoadingStores] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const initialVault = searchParams.get('vault') || '';
  const [selectedVault, setSelectedVault] = useState<string>(initialVault);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    getStores()
      .then(s => {
        setStores(s);
        // If only one vault and none selected, preselect it for friendliness.
        if (!selectedVault && s.length === 1) setSelectedVault(s[0].name);
      })
      .catch(e => onToast(e.response?.data?.detail || 'Failed to load vaults', 'error'))
      .finally(() => setLoadingStores(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep ?vault= in URL synced
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (selectedVault) next.set('vault', selectedVault);
    else next.delete('vault');
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVault]);

  // Debounced live search
  useEffect(() => {
    if (!selectedVault || !query.trim()) { setResults(null); return; }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await searchText(selectedVault, query.trim(), 12, 0.0);
        setResults(res);
      } catch (e: any) {
        const msg = e.response?.data?.detail || 'Search failed';
        // Avoid spamming toasts on every keystroke
        if (e.response?.status === 401 || e.response?.status === 403) {
          onToast(`${msg} — set the API key on the vault page.`, 'error');
        }
        setResults({ results: [], count: 0, error: msg });
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [query, selectedVault, onToast]);

  // Auto-issue an API key for the selected vault so search works without manual setup
  useEffect(() => {
    if (!selectedVault) return;
    if (getVaultKey(selectedVault)) return;
    let cancelled = false;
    rotateVaultKey(selectedVault).catch(() => {});
    return () => { cancelled = true; void cancelled; };
  }, [selectedVault]);

  const searched = !!query.trim();

  return (
    <div className={'search-page page-container view-enter' + (searched ? ' searched' : '')}>
      <div className="search-page-hero">
        <h1 className="hero-title">Ask anything.</h1>
        <p className="hero-subtitle">Multimodal retrieval across your vaults — text, image, audio, video.</p>

        <div className="search-bar-massive" style={{ width: '100%' }}>
          <input
            className="search-bar-input"
            placeholder={selectedVault ? `Search ${selectedVault}…` : 'Ask anything…'}
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
          <div className="search-actions">
            {searching && <span className="spinner" style={{ borderTopColor: 'var(--accent)' }} />}
          </div>
        </div>

        {/* Vault picker — proper dropdown matching the search vibe */}
        <div className="vault-picker">
          {loadingStores ? (
            <span className="vault-picker-hint"><span className="spinner" style={{ width: 12, height: 12, marginRight: 6 }} /> loading vaults…</span>
          ) : stores.length === 0 ? (
            <span className="vault-picker-hint">
              No vaults yet — <Link to="/vaults" style={{ color: 'var(--accent-light)' }}>create one</Link>
            </span>
          ) : (
            <VaultDropdown
              stores={stores}
              value={selectedVault}
              onChange={setSelectedVault}
            />
          )}
        </div>
      </div>

      {/* Results */}
      <div style={{ marginTop: 48 }}>
        {!selectedVault && query.trim() && (
          <div className="search-empty-hint">Select a vault to search.</div>
        )}
        {selectedVault && !query.trim() && (
          <div className="search-empty-hint">Type a query to retrieve from <code style={{ color: 'var(--accent-light)' }}>{selectedVault}</code>.</div>
        )}
        {results?.results && results.results.length > 0 && (
          <div className="results-area view-enter">
            <div className="results-meta">
              <h3 style={{ fontSize: 16, fontWeight: 700 }}>{results.count} result{results.count !== 1 ? 's' : ''}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>for "{query}"</p>
            </div>
            <div className="results-masonry">
              {results.results.map((r: any) => <ResultCard key={r.id} result={r} />)}
            </div>
          </div>
        )}
        {selectedVault && query.trim() && results?.results?.length === 0 && !searching && (
          <div className="search-empty-hint">No matches.</div>
        )}
      </div>
    </div>
  );
}

// ─── Vault Dropdown ──────────────────────────────────────────────

function VaultDropdown({
  stores, value, onChange,
}: { stores: VectorStore[]; value: string; onChange: (n: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const selected = stores.find(s => s.name === value);

  return (
    <div className="vault-dd" ref={ref}>
      <button
        type="button"
        className={'vault-dd-trigger' + (open ? ' open' : '')}
        onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="vault-dd-label">Vault</span>
        <span className="vault-dd-value">
          {selected ? selected.name : <span style={{ color: 'var(--text-muted)' }}>Select a vault</span>}
        </span>
        {selected && (
          <span className="vault-dd-count">{selected.count}</span>
        )}
        <svg className="vault-dd-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="vault-dd-panel" role="listbox">
          {stores.map(s => {
            const isSel = s.name === value;
            return (
              <button
                key={s.name}
                type="button"
                role="option"
                aria-selected={isSel}
                className={'vault-dd-option' + (isSel ? ' selected' : '')}
                onClick={() => { onChange(s.name); setOpen(false); }}
              >
                <span className="vault-dd-option-name">{s.name}</span>
                <span className="vault-dd-option-meta">
                  {s.count} embedding{s.count !== 1 ? 's' : ''}
                </span>
                {isSel && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent)' }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Shared Result Card ──────────────────────────────────────────

function ResultCard({ result }: { result: any }) {
  const mod = result.metadata?.modality || 'unknown';
  const fileUrl = result.metadata?.file_url;
  const filename = result.metadata?.filename || 'Untitled';
  const space = result.space || result.metadata?.space;

  return (
    <div className="card">
      <div className="card-rank">{(result.similarity * 100).toFixed(0)}%</div>
      <div className="card-preview">
        {mod === 'image' && fileUrl && <img src={getFileUrl(fileUrl)} alt={filename} className="preview-image" />}
        {mod === 'video' && fileUrl && <video src={getFileUrl(fileUrl)} className="preview-video" controls preload="metadata" />}
        {mod === 'audio' && fileUrl && (
          <div className="preview-audio" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: 20, width: '100%' }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--mod-audio)' }}>
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="23"></line>
              <line x1="8" y1="23" x2="16" y2="23"></line>
            </svg>
            <audio src={getFileUrl(fileUrl)} controls style={{ width: '100%' }} />
          </div>
        )}
        {(mod === 'text' || mod === 'document') && (
          <div className="preview-text" style={{ padding: 24, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55, overflow: 'hidden', height: '100%', boxSizing: 'border-box' }}>
            {(result.document || '').slice(0, 280)}{result.document?.length > 280 ? '…' : ''}
          </div>
        )}
        {mod === 'unknown' && <div className="preview-text" style={{ padding: 24 }}>Unknown format</div>}
      </div>
      <div className="card-footer">
        <span className="filename" title={filename}>{filename}</span>
        <div className="card-meta-row" style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, flexWrap: 'wrap' }}>
          <Pill label={mod} tone={MOD_TONE[mod] || 'neutral'} />
          {space && <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{space}</span>}
          {result.metadata?.page_numbers && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>p.{result.metadata.page_numbers}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DASHBOARD PAGE
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

interface DashStats {
  totalVaults: number;
  totalFiles: number;
  totalEmbeddings: number;
  byModality: Record<string, number>;
}

function DashboardPage({ onToast }: { onToast: ToastFn }) {
  const [stats, setStats] = useState<DashStats | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [list, h] = await Promise.all([getStores(), healthCheck().catch(() => null)]);
        if (!alive) return;
        if (h) setHealth(h);
        // Pull each store's details to derive modality breakdown.
        const detailed = await Promise.all(list.map(s => getStore(s.name).catch(() => null)));
        if (!alive) return;
        const byModality: Record<string, number> = {};
        let totalFiles = 0;
        let totalEmbeddings = 0;
        for (let i = 0; i < detailed.length; i++) {
          const d = detailed[i];
          if (!d) { totalEmbeddings += list[i].count; continue; }
          totalEmbeddings += d.count || 0;
          if (d.files?.length) {
            // group by doc_id to count files (not chunks)
            const seenDocs = new Set<string>();
            for (const f of d.files) {
              const docId = f.metadata?.doc_id || f.id;
              if (seenDocs.has(docId)) continue;
              seenDocs.add(docId);
              const m = (f.metadata?.modality || 'unknown') as string;
              byModality[m] = (byModality[m] || 0) + 1;
              totalFiles++;
            }
          }
        }
        setStats({
          totalVaults: list.length,
          totalFiles,
          totalEmbeddings,
          byModality,
        });
      } catch (e: any) {
        onToast(e.response?.data?.detail || 'Dashboard load failed', 'error');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [onToast]);

  const isHealthy = health?.status === 'healthy';
  const mem = health?.memory || {};
  const memUsed = mem.mps_allocated_mb ?? mem.cuda_allocated_mb ?? null;
  const memReserved = mem.mps_reserved_mb ?? mem.cuda_reserved_mb ?? null;

  return (
    <div className="page-container view-enter">
      <div style={{ marginBottom: 32 }}>
        <p className="section-eyebrow" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 8 }}>Overview</p>
        <h1 className="hero-title" style={{ fontSize: 44, marginBottom: 12, textAlign: 'left' }}>Dashboard</h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: 15, maxWidth: 640 }}>
          A live snapshot of your embedding store.
        </p>
      </div>

      {/* SYSTEM STATUS — one line, always visible */}
      {health && (
        <div className="system-strip">
          <span className={'sys-dot ' + (isHealthy ? 'on' : 'off')} />
          <span className="sys-key">status</span>
          <span className="sys-val">{health.status}</span>
          <span className="sys-sep" />
          <span className="sys-key">device</span>
          <span className="sys-val">{mem.device || '—'}{mem.dtype ? ` · ${mem.dtype}` : ''}</span>
          {memUsed !== null && (
            <>
              <span className="sys-sep" />
              <span className="sys-key">memory</span>
              <span className="sys-val">
                {Math.round(memUsed)} MB{memReserved !== null ? ` / ${Math.round(memReserved)} MB reserved` : ''}
              </span>
            </>
          )}
          <span className="sys-sep" />
          <span className="sys-key">encoder</span>
          <span className="sys-val">{health.perception_encoder ? 'ready' : 'down'}</span>
          <span className="sys-sep" />
          <span className="sys-key">chroma</span>
          <span className="sys-val">{health.chromadb ? 'ready' : 'down'}</span>
        </div>
      )}

      {/* STATS */}
      <section className="dashboard-section">
        {loading ? (
          <div style={{ color: 'var(--text-muted)', padding: 24 }}><span className="spinner" /> Loading stats…</div>
        ) : stats ? (
          <div className="dashboard-stats">
            <StatCard label="Vaults" value={stats.totalVaults} />
            <StatCard label="Files" value={stats.totalFiles} />
            <StatCard label="Embeddings" value={stats.totalEmbeddings} />
            <StatCard
              label="By Modality"
              value={Object.values(stats.byModality).reduce((a, b) => a + b, 0)}
              sub={
                <div className="stat-sub">
                  {Object.entries(stats.byModality).length === 0 && (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>no files</span>
                  )}
                  {Object.entries(stats.byModality).map(([m, n]) => (
                    <Pill key={m} label={`${m} ${n}`} tone={MOD_TONE[m] || 'neutral'} />
                  ))}
                </div>
              }
            />
          </div>
        ) : null}
      </section>

    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: React.ReactNode }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// VAULTS LIST PAGE (/vaults)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function VaultsListPage({ onToast, onChange }: { onToast: ToastFn; onChange: () => void }) {
  const [stores, setStores] = useState<VectorStore[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState<{ key: string; vault: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setStores(await getStores()); }
    catch (e: any) { onToast(e.response?.data?.detail || 'Failed to load vaults', 'error'); }
    finally { setLoading(false); onChange(); }
  }, [onToast, onChange]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (name: string, desc: string) => {
    try {
      const res: CreateStoreResponse = await createStore(name, desc);
      if (res.api_key) {
        saveVaultKey(name, res.api_key);
        setNewKey({ key: res.api_key, vault: name });
      }
      setShowCreate(false);
      await load();
      onToast(`Created "${name}"`);
    } catch (e: any) {
      onToast(e.response?.data?.detail || 'Create failed', 'error');
    }
  };

  return (
    <div className="page-container view-enter">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 48, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <p className="section-eyebrow" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 8 }}>Storage</p>
          <h1 className="hero-title" style={{ fontSize: 56, marginBottom: 12, textAlign: 'left' }}>Vaults</h1>
          <p className="hero-subtitle" style={{ margin: 0, textAlign: 'left' }}>
            Multimodal embedding stores. Drop files in. Search across all of them.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New Vault</button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>
          <span className="spinner" /> Loading vaults...
        </div>
      ) : stores.length === 0 ? (
        <div className="upload-hero" style={{ borderStyle: 'solid' }} onClick={() => setShowCreate(true)}>
          <div className="upload-icon" style={{ fontFamily: 'var(--font-mono)', fontSize: 32, fontWeight: 800 }}>EMPTY</div>
          <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>No vaults yet</h3>
          <p style={{ color: 'var(--text-muted)' }}>Click to create your first vault</p>
        </div>
      ) : (
        <div className="collections-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 24 }}>
          {stores.map(s => <VaultCard key={s.name} store={s} />)}
        </div>
      )}

      {showCreate && <CreateVaultModal onClose={() => setShowCreate(false)} onCreate={handleCreate} />}
      {newKey && (
        <ApiKeyModal
          apiKey={newKey.key}
          vaultName={newKey.vault}
          onClose={() => setNewKey(null)}
        />
      )}
    </div>
  );
}

function VaultCard({ store }: { store: VectorStore }) {
  const desc = store.metadata?.description || 'No description';
  return (
    <div className="collection-card" style={{
      background: 'rgba(10,15,29,0.4)', backdropFilter: 'blur(30px) saturate(140%)',
      border: '1px solid var(--glass-border)', borderRadius: 24, padding: 24,
      display: 'flex', flexDirection: 'column', gap: 16, transition: 'all .3s var(--ease)',
    }}>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8, gap: 12 }}>
          <h3 style={{ fontSize: 20, fontWeight: 700, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{store.name}</h3>
          <Pill label={`${store.count}`} tone="neutral" />
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, minHeight: 36 }}>{desc}</p>
      </div>
      <div style={{ display: 'flex', gap: 10, alignSelf: 'flex-start' }}>
        <Link to={`/vaults/${encodeURIComponent(store.name)}`} className="btn btn-primary">Open →</Link>
        <Link to={`/?vault=${encodeURIComponent(store.name)}`} className="btn btn-outline">Search</Link>
      </div>
    </div>
  );
}

// ─── Create Vault Modal ──────────────────────────────────────────

function CreateVaultModal({ onClose, onCreate }: { onClose: () => void; onCreate: (n: string, d: string) => void }) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);

  return (
    <div className="premium-overlay" onClick={onClose}>
      <form className="premium-modal" onClick={e => e.stopPropagation()} onSubmit={e => { e.preventDefault(); if (name.trim()) onCreate(name.trim(), desc.trim()); }} style={{ padding: 40 }}>
        <h2 style={{ fontSize: 28, marginBottom: 8, fontWeight: 800 }}>New Vault</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14 }}>Create an isolated multimodal embedding store.</p>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13, fontWeight: 600 }}>Name *</label>
          <input
            ref={ref}
            className="premium-input"
            placeholder="e.g. research_papers"
            value={name}
            onChange={e => setName(e.target.value.replace(/[^a-zA-Z0-9_-]/g, ''))}
            required
          />
        </div>

        <div style={{ marginBottom: 32 }}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13, fontWeight: 600 }}>Description (optional)</label>
          <input
            className="premium-input"
            placeholder="What's stored here?"
            value={desc}
            onChange={e => setDesc(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!name.trim()}>Create Vault</button>
        </div>
      </form>
    </div>
  );
}

// ─── API Key Modal (one-time display) ────────────────────────────

function ApiKeyModal({ apiKey, vaultName, onClose }: { apiKey: string; vaultName: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="premium-overlay">
      <div className="premium-modal" onClick={e => e.stopPropagation()} style={{ padding: 40 }}>
        <h2 style={{ fontSize: 26, marginBottom: 8, fontWeight: 800 }}>API Key for "{vaultName}"</h2>
        <div style={{ background: 'rgba(255,200,50,0.08)', border: '1px solid rgba(255,200,50,0.25)', borderRadius: 10, padding: '12px 16px', marginBottom: 20 }}>
          <p style={{ margin: 0, fontSize: 13, color: 'rgba(255,200,50,0.9)', fontWeight: 600 }}>
            Save this key now — it cannot be retrieved later.
          </p>
        </div>
        <div style={{ background: 'var(--bg-root)', borderRadius: 10, padding: '14px 18px', marginBottom: 20, border: '1px solid var(--border)' }}>
          <code style={{ fontSize: 13, color: 'var(--accent)', wordBreak: 'break-all', fontFamily: 'var(--font-mono)' }}>{apiKey}</code>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 24, lineHeight: 1.6 }}>
          Use this in the <code style={{ color: 'var(--accent)' }}>X-API-Key</code> header for embed/search calls. We've stored it locally so the UI can use it.
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <button className="btn btn-outline" onClick={copy}>{copied ? 'Copied!' : 'Copy Key'}</button>
          <button className="btn btn-primary" onClick={onClose}>I've saved it</button>
        </div>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// VAULT DETAIL PAGE (/vaults/:name)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function VaultDetailPage({ onToast }: { onToast: ToastFn }) {
  const { name = '' } = useParams();
  const navigate = useNavigate();
  const [vault, setVault] = useState<VectorStore | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const v = await getStore(name);
      setVault(v);
    } catch (e: any) {
      onToast(e.response?.data?.detail || `Vault "${name}" not found`, 'error');
    } finally {
      setLoading(false);
    }
  }, [name, onToast]);

  useEffect(() => {
    load();
  }, [load, name]);

  const handleDeleteVault = async () => {
    if (!window.confirm(`Delete vault "${name}" and ALL its embeddings? This cannot be undone.`)) return;
    try {
      await deleteStore(name);
      removeVaultKey(name);
      onToast(`Deleted "${name}"`);
      navigate('/vaults');
    } catch (e: any) {
      onToast(e.response?.data?.detail || 'Delete failed', 'error');
    }
  };

  if (loading) {
    return (
      <div className="page-container view-enter" style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>
        <span className="spinner" /> Loading vault...
      </div>
    );
  }

  if (!vault) {
    return (
      <div className="page-container view-enter" style={{ textAlign: 'center', padding: 80 }}>
        <h2 style={{ fontSize: 28, marginBottom: 16 }}>Vault not found</h2>
        <Link to="/vaults" className="btn btn-primary">← Back to Vaults</Link>
      </div>
    );
  }

  return (
    <div className="page-container view-enter">
      <Link to="/vaults" className="btn btn-outline" style={{ marginBottom: 24 }}>← All Vaults</Link>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32, gap: 24, flexWrap: 'wrap' }}>
        <div>
          <h1 className="hero-title" style={{ fontSize: 44, marginBottom: 8, textAlign: 'left' }}>{vault.name}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Pill label={`${vault.count} embedding${vault.count !== 1 ? 's' : ''}`} tone="accent" />
            {vault.metadata?.description && (
              <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{vault.metadata.description}</span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Link to={`/?vault=${encodeURIComponent(vault.name)}`} className="btn btn-outline">Search this vault</Link>
          <button className="btn btn-danger" onClick={handleDeleteVault}>Delete Vault</button>
        </div>
      </div>

      <ConnectPanel vaultName={vault.name} />

      <UploadPanel
        vaultName={vault.name}
        onSuccess={() => { load(); onToast('Embedded successfully'); }}
        onError={m => onToast(m, 'error')}
      />

      <FileList
        vault={vault}
        onDelete={async (docId, filename) => {
          if (!window.confirm(`Remove "${filename}" from this vault?`)) return;
          try {
            await deleteDocument(vault.name, docId);
            await load();
            onToast(`Removed "${filename}"`);
          } catch (e: any) {
            onToast(e.response?.data?.detail || 'Delete failed', 'error');
          }
        }}
      />

    </div>
  );
}

// ─── Connect Panel (curl / python / mcp snippets) ───────────────

function ConnectPanel({ vaultName }: { vaultName: string }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<'curl' | 'python' | 'mcp'>('curl');
  const [copied, setCopied] = useState(false);
  const [apiKey, setApiKey] = useState<string>(() => getVaultKey(vaultName));
  const base = getApiBase();

  // Auto-issue a fresh key the first time the panel opens with no local key.
  useEffect(() => {
    if (!open || apiKey) return;
    let cancelled = false;
    rotateVaultKey(vaultName).then(k => { if (!cancelled) setApiKey(k); }).catch(() => {});
    return () => { cancelled = true; };
  }, [open, apiKey, vaultName]);

  const snippets: Record<string, string> = {
    curl: `curl -X POST ${base}/api/search \\
  -H "X-API-Key: ${apiKey}" \\
  -F "vector_store=${vaultName}" \\
  -F "query=your question here" \\
  -F "n_results=5"`,
    python: `import httpx

with httpx.Client() as client:
    r = client.post(
        "${base}/api/search",
        headers={"X-API-Key": "${apiKey}"},
        data={
            "vector_store": "${vaultName}",
            "query": "your question here",
            "n_results": 5,
        },
    )
    for hit in r.json()["results"]:
        print(f"{hit['similarity']:.2f}  {hit['metadata']['filename']}")`,
    mcp: `// Add to your MCP client config:
{
  "mcpServers": {
    "embed": {
      "command": "uvx",
      "args": ["--from", "/absolute/path/to/EMBEd/mcp", "embed-mcp"],
      "env": { "EMBED_BASE_URL": "${base}" }
    }
  }
}
// Then save your per-vault key into ~/.config/embed-mcp/keys.json
// {"${vaultName}": "${apiKey}"}`,
  };

  const copy = () => {
    navigator.clipboard.writeText(snippets[tab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{ marginBottom: 32, border: '1px solid var(--glass-border)', borderRadius: 16, background: 'rgba(10,15,29,0.4)', overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '16px 20px', background: 'transparent', border: 'none', cursor: 'pointer',
          color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', fontSize: 14, fontWeight: 600,
        }}
      >
        <span>Connect <span style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>– curl, Python, MCP</span></span>
        <span style={{ color: 'var(--text-muted)' }}>{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div style={{ borderTop: '1px solid var(--border-subtle)', padding: 16 }}>
          <div className="snippet-tabs" style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
            {(['curl', 'python', 'mcp'] as const).map(t => (
              <button
                key={t}
                className={tab === t ? 'active' : ''}
                onClick={() => setTab(t)}
                style={{
                  background: tab === t ? 'var(--bg-hover)' : 'none',
                  color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)',
                  border: 'none', padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                  fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1,
                }}
              >
                {t === 'mcp' ? 'MCP' : t}
              </button>
            ))}
            <button className="btn btn-outline" style={{ marginLeft: 'auto', padding: '4px 14px', fontSize: 11 }} onClick={copy}>
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          <pre style={{
            background: 'var(--bg-root)', borderRadius: 8, padding: 16,
            fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent)',
            lineHeight: 1.6, overflow: 'auto', margin: 0,
          }}>{snippets[tab]}</pre>
        </div>
      )}
    </div>
  );
}

// ─── Upload Panel (drag + drop) ──────────────────────────────────

function UploadPanel({ vaultName, onSuccess, onError }: { vaultName: string; onSuccess: () => void; onError: (m: string) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = '.txt,.md,.jpg,.jpeg,.png,.gif,.webp,.mp4,.mov,.mp3,.wav,.flac,.m4a,.ogg,.pdf';

  const addFiles = (incoming: File[]) => {
    const ok = incoming.filter(f => (f.name.split('.').pop()?.toLowerCase() || '') in EXT_MOD);
    if (ok.length < incoming.length) onError(`${incoming.length - ok.length} unsupported file(s) skipped`);
    setFiles(prev => [...prev, ...ok]);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    addFiles(Array.from(e.dataTransfer.files));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async () => {
    if (!files.length) return;
    setUploading(true);
    try {
      if (files.length === 1) await embedFile(vaultName, files[0]);
      else await embedBatch(vaultName, files);
      setFiles([]);
      onSuccess();
    } catch (e: any) {
      onError(e.response?.data?.detail || 'Upload failed');
    } finally { setUploading(false); }
  };

  return (
    <div style={{ marginBottom: 32 }}>
      <div
        className="upload-hero"
        style={{
          padding: '60px 40px', marginBottom: files.length ? 16 : 32,
          borderColor: dragOver ? 'var(--accent)' : undefined,
          background: dragOver ? 'rgba(13,204,242,0.05)' : undefined,
        }}
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept={accept}
          onChange={e => { if (e.target.files) addFiles(Array.from(e.target.files)); }}
        />
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="upload-icon" style={{ marginBottom: 20 }}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
          {dragOver ? 'Drop to add' : 'Drag files here'}
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>or click to browse · text, image, audio, video, PDF</p>
      </div>

      {files.length > 0 && (
        <div className="file-queue view-enter" style={{ background: 'rgba(10,15,29,0.4)', border: '1px solid var(--glass-border)', borderRadius: 16, padding: 20 }}>
          <div className="file-queue-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700 }}>{files.length} file{files.length > 1 ? 's' : ''} ready</h4>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-outline" onClick={() => setFiles([])}>Clear</button>
              <button className="btn btn-primary" disabled={uploading} onClick={submit}>
                {uploading ? <><span className="spinner" /> Embedding...</> : 'Embed'}
              </button>
            </div>
          </div>
          <div className="queue-list" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {files.map((f, i) => (
              <div key={i} className="queue-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                  <Pill label={getMod(f.name)} tone={MOD_TONE[getMod(f.name)] || 'neutral'} />
                  <span style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{fmtSize(f.size)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── File List ───────────────────────────────────────────────────

interface FileGroup {
  doc_id: string;
  filename: string;
  modality: string;
  chunk_count: number;
  size_bytes: number;
}

function groupFiles(files: StoreFile[]): FileGroup[] {
  const groups: Record<string, FileGroup> = {};
  for (const f of files) {
    const id = f.metadata?.doc_id || f.id;
    if (!groups[id]) {
      groups[id] = {
        doc_id: id,
        filename: f.metadata?.filename || 'Unknown',
        modality: f.metadata?.modality || 'unknown',
        chunk_count: 0,
        size_bytes: Number(f.metadata?.size_bytes || 0),
      };
    }
    groups[id].chunk_count++;
  }
  return Object.values(groups);
}

function FileList({ vault, onDelete }: { vault: VectorStore; onDelete: (docId: string, filename: string) => void }) {
  const docs = vault.files ? groupFiles(vault.files) : [];
  if (docs.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 14 }}>
        No files yet. Drop some above.
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 32 }}>
      <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Files ({docs.length})
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {docs.map(d => (
          <div key={d.doc_id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', background: 'rgba(10,15,29,0.4)',
            border: '1px solid var(--glass-border)', borderRadius: 12,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
              <Pill label={d.modality} tone={MOD_TONE[d.modality] || 'neutral'} />
              <span style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={d.filename}>
                {d.filename}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {d.size_bytes > 0 && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{fmtSize(d.size_bytes)}</span>
              )}
              <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {d.chunk_count} chunk{d.chunk_count !== 1 ? 's' : ''}
              </span>
              <Pill label="indexed" tone="success" />
              <button
                onClick={() => onDelete(d.doc_id, d.filename)}
                style={{ background: 'none', border: 'none', color: 'var(--error)', cursor: 'pointer', fontSize: 13, padding: '4px 10px' }}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

