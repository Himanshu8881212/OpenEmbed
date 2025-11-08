import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Container,
  Typography,
  Paper,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Chip,
  alpha,
} from '@mui/material';
import {
  CloudUpload,
  Close,
  CheckCircle,
  Delete,
} from '@mui/icons-material';
import { uploadFile, getVectorStores, VectorStore } from '../services/api';

const modalityExtensions: { [key: string]: string[] } = {
  text: ['.txt', '.md', '.json', '.csv'],
  image: ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'],
  video: ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
  audio: ['.wav', '.mp3', '.flac', '.m4a', '.ogg'],
  depth: ['.png', '.jpg', '.jpeg', '.tiff'],
  thermal: ['.png', '.jpg', '.jpeg', '.tiff'],
  imu: ['.csv', '.json', '.txt'],
};

const detectModality = (filename: string): string => {
  const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
  for (const [modality, extensions] of Object.entries(modalityExtensions)) {
    if (extensions.includes(ext)) {
      return modality;
    }
  }
  return 'image'; // default
};

const UploadPage: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [vectorStores, setVectorStores] = useState<VectorStore[]>([]);
  const [selectedStore, setSelectedStore] = useState<string>('');
  const [newStoreName, setNewStoreName] = useState<string>('');
  const [createNew, setCreateNew] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);

  useEffect(() => {
    loadVectorStores();
  }, []);

  const loadVectorStores = async () => {
    try {
      const stores = await getVectorStores();
      setVectorStores(Array.isArray(stores) ? stores : []);
    } catch (error) {
      console.error('Failed to load vector stores:', error);
      setVectorStores([]);
    }
  };

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    // Validate file formats
    const validFiles: File[] = [];
    const invalidFiles: string[] = [];

    acceptedFiles.forEach((file) => {
      const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
      const modality = detectModality(file.name);
      const allowedExtensions = modalityExtensions[modality] || [];

      if (allowedExtensions.includes(ext)) {
        validFiles.push(file);
      } else {
        invalidFiles.push(`${file.name} (not a valid ${modality} file)`);
      }
    });

    if (invalidFiles.length > 0) {
      setSnackbar({
        open: true,
        message: `Invalid files rejected: ${invalidFiles.join(', ')}`,
        severity: 'error',
      });
    }

    setFiles(validFiles);
    if (validFiles.length > 0) {
      setDialogOpen(true);
    }
  }, []);



  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: {
      'text/*': modalityExtensions.text,
      'image/*': modalityExtensions.image,
      'video/*': modalityExtensions.video,
      'audio/*': modalityExtensions.audio,
    },
  });

  const handleUpload = async () => {
    if (files.length === 0) return;
    if (!createNew && !selectedStore) {
      setSnackbar({ open: true, message: 'Please select a vector store', severity: 'error' });
      return;
    }
    if (createNew && !newStoreName) {
      setSnackbar({ open: true, message: 'Please enter a name for the new vector store', severity: 'error' });
      return;
    }

    setUploading(true);
    setProgress(0);

    try {
      const storeName = createNew ? newStoreName : selectedStore;
      const totalFiles = files.length;

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const modality = detectModality(file.name);

        await uploadFile(file, modality, storeName, createNew && i === 0);
        setProgress(((i + 1) / totalFiles) * 100);
      }

      setSnackbar({
        open: true,
        message: `Successfully uploaded ${files.length} file(s) to ${storeName}`,
        severity: 'success',
      });

      setFiles([]);
      setDialogOpen(false);
      setNewStoreName('');
      setSelectedStore('');
      setCreateNew(false);
      loadVectorStores();
    } catch (error: any) {
      setSnackbar({
        open: true,
        message: `Upload failed: ${error.message}`,
        severity: 'error',
      });
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, borderBottom: '1px solid', borderColor: 'divider', pb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Upload
        </Typography>
      </Box>

      <Paper
        {...getRootProps()}
        sx={{
          p: 6,
          textAlign: 'center',
          cursor: 'pointer',
          border: '2px dashed',
          borderColor: isDragActive ? 'text.primary' : 'divider',
          bgcolor: 'background.paper',
        }}
        elevation={0}
      >
        <input {...getInputProps()} />
        <CloudUpload sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
          {isDragActive ? 'Drop files here' : 'Drop files or click to browse'}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          All modalities supported
        </Typography>

        {/* Supported Formats Info */}
        <Box sx={{ mt: 3, pt: 3, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5, fontWeight: 600 }}>
            Supported Formats:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
            {Object.entries(modalityExtensions).map(([modality, extensions]) => (
              <Chip
                key={modality}
                label={`${modality.toUpperCase()}: ${extensions.join(', ')}`}
                size="small"
                sx={{
                  bgcolor: 'background.default',
                  border: '1px solid',
                  borderColor: 'divider',
                  fontSize: '0.7rem',
                }}
              />
            ))}
          </Box>
        </Box>

        {files.length > 0 && (
          <Box sx={{ mt: 3, pt: 3, borderTop: '1px solid', borderColor: 'divider' }}>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {files.length} file{files.length > 1 ? 's' : ''} selected
            </Typography>
            <Button
              variant="contained"
              onClick={(e) => {
                e.stopPropagation();
                setDialogOpen(true);
              }}
            >
              Continue
            </Button>
          </Box>
        )}
      </Paper>

      {/* Upload Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => !uploading && setDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: 'background.paper',
            backgroundImage: 'none',
            borderRadius: 3,
          },
        }}
      >
        <DialogTitle>
          Configure Upload
          {!uploading && (
            <IconButton
              onClick={() => setDialogOpen(false)}
              sx={{ position: 'absolute', right: 8, top: 8 }}
            >
              <Close />
            </IconButton>
          )}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
              Selected Files ({files.length})
            </Typography>
            <Box sx={{ maxHeight: 250, overflow: 'auto' }}>
              {files.map((file, index) => {
                const modality = detectModality(file.name);
                return (
                  <Paper
                    key={index}
                    sx={{
                      p: 1.5,
                      mb: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1.5,
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                        {file.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {modality} • {(file.size / 1024).toFixed(2)} KB
                      </Typography>
                    </Box>
                    {!uploading && (
                      <IconButton size="small" onClick={() => removeFile(index)}>
                        <Delete fontSize="small" />
                      </IconButton>
                    )}
                  </Paper>
                );
              })}
            </Box>
          </Box>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <Button
              variant={createNew ? 'contained' : 'outlined'}
              onClick={() => setCreateNew(!createNew)}
              fullWidth
            >
              {createNew ? 'Creating New Vector Store' : 'Use Existing Vector Store'}
            </Button>
          </FormControl>

          {createNew ? (
            <TextField
              fullWidth
              label="New Vector Store Name"
              value={newStoreName}
              onChange={(e) => setNewStoreName(e.target.value)}
              disabled={uploading}
              sx={{ mb: 2 }}
            />
          ) : (
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Select Vector Store</InputLabel>
              <Select
                value={selectedStore}
                onChange={(e) => setSelectedStore(e.target.value)}
                label="Select Vector Store"
                disabled={uploading}
              >
                {vectorStores.map((store) => (
                  <MenuItem key={store.name} value={store.name}>
                    {store.name} ({store.count} embeddings)
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {uploading && (
            <Box sx={{ mt: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Uploading...
                </Typography>
                <Typography variant="body2" color="primary" sx={{ fontWeight: 600 }}>
                  {Math.round(progress)}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={progress}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: alpha('#667eea', 0.1),
                  '& .MuiLinearProgress-bar': {
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    borderRadius: 4,
                  },
                }}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={uploading}>
            Cancel
          </Button>
          <Button
            onClick={handleUpload}
            variant="contained"
            disabled={uploading || files.length === 0}
            startIcon={uploading ? undefined : <CheckCircle />}
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </Button>
        </DialogActions>
      </Dialog >

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

export default UploadPage;

