import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  Divider,
  Alert,
  Snackbar,
  CircularProgress,
  Paper,
  Chip,
  ListItemButton,
} from '@mui/material';
import {
  Delete,
  FolderOpen,
  Close,
  OpenInNew,
} from '@mui/icons-material';
import {
  getVectorStores,
  getVectorStoreFiles,
  deleteVectorStore,
  VectorStore,
  EmbeddedFile,
} from '../services/api';

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

const VectorStoresPage: React.FC = () => {
  const [vectorStores, setVectorStores] = useState<VectorStore[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedStore, setSelectedStore] = useState<VectorStore | null>(null);
  const [storeFiles, setStoreFiles] = useState<EmbeddedFile[]>([]);
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<boolean>(false);
  const [storeToDelete, setStoreToDelete] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  useEffect(() => {
    loadVectorStores();
  }, []);

  const loadVectorStores = async () => {
    setLoading(true);
    try {
      const stores = await getVectorStores();
      setVectorStores(stores);
    } catch (error) {
      console.error('Failed to load vector stores:', error);
      setSnackbar({
        open: true,
        message: 'Failed to load vector stores',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleViewStore = async (store: VectorStore) => {
    setSelectedStore(store);
    try {
      const files = await getVectorStoreFiles(store.name);
      setStoreFiles(files);
      setDialogOpen(true);
    } catch (error) {
      console.error('Failed to load store files:', error);
      setSnackbar({
        open: true,
        message: 'Failed to load store files',
        severity: 'error',
      });
    }
  };

  const handleDeleteClick = (storeName: string) => {
    setStoreToDelete(storeName);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!storeToDelete) return;

    try {
      await deleteVectorStore(storeToDelete);
      setSnackbar({
        open: true,
        message: `Vector store "${storeToDelete}" deleted successfully`,
        severity: 'success',
      });
      loadVectorStores();
    } catch (error) {
      console.error('Failed to delete vector store:', error);
      setSnackbar({
        open: true,
        message: 'Failed to delete vector store',
        severity: 'error',
      });
    } finally {
      setDeleteDialogOpen(false);
      setStoreToDelete(null);
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, borderBottom: '1px solid', borderColor: 'divider', pb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Vector Stores
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {vectorStores.length} stores • {vectorStores.reduce((sum, s) => sum + s.count, 0)} files • {formatBytes(vectorStores.reduce((sum, s) => sum + (s.size_bytes || 0), 0))}
        </Typography>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : vectorStores.length === 0 ? (
        <Paper sx={{ p: 8, textAlign: 'center', border: '2px dashed', borderColor: 'divider' }}>
          <FolderOpen sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
            No Vector Stores
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Upload files to create a vector store
          </Typography>
          <Button
            variant="contained"
            onClick={() => window.location.href = '/upload'}
          >
            Upload Files
          </Button>
        </Paper>
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }, gap: 2 }}>
          {vectorStores.map((store) => {
            const modality = store.modality?.toLowerCase() || 'unknown';

            return (
              <Card
                key={store.name}
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <CardContent sx={{ flex: 1 }}>
                  <Typography variant="h6" noWrap sx={{ fontWeight: 600, mb: 1 }}>
                    {store.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {modality}
                  </Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <Box>
                      <Typography variant="h4" sx={{ fontWeight: 600 }}>
                        {store.count.toLocaleString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        files
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {formatBytes(store.size_bytes || 0)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        storage
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>

                <CardActions sx={{ p: 2, gap: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => handleViewStore(store)}
                  >
                    View
                  </Button>
                  <IconButton
                    size="small"
                    onClick={() => handleDeleteClick(store.name)}
                  >
                    <Delete />
                  </IconButton>
                </CardActions>
              </Card>
            );
          })}
        </Box>
      )}

      {/* View Store Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: 'background.paper',
            backgroundImage: 'none',
          },
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {selectedStore?.name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {storeFiles.length} files
              </Typography>
            </Box>
            <IconButton onClick={() => setDialogOpen(false)}>
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>
        <Divider />
        <DialogContent>
          <List sx={{ pt: 2 }}>
            {storeFiles.map((file) => {
              const handleFileClick = async () => {
                try {
                  // Construct the file URL based on the backend API endpoint
                  const fileUrl = `http://localhost:8000/api/uploads/${file.modality}/${file.id}`;

                  // Fetch the file as a blob
                  const response = await fetch(fileUrl);
                  if (!response.ok) {
                    throw new Error('Failed to fetch file');
                  }

                  const blob = await response.blob();
                  const url = window.URL.createObjectURL(blob);

                  // Create a temporary link and trigger download
                  const link = document.createElement('a');
                  link.href = url;
                  link.download = file.filename || `file_${file.id}`;
                  document.body.appendChild(link);
                  link.click();

                  // Cleanup
                  document.body.removeChild(link);
                  window.URL.revokeObjectURL(url);
                } catch (error) {
                  console.error('Error downloading file:', error);
                  setSnackbar({
                    open: true,
                    message: 'Failed to download file',
                    severity: 'error',
                  });
                }
              };

              return (
                <ListItemButton
                  key={file.id}
                  onClick={handleFileClick}
                  sx={{
                    mb: 1,
                    p: 2,
                    border: '1px solid',
                    borderColor: 'divider',
                    bgcolor: 'background.paper',
                    '&:hover': {
                      borderColor: 'text.secondary',
                    },
                  }}
                >
                  <Box sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {file.filename}
                      </Typography>
                      <Chip
                        label={file.modality}
                        size="small"
                        sx={{
                          height: 20,
                          fontSize: '0.7rem',
                          bgcolor: 'background.default',
                          border: '1px solid',
                          borderColor: 'divider',
                        }}
                      />
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {new Date(file.timestamp).toLocaleString()}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Download
                    </Typography>
                    <OpenInNew sx={{ fontSize: 16, color: 'text.secondary' }} />
                  </Box>
                </ListItemButton>
              );
            })}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        PaperProps={{
          sx: {
            bgcolor: 'background.paper',
            backgroundImage: 'none',
          },
        }}
      >
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the vector store "{storeToDelete}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Container >
  );
};

export default VectorStoresPage;

