import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Container,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  useMediaQuery,
  useTheme as useMuiTheme,
} from '@mui/material';
import {
  CloudUpload,
  Storage,
  Menu as MenuIcon,
  Close,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { theme } from './theme';
import UploadPage from './pages/UploadPage';
import VectorStoresPage from './pages/VectorStoresPage';

const Navigation: React.FC = () => {
  const location = useLocation();
  const muiTheme = useMuiTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const navItems = [
    { path: '/', label: 'Upload', icon: <CloudUpload /> },
    { path: '/stores', label: 'Vector Stores', icon: <Storage /> },
  ];

  const NavButton: React.FC<{ path: string; label: string; icon: React.ReactElement }> = ({
    path,
    label,
    icon,
  }) => {
    const isActive = location.pathname === path;
    return (
      <Button
        component={Link}
        to={path}
        startIcon={icon}
        sx={{
          color: isActive ? 'primary.main' : 'text.secondary',
          position: 'relative',
          '&::after': {
            content: '""',
            position: 'absolute',
            bottom: 0,
            left: '50%',
            transform: 'translateX(-50%)',
            width: isActive ? '80%' : '0%',
            height: '2px',
            bgcolor: 'primary.main',
            transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          },
          '&:hover::after': {
            width: '80%',
          },
        }}
      >
        {label}
      </Button>
    );
  };

  return (
    <>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
          backdropFilter: 'blur(20px)',
          backgroundColor: 'rgba(26, 26, 26, 0.8)',
        }}
      >
        <Container maxWidth="lg">
          <Toolbar disableGutters>
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5 }}
            >
              <Typography
                variant="h5"
                component={Link}
                to="/"
                sx={{
                  fontWeight: 300,
                  letterSpacing: '0.1em',
                  textDecoration: 'none',
                  color: 'primary.main',
                  mr: 4,
                }}
              >
                openEmbed
              </Typography>
            </motion.div>

            {isMobile ? (
              <IconButton
                color="inherit"
                onClick={() => setDrawerOpen(true)}
                sx={{ ml: 'auto' }}
              >
                <MenuIcon />
              </IconButton>
            ) : (
              <Box sx={{ display: 'flex', gap: 2, ml: 'auto' }}>
                {navItems.map((item) => (
                  <NavButton key={item.path} {...item} />
                ))}
              </Box>
            )}
          </Toolbar>
        </Container>
      </AppBar>

      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{
          sx: {
            width: 250,
            bgcolor: 'background.paper',
          },
        }}
      >
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Menu</Typography>
          <IconButton onClick={() => setDrawerOpen(false)}>
            <Close />
          </IconButton>
        </Box>
        <List>
          {navItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                onClick={() => setDrawerOpen(false)}
                selected={location.pathname === item.path}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
    </>
  );
};

const PageTransition: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
};

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Box
          sx={{
            minHeight: '100vh',
            bgcolor: 'background.default',
            backgroundImage: `
              radial-gradient(circle at 20% 50%, rgba(255, 255, 255, 0.02) 0%, transparent 50%),
              radial-gradient(circle at 80% 80%, rgba(255, 255, 255, 0.02) 0%, transparent 50%)
            `,
          }}
        >
          <Navigation />
          <AnimatePresence mode="wait">
            <Routes>
              <Route
                path="/"
                element={
                  <PageTransition>
                    <UploadPage />
                  </PageTransition>
                }
              />
              <Route
                path="/stores"
                element={
                  <PageTransition>
                    <VectorStoresPage />
                  </PageTransition>
                }
              />
            </Routes>
          </AnimatePresence>
        </Box>
      </Router>
    </ThemeProvider>
  );
}

export default App;
