// EMBEd - Multi-Modal Embedding Application
// Frontend JavaScript

const API_BASE = '/api';

// Global state
let currentStores = [];
let uploadedFileId = null;
let searchFileId = null;

// Utility Functions
function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function showStatus(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `status-message ${type}`;
    element.style.display = 'block';

    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Vector Store Functions
async function loadVectorStores() {
    try {
        const response = await fetch(`${API_BASE}/vector-stores`);
        const data = await response.json();

        currentStores = data.stores;
        renderStoresList(data.stores);
        updateStoreSelectors(data.stores);
    } catch (error) {
        console.error('Error loading vector stores:', error);
        document.getElementById('stores-list').innerHTML = '<p class="error">Failed to load vector stores</p>';
    }
}

function renderStoresList(stores) {
    const container = document.getElementById('stores-list');

    if (stores.length === 0) {
        container.innerHTML = '<p class="loading">No vector stores found. Create one to get started!</p>';
        return;
    }

    container.innerHTML = stores.map(store => `
        <div class="store-card">
            <h3>${store.name}</h3>
            <p>${store.description || 'No description'}</p>
            <div class="store-meta">
                <span class="store-count">${store.count} embeddings</span>
                <button class="btn btn-danger" onclick="deleteStore('${store.name}')">Delete</button>
            </div>
            <p style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 10px;">
                Created: ${formatDate(store.created_at)}
            </p>
        </div>
    `).join('');
}

function updateStoreSelectors(stores) {
    const selectors = ['vector-store-select', 'search-vector-store'];

    selectors.forEach(selectorId => {
        const selector = document.getElementById(selectorId);
        selector.innerHTML = '<option value="">-- Select Vector Store --</option>';

        stores.forEach(store => {
            const option = document.createElement('option');
            option.value = store.name;
            option.textContent = `${store.name} (${store.count} embeddings)`;
            selector.appendChild(option);
        });
    });
}

async function createVectorStore(name, description) {
    try {
        showLoading();

        const response = await fetch(`${API_BASE}/vector-stores`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description || null
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create vector store');
        }

        await loadVectorStores();
        hideLoading();
        return true;
    } catch (error) {
        hideLoading();
        alert('Error: ' + error.message);
        return false;
    }
}

async function deleteStore(name) {
    if (!confirm(`Are you sure you want to delete vector store "${name}"?`)) {
        return;
    }

    try {
        showLoading();

        const response = await fetch(`${API_BASE}/vector-stores/${name}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete vector store');
        }

        await loadVectorStores();
        hideLoading();
    } catch (error) {
        hideLoading();
        alert('Error: ' + error.message);
    }
}

// File Upload Functions
async function uploadFile(file, modality) {
    try {
        showLoading();

        const formData = new FormData();
        formData.append('file', file);
        formData.append('modality', modality);

        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to upload file');
        }

        const data = await response.json();
        hideLoading();
        return data;
    } catch (error) {
        hideLoading();
        throw error;
    }
}

async function generateEmbedding(fileId, modality, vectorStore, textContent = null) {
    try {
        showLoading();

        const requestBody = {
            vector_store_name: vectorStore,
            operation: 'use_existing',
            modality: modality,
            file_id: fileId,
            text_content: textContent,
            metadata: {
                uploaded_at: new Date().toISOString()
            }
        };

        const response = await fetch(`${API_BASE}/embeddings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate embedding');
        }

        const data = await response.json();
        hideLoading();
        return data;
    } catch (error) {
        hideLoading();
        throw error;
    }
}

// Search Functions
async function searchSimilar(vectorStore, queryModality, queryFileId, queryText, nResults) {
    try {
        showLoading();

        const requestBody = {
            vector_store_name: vectorStore,
            query_modality: queryModality,
            query_file_id: queryFileId,
            query_text: queryText,
            n_results: parseInt(nResults),
            include_metadata: true
        };

        const response = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Search failed');
        }

        const data = await response.json();
        hideLoading();
        return data;
    } catch (error) {
        hideLoading();
        throw error;
    }
}

function renderSearchResults(results) {
    const container = document.getElementById('search-results');

    if (results.length === 0) {
        container.innerHTML = '<p class="loading">No results found</p>';
        return;
    }

    container.innerHTML = `
        <h3>Found ${results.length} similar embeddings</h3>
        ${results.map(result => `
            <div class="result-card">
                <div class="result-header">
                    <span class="result-id">ID: ${result.id}</span>
                    <span class="result-distance">Distance: ${result.distance.toFixed(4)}</span>
                </div>
                ${result.metadata ? `
                    <div class="result-metadata">
                        <strong>Modality:</strong> ${result.metadata.modality}<br>
                        ${result.metadata.filename ? `<strong>Filename:</strong> ${result.metadata.filename}<br>` : ''}
                        ${result.metadata.added_at ? `<strong>Added:</strong> ${formatDate(result.metadata.added_at)}` : ''}
                    </div>
                ` : ''}
            </div>
        `).join('')}
    `;
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    loadVectorStores();

    // Modal handlers
    const modal = document.getElementById('create-store-modal');
    const btnCreateStore = document.getElementById('btn-create-store');
    const btnCancel = document.getElementById('btn-cancel-create');
    const closeBtn = document.querySelector('.close');

    btnCreateStore.onclick = () => modal.style.display = 'block';
    btnCancel.onclick = () => modal.style.display = 'none';
    closeBtn.onclick = () => modal.style.display = 'none';
    window.onclick = (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    };

    // Create store form
    document.getElementById('create-store-form').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('store-name').value;
        const description = document.getElementById('store-description').value;

        const success = await createVectorStore(name, description);
        if (success) {
            modal.style.display = 'none';
            document.getElementById('create-store-form').reset();
        }
    };

    // Refresh stores
    document.getElementById('btn-refresh-stores').onclick = loadVectorStores;

    // Modality selection for upload
    document.getElementById('modality').onchange = function() {
        const modality = this.value;
        const textGroup = document.getElementById('text-input-group');
        const fileGroup = document.getElementById('file-input-group');
        const generateBtn = document.getElementById('btn-generate-embedding');

        if (modality === 'text') {
            textGroup.style.display = 'block';
            fileGroup.style.display = 'none';
        } else if (modality) {
            textGroup.style.display = 'none';
            fileGroup.style.display = 'block';
        } else {
            textGroup.style.display = 'none';
            fileGroup.style.display = 'none';
        }

        updateGenerateButton();
    };

    // File selection
    document.getElementById('file-input').onchange = function() {
        const file = this.files[0];
        if (file) {
            document.getElementById('file-info').textContent =
                `Selected: ${file.name} (${formatFileSize(file.size)})`;
            updateGenerateButton();
        }
    };

    // Vector store selection
    document.getElementById('vector-store-select').onchange = updateGenerateButton;

    // Generate embedding button
    document.getElementById('btn-generate-embedding').onclick = async function() {
        const modality = document.getElementById('modality').value;
        const vectorStore = document.getElementById('vector-store-select').value;

        try {
            let fileId = null;
            let textContent = null;

            if (modality === 'text') {
                textContent = document.getElementById('text-content').value;
                fileId = 'text-' + Date.now(); // Dummy ID for text
            } else {
                const file = document.getElementById('file-input').files[0];
                const uploadResult = await uploadFile(file, modality);
                fileId = uploadResult.file_id;
                showStatus('upload-status', `File uploaded: ${uploadResult.filename}`, 'success');
            }

            const result = await generateEmbedding(fileId, modality, vectorStore, textContent);
            showStatus('upload-status',
                `Embedding generated successfully! ID: ${result.embedding_id}`, 'success');

            // Reset form
            document.getElementById('modality').value = '';
            document.getElementById('text-content').value = '';
            document.getElementById('file-input').value = '';
            document.getElementById('file-info').textContent = '';
            document.getElementById('text-input-group').style.display = 'none';
            document.getElementById('file-input-group').style.display = 'none';
            updateGenerateButton();

            // Reload stores to update counts
            loadVectorStores();

        } catch (error) {
            showStatus('upload-status', 'Error: ' + error.message, 'error');
        }
    };

    // Search modality selection
    document.getElementById('search-modality').onchange = function() {
        const modality = this.value;
        const textGroup = document.getElementById('search-text-group');
        const fileGroup = document.getElementById('search-file-group');

        if (modality === 'text') {
            textGroup.style.display = 'block';
            fileGroup.style.display = 'none';
        } else if (modality) {
            textGroup.style.display = 'none';
            fileGroup.style.display = 'block';
        } else {
            textGroup.style.display = 'none';
            fileGroup.style.display = 'none';
        }

        updateSearchButton();
    };

    // Search vector store selection
    document.getElementById('search-vector-store').onchange = updateSearchButton;

    // Search file selection
    document.getElementById('search-file').onchange = updateSearchButton;

    // Search text input
    document.getElementById('search-text').oninput = updateSearchButton;

    // Search button
    document.getElementById('btn-search').onclick = async function() {
        const vectorStore = document.getElementById('search-vector-store').value;
        const modality = document.getElementById('search-modality').value;
        const nResults = document.getElementById('search-results-count').value;

        try {
            let fileId = null;
            let queryText = null;

            if (modality === 'text') {
                queryText = document.getElementById('search-text').value;
            } else {
                const file = document.getElementById('search-file').files[0];
                const uploadResult = await uploadFile(file, modality);
                fileId = uploadResult.file_id;
            }

            const results = await searchSimilar(vectorStore, modality, fileId, queryText, nResults);
            renderSearchResults(results.results);

        } catch (error) {
            document.getElementById('search-results').innerHTML =
                `<p class="status-message error">Error: ${error.message}</p>`;
        }
    };
});

function updateGenerateButton() {
    const modality = document.getElementById('modality').value;
    const vectorStore = document.getElementById('vector-store-select').value;
    const generateBtn = document.getElementById('btn-generate-embedding');

    let enabled = false;

    if (modality && vectorStore) {
        if (modality === 'text') {
            const text = document.getElementById('text-content').value;
            enabled = text.trim().length > 0;
        } else {
            const file = document.getElementById('file-input').files[0];
            enabled = file !== undefined;
        }
    }

    generateBtn.disabled = !enabled;
}

function updateSearchButton() {
    const vectorStore = document.getElementById('search-vector-store').value;
    const modality = document.getElementById('search-modality').value;
    const searchBtn = document.getElementById('btn-search');

    let enabled = false;

    if (vectorStore && modality) {
        if (modality === 'text') {
            const text = document.getElementById('search-text').value;
            enabled = text.trim().length > 0;
        } else {
            const file = document.getElementById('search-file').files[0];
            enabled = file !== undefined;
        }
    }

    searchBtn.disabled = !enabled;
}
