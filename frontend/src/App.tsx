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
  Dashboard,
  Search,
} from '@mui/icons-material';
import { AnimatePresence } from 'framer-motion';
import { theme } from './theme';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import VectorStoresPage from './pages/VectorStoresPage';
import SearchPage from './pages/SearchPage';

const Navigation: React.FC = () => {
  const location = useLocation();
  const muiTheme = useMuiTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <Dashboard /> },
    { path: '/upload', label: 'Upload', icon: <CloudUpload /> },
    { path: '/stores', label: 'Stores', icon: <Storage /> },
    { path: '/search', label: 'Search', icon: <Search /> },
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
          color: isActive ? 'text.primary' : 'text.secondary',
          fontWeight: isActive ? 600 : 400,
          px: 2.5,
          borderBottom: isActive ? '2px solid' : 'none',
          borderColor: 'text.primary',
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
          backgroundColor: 'rgba(26, 26, 26, 0.95)',
        }}
      >
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ minHeight: { xs: 64, md: 72 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography
                variant="h6"
                component={Link}
                to="/"
                sx={{
                  fontWeight: 600,
                  textDecoration: 'none',
                  color: 'text.primary',
                }}
              >
                OpenEmbed
              </Typography>
            </Box>

            {isMobile ? (
              <IconButton
                color="inherit"
                onClick={() => setDrawerOpen(true)}
                sx={{ ml: 'auto' }}
              >
                <MenuIcon />
              </IconButton>
            ) : (
              <Box sx={{ display: 'flex', gap: 1, ml: 'auto' }}>
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
            width: 280,
            bgcolor: 'background.paper',
          },
        }}
      >
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>Navigation</Typography>
          <IconButton onClick={() => setDrawerOpen(false)} size="small">
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
                sx={{
                  py: 1.5,
                  '&.Mui-selected': {
                    bgcolor: 'rgba(255, 255, 255, 0.08)',
                    borderLeft: '3px solid',
                    borderColor: 'primary.main',
                  },
                }}
              >
                <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'text.secondary' }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontWeight: location.pathname === item.path ? 600 : 400
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
    </>
  );
};

const PageTransition: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <>{children}</>;
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
          }}
        >
          <Navigation />
          <AnimatePresence mode="wait">
            <Routes>
              <Route
                path="/"
                element={
                  <PageTransition>
                    <HomePage />
                  </PageTransition>
                }
              />
              <Route
                path="/upload"
                element={
                  <PageTransition>
                    <UploadPage />
                  </PageTransition>
                }
              />
              <Route
                path="/search"
                element={
                  <PageTransition>
                    <SearchPage />
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
