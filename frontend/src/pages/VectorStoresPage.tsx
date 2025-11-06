import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Alert,
  Snackbar,
  CircularProgress,
} from '@mui/material';
import {
  Storage,
  Delete,
  Visibility,
  Image,
  VideoLibrary,
  AudioFile,
  Thermostat,
  Layers,
  TextFields,
  FolderOpen,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import {
  getVectorStores,
  getVectorStoreFiles,
  deleteVectorStore,
  VectorStore,
  EmbeddedFile,
} from '../services/api';

const modalityIcons: { [key: string]: React.ReactElement } = {
  image: <Image />,
  video: <VideoLibrary />,
  audio: <AudioFile />,
  thermal: <Thermostat />,
  depth: <Layers />,
  text: <TextFields />,
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
    <Container maxWidth="lg" sx={{ py: 8 }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Typography variant="h2" gutterBottom sx={{ mb: 2, fontWeight: 300 }}>
          Vector Stores
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 6 }}>
          Manage your vector stores and view embedded files
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : vectorStores.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            <Card sx={{ p: 8, textAlign: 'center' }}>
              <FolderOpen sx={{ fontSize: 80, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h5" gutterBottom>
                No Vector Stores Yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Upload some files to create your first vector store
              </Typography>
            </Card>
          </motion.div>
        ) : (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
              },
              gap: 3,
            }}
          >
            {vectorStores.map((store, index) => (
              <motion.div
                key={store.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                    overflow: 'visible',
                  }}
                >
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <Storage sx={{ mr: 1, color: 'primary.main' }} />
                      <Typography variant="h6" component="div" noWrap>
                        {store.name}
                      </Typography>
                    </Box>
                    <Chip
                      label={`${store.count} embeddings`}
                      size="small"
                      sx={{ mb: 1 }}
                    />
                  </CardContent>
                  <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
                    <Button
                      size="small"
                      startIcon={<Visibility />}
                      onClick={() => handleViewStore(store)}
                    >
                      View
                    </Button>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => handleDeleteClick(store.name)}
                    >
                      <Delete />
                    </IconButton>
                  </CardActions>
                </Card>
              </motion.div>
            ))}
          </Box>
        )}
      </motion.div>

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
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Storage sx={{ mr: 1 }} />
            {selectedStore?.name}
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {storeFiles.length} embedded file(s)
          </Typography>
          <Divider sx={{ my: 2 }} />
          <List>
            {storeFiles.map((file, index) => (
              <motion.div
                key={file.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <ListItem>
                  <ListItemIcon>
                    {modalityIcons[file.modality] || <TextFields />}
                  </ListItemIcon>
                  <ListItemText
                    primary={file.filename}
                    secondary={
                      <Box component="span" sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                        <Chip
                          label={file.modality}
                          size="small"
                          sx={{ textTransform: 'capitalize' }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          {new Date(file.timestamp).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                {index < storeFiles.length - 1 && <Divider />}
              </motion.div>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Close</Button>
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
    </Container>
  );
};

export default VectorStoresPage;

