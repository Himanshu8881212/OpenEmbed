import React, { useEffect, useState } from 'react';
import {
  Box,
  Container,
  Card,
  CardContent,
  Typography,
  Paper,
} from '@mui/material';
import {
  ImageOutlined,
  VideoLibrary,
  AudioFile,
  TextFields,
  Terrain,
  Thermostat,
  Sensors,
} from '@mui/icons-material';
import axios from 'axios';

interface SystemStats {
  total_stores: number;
  total_files: number;
  total_size_bytes: number;
  modalities: {
    text: number;
    image: number;
    video: number;
    audio: number;
    depth: number;
    thermal: number;
    imu: number;
  };
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

const modalityConfig = [
  { name: 'Text', icon: TextFields, key: 'text', formats: '.txt, .md, .json, .csv' },
  { name: 'Image', icon: ImageOutlined, key: 'image', formats: '.jpg, .jpeg, .png, .bmp, .gif, .webp' },
  { name: 'Video', icon: VideoLibrary, key: 'video', formats: '.mp4, .avi, .mov, .mkv, .webm' },
  { name: 'Audio', icon: AudioFile, key: 'audio', formats: '.wav, .mp3, .flac, .m4a, .ogg' },
  { name: 'Depth', icon: Terrain, key: 'depth', formats: '.png, .jpg, .jpeg, .tiff' },
  { name: 'Thermal', icon: Thermostat, key: 'thermal', formats: '.png, .jpg, .jpeg, .tiff' },
  { name: 'IMU', icon: Sensors, key: 'imu', formats: '.csv, .json, .txt' },
];

const HomePage: React.FC = () => {
  const [stats, setStats] = useState<SystemStats>({
    total_stores: 0,
    total_files: 0,
    total_size_bytes: 0,
    modalities: { text: 0, image: 0, video: 0, audio: 0, depth: 0, thermal: 0, imu: 0 },
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await axios.get('http://localhost:8000/api/vector-stores');

      let totalFiles = 0;
      let totalSizeBytes = 0;
      const modalityCounts = { text: 0, image: 0, video: 0, audio: 0, depth: 0, thermal: 0, imu: 0 };

      response.data.stores.forEach((store: any) => {
        const count = store.count || 0;
        const sizeBytes = store.size_bytes || 0;
        totalFiles += count;
        totalSizeBytes += sizeBytes;

        // Get modality counts from metadata (added by backend)
        if (store.metadata && store.metadata.modality_counts) {
          const counts = store.metadata.modality_counts;
          Object.keys(counts).forEach((modality: string) => {
            const modalityKey = modality.toLowerCase();
            if (modalityKey in modalityCounts) {
              modalityCounts[modalityKey as keyof typeof modalityCounts] += counts[modality];
            }
          });
        }
      });

      setStats({
        total_stores: response.data.stores.length,
        total_files: totalFiles,
        total_size_bytes: totalSizeBytes,
        modalities: modalityCounts,
      });
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };



  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4, borderBottom: '1px solid', borderColor: 'divider', pb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Dashboard
        </Typography>
      </Box>

      {/* Key Metrics */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 2, mb: 4 }}>
        <Card
          sx={{
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <CardContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Total Files
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {loading ? '...' : stats.total_files.toLocaleString()}
            </Typography>
          </CardContent>
        </Card>

        <Card
          sx={{
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <CardContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Vector Stores
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {loading ? '...' : stats.total_stores}
            </Typography>
          </CardContent>
        </Card>

        <Card
          sx={{
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <CardContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Storage Size
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {loading ? '...' : formatBytes(stats.total_size_bytes)}
            </Typography>
          </CardContent>
        </Card>

        <Card
          sx={{
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <CardContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Modalities
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {loading ? '...' : Object.values(stats.modalities).filter((v) => v > 0).length}/7
            </Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Modality Usage Distribution */}
      <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
          Modality Usage Distribution
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {modalityConfig.map((modality) => {
            const Icon = modality.icon;
            const count = stats.modalities[modality.key as keyof typeof stats.modalities] || 0;
            const percentage = stats.total_files > 0 ? (count / stats.total_files) * 100 : 0;

            return (
              <Box key={modality.key}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Icon sx={{ fontSize: 18, color: 'text.secondary' }} />
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {modality.name}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    {count} ({percentage.toFixed(1)}%)
                  </Typography>
                </Box>
                <Box
                  sx={{
                    width: '100%',
                    height: 8,
                    bgcolor: 'background.default',
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 0,
                    overflow: 'hidden',
                  }}
                >
                  <Box
                    sx={{
                      width: `${percentage}%`,
                      height: '100%',
                      bgcolor: 'text.primary',
                      transition: 'width 0.3s ease',
                    }}
                  />
                </Box>
              </Box>
            );
          })}
        </Box>
      </Paper>
    </Container >
  );
};

export default HomePage;

