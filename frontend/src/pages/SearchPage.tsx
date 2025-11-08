import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Paper,
  IconButton,
  Tooltip,
  CardMedia,
} from '@mui/material';
import {
  Search,
  TextFields,
  ImageOutlined,
  VideoLibrary,
  AudioFile,
  Terrain,
  Thermostat,
  CloudUpload,
  Clear,
  Download,
  Insights,
  Sensors,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import axios from 'axios';

const MotionBox = motion(Box);

interface VectorStore {
  name: string;
  modality: string;
  count: number;
}

interface SearchResult {
  id: string;
  file_path: string;
  modality: string;
  similarity?: number;
  metadata?: any;
}

const modalityConfig = [
  { name: 'Text', icon: <TextFields />, value: 'text' },
  { name: 'Image', icon: <ImageOutlined />, value: 'image' },
  { name: 'Video', icon: <VideoLibrary />, value: 'video' },
  { name: 'Audio', icon: <AudioFile />, value: 'audio' },
  { name: 'Depth', icon: <Terrain />, value: 'depth' },
  { name: 'Thermal', icon: <Thermostat />, value: 'thermal' },
  { name: 'IMU', icon: <Sensors />, value: 'imu' },
];

const SearchPage: React.FC = () => {
  const [stores, setStores] = useState<VectorStore[]>([]);
  const [textQuery, setTextQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchStores();
  }, []);

  const fetchStores = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/vector-stores');
      setStores(response.data.stores);
    } catch (error) {
      console.error('Failed to fetch stores:', error);
      setError('Failed to load vector stores');
    }
  };

  const handleSearch = async () => {
    // Validate input - need at least text or file
    if (!textQuery.trim() && !selectedFile) {
      setError('Please enter text or select a file to search');
      return;
    }

    setLoading(true);
    setError('');
    setResults([]);

    try {
      // Search across ALL stores and aggregate results
      const allResults: SearchResult[] = [];

      for (const store of stores) {
        try {
          let storeResults: SearchResult[] = [];

          // If we have text query, search with text
          if (textQuery.trim()) {
            const response = await axios.post('http://localhost:8000/api/search-by-id', {
              vector_store_name: store.name,
              query_text: textQuery,
              query_modality: 'text',
              n_results: 5,
            });
            storeResults = response.data.results || [];
          }

          // If we have a file, search with file
          if (selectedFile) {
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('vector_store', store.name);
            formData.append('n_results', '5');

            const response = await axios.post('http://localhost:8000/api/search', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
            });

            // Merge file results with text results
            const fileResults = response.data.results || [];
            storeResults = [...storeResults, ...fileResults];
          }

          // Add store results to all results
          allResults.push(...storeResults);
        } catch (storeError) {
          console.error(`Search failed for store ${store.name}:`, storeError);
          // Continue with other stores even if one fails
        }
      }

      // Sort all results by similarity (descending) and take top 20
      const sortedResults = allResults
        .sort((a, b) => (b.similarity || 0) - (a.similarity || 0))
        .slice(0, 20);

      setResults(sortedResults);

      if (sortedResults.length === 0) {
        setError('No results found across any vector stores');
      }
    } catch (error: any) {
      console.error('Search failed:', error);
      setError(error.response?.data?.detail || 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0];
      setSelectedFile(file);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
  };

  const getModalityIcon = (modality: string) => {
    if (!modality) return <Insights />;
    const config = modalityConfig.find(m => m.value === modality.toLowerCase());
    return config?.icon || <Insights />;
  };

  const renderResultPreview = (result: SearchResult) => {
    const modality = result.modality.toLowerCase();

    if (modality === 'image') {
      return (
        <CardMedia
          component="img"
          height="150"
          image={`http://localhost:8000${result.file_path}`}
          alt="Result"
          sx={{ objectFit: 'cover' }}
        />
      );
    } else if (modality === 'video') {
      return (
        <CardMedia
          component="video"
          height="150"
          controls
          src={`http://localhost:8000${result.file_path}`}
          sx={{ objectFit: 'cover' }}
        />
      );
    } else if (modality === 'audio') {
      return (
        <Box sx={{ p: 2, bgcolor: 'background.paper' }}>
          <audio controls style={{ width: '100%' }}>
            <source src={`http://localhost:8000${result.file_path}`} />
          </audio>
        </Box>
      );
    } else {
      return (
        <Box
          sx={{
            height: 150,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ textAlign: 'center', color: 'text.secondary' }}>
            {getModalityIcon(modality)}
            <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
              {modality.toUpperCase()}
            </Typography>
          </Box>
        </Box>
      );
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, borderBottom: '1px solid', borderColor: 'divider', pb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Search
        </Typography>
      </Box>

      <Box sx={{ maxWidth: 900, mx: 'auto' }}>
        <Card sx={{ mb: 4, border: '1px solid', borderColor: 'divider' }}>
          <CardContent sx={{ p: 3 }}>
            <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
              Search across all vector stores • Use text, file, or both
            </Typography>

            <TextField
              fullWidth
              multiline
              rows={2}
              placeholder="Enter text query (optional)..."
              value={textQuery}
              onChange={(e) => setTextQuery(e.target.value)}
              sx={{ mb: 3 }}
            />

            <Box sx={{ mb: 3 }}>
              <input
                accept="*/*"
                style={{ display: 'none' }}
                id="search-file-upload"
                type="file"
                onChange={handleFileSelect}
              />
              {!selectedFile ? (
                <label htmlFor="search-file-upload">
                  <Paper
                    component="span"
                    sx={{
                      p: 3,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      cursor: 'pointer',
                      border: '2px dashed',
                      borderColor: 'divider',
                      bgcolor: 'background.paper',
                    }}
                  >
                    <CloudUpload sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
                    <Typography variant="body2">
                      Click to upload file (optional)
                    </Typography>
                  </Paper>
                </label>
              ) : (
                <Paper sx={{ p: 2, border: '1px solid', borderColor: 'divider' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {selectedFile.name}
                      </Typography>
                    </Box>
                    <IconButton size="small" onClick={clearFile}>
                      <Clear />
                    </IconButton>
                  </Box>
                </Paper>
              )}
            </Box>

            <Button
              fullWidth
              variant="contained"
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <Search />}
              onClick={handleSearch}
              disabled={loading}
            >
              {loading ? 'Searching...' : 'Search'}
            </Button>

            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Search Results */}
        {results.length === 0 && !loading && !error && (
          <MotionBox
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            sx={{
              mt: 6,
              textAlign: 'center',
              py: 8,
              color: 'text.secondary',
            }}
          >
            <Search sx={{ fontSize: 80, opacity: 0.2, mb: 2 }} />
            <Typography variant="h5" sx={{ mb: 1, fontWeight: 600 }}>
              Ready to search
            </Typography>
            <Typography variant="body1">
              Enter text or upload a file to search across all vector stores
            </Typography>
          </MotionBox>
        )}

        {results.length > 0 && (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              {results.length} results
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }, gap: 2 }}>
              {results.map((result) => (
                <Card
                  key={result.id}
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  {renderResultPreview(result)}
                  <CardContent sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        {result.modality}
                      </Typography>
                      {result.similarity !== undefined && (
                        <Typography variant="caption" color="text.secondary">
                          {(result.similarity * 100).toFixed(0)}%
                        </Typography>
                      )}
                    </Box>
                    <Tooltip title={result.file_path || result.metadata?.filename || 'Unknown file'}>
                      <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                        {result.file_path ? result.file_path.split('/').pop() : result.metadata?.filename || result.id}
                      </Typography>
                    </Tooltip>
                    {result.file_path && (
                      <Button
                        fullWidth
                        size="small"
                        variant="outlined"
                        startIcon={<Download />}
                        href={`http://localhost:8000${result.file_path}`}
                        download
                        sx={{ mt: 1 }}
                      >
                        Download
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </Box>
          </Box>
        )}
      </Box>
    </Container>
  );
};

export default SearchPage;
