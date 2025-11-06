import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface VectorStore {
  name: string;
  count: number;
  metadata?: any;
}

export interface EmbeddedFile {
  id: string;
  filename: string;
  modality: string;
  timestamp: string;
  metadata?: any;
}

// Get all vector stores
export const getVectorStores = async (): Promise<VectorStore[]> => {
  const response = await api.get('/api/vector-stores');
  // API returns {stores: [...], total: number}
  return response.data.stores || [];
};

// Get files in a vector store
export const getVectorStoreFiles = async (storeName: string): Promise<EmbeddedFile[]> => {
  const response = await api.get(`/api/vector-stores/${storeName}/files`);
  return response.data;
};

// Upload file and generate embedding
export const uploadFile = async (
  file: File,
  modality: string,
  vectorStore: string,
  createNew: boolean = false
): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('modality', modality);
  formData.append('vector_store', vectorStore);
  formData.append('create_new', createNew.toString());

  const response = await api.post('/api/embed', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// Delete a vector store
export const deleteVectorStore = async (storeName: string): Promise<void> => {
  await api.delete(`/api/vector-stores/${storeName}`);
};

// Search in vector store
export const searchVectorStore = async (
  storeName: string,
  query: string,
  modality: string,
  topK: number = 5
): Promise<any> => {
  const response = await api.post(`/api/vector-stores/${storeName}/search`, {
    query,
    modality,
    top_k: topK,
  });
  return response.data;
};

// Health check
export const healthCheck = async (): Promise<any> => {
  const response = await api.get('/health');
  return response.data;
};

export default api;

