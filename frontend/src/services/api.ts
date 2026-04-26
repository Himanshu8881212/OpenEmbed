import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const ADMIN_KEY = process.env.REACT_APP_ADMIN_API_KEY || '';

const api = axios.create({ baseURL: API_BASE_URL });

// Default header (admin) for store-management calls
api.interceptors.request.use((config) => {
  if (ADMIN_KEY && !config.headers['X-API-Key']) {
    config.headers['X-API-Key'] = ADMIN_KEY;
  }
  return config;
});

// ── localStorage helpers for per-vault keys ──────────────
const KEY_PREFIX = 'embed.vaultKey.';
export const saveVaultKey = (name: string, apiKey: string) => {
  try { localStorage.setItem(KEY_PREFIX + name, apiKey); } catch { }
};
export const getVaultKey = (name: string): string => {
  try { return localStorage.getItem(KEY_PREFIX + name) || ''; } catch { return ''; }
};
export const removeVaultKey = (name: string) => {
  try { localStorage.removeItem(KEY_PREFIX + name); } catch { }
};

const vaultHeaders = (name: string) => {
  const k = getVaultKey(name);
  return k ? { 'X-API-Key': k } : undefined;
};

// ── Types ───────────────────────────────────────────────

export interface VectorStore {
  name: string;
  count: number;
  metadata?: Record<string, any>;
  files?: StoreFile[];
}

export interface StoreFile {
  id: string;
  metadata: Record<string, any>;
}

export interface SearchResult {
  id: string;
  similarity: number;
  distance: number;
  metadata: Record<string, any>;
  document: string;
  space?: string;
}

export interface CreateStoreResponse {
  success: boolean;
  store: VectorStore;
  api_key: string;
  warning: string;
}

// ── Stores (admin / dev-mode) ───────────────────────────

export const getStores = async (): Promise<VectorStore[]> => {
  const res = await api.get('/api/stores');
  return res.data.stores || [];
};

export const getStore = async (name: string): Promise<VectorStore> => {
  const res = await api.get(`/api/stores/${name}`);
  return res.data;
};

export const createStore = async (name: string, description: string = ''): Promise<CreateStoreResponse> => {
  const form = new FormData();
  form.append('name', name);
  form.append('description', description);
  const res = await api.post('/api/stores', form);
  return res.data;
};

export const deleteStore = async (name: string): Promise<void> => {
  await api.delete(`/api/stores/${name}`);
};

export const rotateVaultKey = async (name: string): Promise<string> => {
  const existing = getVaultKey(name);
  const headers: Record<string, string> = {};
  if (existing) headers['X-API-Key'] = existing;
  const res = await api.post(`/api/stores/${name}/rotate-key`, undefined, { headers });
  const key = res.data.api_key as string;
  saveVaultKey(name, key);
  return key;
};

export const deleteDocument = async (storeName: string, docId: string): Promise<any> => {
  const res = await api.delete(`/api/stores/${storeName}/documents/${docId}`);
  return res.data;
};

// ── Embed (per-vault key) ───────────────────────────────

export const embedFile = async (store: string, file: File): Promise<any> => {
  const form = new FormData();
  form.append('vector_store', store);
  form.append('file', file);
  const res = await api.post('/api/embed', form, { headers: vaultHeaders(store) });
  return res.data;
};

export const embedBatch = async (store: string, files: File[]): Promise<any> => {
  const form = new FormData();
  form.append('vector_store', store);
  files.forEach(f => form.append('files', f));
  const res = await api.post('/api/embed/batch', form, { headers: vaultHeaders(store) });
  return res.data;
};

// ── Search (per-vault key) ──────────────────────────────

export const searchText = async (store: string, query: string, nResults: number = 20, minSimilarity: number = 0.0): Promise<any> => {
  const form = new FormData();
  form.append('vector_store', store);
  form.append('query', query);
  form.append('n_results', nResults.toString());
  form.append('min_similarity', minSimilarity.toString());
  const res = await api.post('/api/search', form, { headers: vaultHeaders(store) });
  return res.data;
};

export const searchFile = async (store: string, file: File, nResults: number = 20, minSimilarity: number = 0.0): Promise<any> => {
  const form = new FormData();
  form.append('vector_store', store);
  form.append('file', file);
  form.append('n_results', nResults.toString());
  form.append('min_similarity', minSimilarity.toString());
  const res = await api.post('/api/search', form, { headers: vaultHeaders(store) });
  return res.data;
};

// ── Health ──────────────────────────────────────────────

export const healthCheck = async (): Promise<any> => {
  const res = await api.get('/api/health');
  return res.data;
};

// ── Formats ─────────────────────────────────────────────

export const getFormats = async (): Promise<Record<string, string[]>> => {
  const res = await api.get('/api/formats');
  return res.data.formats || {};
};

// ── File URL helper ─────────────────────────────────────
//
// File URLs are stored in chunk metadata as either:
//   - `/api/files/{store}/{name}`  (current auth-gated form)
//   - `/uploads/{store}/{name}`    (legacy public form, rewritten on the fly)
// Img/video tags can't send headers, so we append `?api_key=...` so the
// backend's extract_api_key() picks it up from the query param.

export const getFileUrl = (fileUrl: string): string => {
  // Rewrite legacy public path → auth-gated path
  let path = fileUrl.startsWith('/uploads/')
    ? '/api/files/' + fileUrl.slice('/uploads/'.length)
    : fileUrl;

  // Pull store name from /api/files/{store}/{name}
  const m = path.match(/^\/api\/files\/([^/]+)\//);
  if (m) {
    const key = getVaultKey(m[1]) || ADMIN_KEY;
    if (key) {
      const sep = path.includes('?') ? '&' : '?';
      path = `${path}${sep}api_key=${encodeURIComponent(key)}`;
    }
  }
  return `${API_BASE_URL}${path}`;
};

export const getApiBase = (): string => API_BASE_URL;

export default api;
