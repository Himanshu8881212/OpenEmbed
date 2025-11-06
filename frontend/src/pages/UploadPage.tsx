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
  Chip,
  LinearProgress,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
} from '@mui/material';
import {
  CloudUpload,
  Image,
  VideoLibrary,
  AudioFile,
  Thermostat,
  Layers,
  TextFields,
  Close,
  CheckCircle,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { uploadFile, getVectorStores, VectorStore } from '../services/api';

const modalityIcons: { [key: string]: React.ReactElement } = {
  image: <Image />,
  video: <VideoLibrary />,
  audio: <AudioFile />,
  thermal: <Thermostat />,
  depth: <Layers />,
  text: <TextFields />,
};

const modalityExtensions: { [key: string]: string[] } = {
  text: ['.txt'],
  image: ['.jpg', '.jpeg', '.png', '.bmp'],
  video: ['.mp4', '.avi', '.mov', '.mkv'],
  audio: ['.wav', '.mp3', '.flac', '.m4a'],
  thermal: ['.jpg', '.jpeg', '.png'],
  depth: ['.png', '.npy'],
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

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles(acceptedFiles);
    if (acceptedFiles.length > 0) {
      setDialogOpen(true);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
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
    <Container maxWidth="lg" sx={{ py: 8 }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Typography variant="h2" gutterBottom sx={{ mb: 2, fontWeight: 300 }}>
          Upload Files
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 6 }}>
          Drag and drop your files to automatically detect the modality and embed them into a vector store
        </Typography>

        <Paper
          {...getRootProps()}
          sx={{
            p: 8,
            textAlign: 'center',
            cursor: 'pointer',
            border: '2px dashed',
            borderColor: isDragActive ? 'primary.main' : 'divider',
            bgcolor: isDragActive ? 'action.hover' : 'background.paper',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            '&:hover': {
              borderColor: 'primary.main',
              bgcolor: 'action.hover',
              transform: 'scale(1.01)',
            },
          }}
          elevation={isDragActive ? 8 : 2}
        >
          <input {...getInputProps()} />
          <motion.div
            animate={{ scale: isDragActive ? 1.1 : 1 }}
            transition={{ duration: 0.2 }}
          >
            <CloudUpload sx={{ fontSize: 80, color: 'text.secondary', mb: 2 }} />
          </motion.div>
          <Typography variant="h5" gutterBottom>
            {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            or click to browse
          </Typography>
          <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap' }}>
            {Object.entries(modalityIcons).map(([modality, icon]) => (
              <Chip
                key={modality}
                icon={icon}
                label={modality}
                variant="outlined"
                sx={{ textTransform: 'capitalize' }}
              />
            ))}
          </Box>
        </Paper>
      </motion.div>

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
            <Typography variant="subtitle2" gutterBottom>
              Selected Files ({files.length})
            </Typography>
            <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
              {files.map((file, index) => (
                <Chip
                  key={index}
                  label={`${file.name} (${detectModality(file.name)})`}
                  onDelete={() => !uploading && removeFile(index)}
                  icon={modalityIcons[detectModality(file.name)]}
                  sx={{ m: 0.5 }}
                />
              ))}
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
            <Box sx={{ mt: 2 }}>
              <LinearProgress variant="determinate" value={progress} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
                Uploading... {Math.round(progress)}%
              </Typography>
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

export default UploadPage;

