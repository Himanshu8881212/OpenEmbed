import { createTheme } from '@mui/material/styles';

// Professional greyscale Material UI theme
export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#e0e0e0',
      light: '#f5f5f5',
      dark: '#9e9e9e',
      contrastText: '#212121',
    },
    secondary: {
      main: '#757575',
      light: '#a4a4a4',
      dark: '#494949',
      contrastText: '#ffffff',
    },
    background: {
      default: '#0a0a0a',
      paper: '#1a1a1a',
    },
    text: {
      primary: '#e0e0e0',
      secondary: '#9e9e9e',
    },
    divider: '#2a2a2a',
    success: {
      main: '#b0b0b0',
      light: '#d0d0d0',
      dark: '#808080',
    },
    error: {
      main: '#757575',
      light: '#9e9e9e',
      dark: '#424242',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '3.5rem',
      fontWeight: 300,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '2.5rem',
      fontWeight: 300,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '2rem',
      fontWeight: 400,
      letterSpacing: '0em',
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 400,
      letterSpacing: '0.01em',
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
      letterSpacing: '0.01em',
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
      letterSpacing: '0.02em',
    },
    body1: {
      fontSize: '1rem',
      letterSpacing: '0.01em',
    },
    body2: {
      fontSize: '0.875rem',
      letterSpacing: '0.01em',
    },
  },
  shape: {
    borderRadius: 12,
  },
  shadows: [
    'none',
    '0px 2px 4px rgba(0,0,0,0.3)',
    '0px 4px 8px rgba(0,0,0,0.3)',
    '0px 6px 12px rgba(0,0,0,0.3)',
    '0px 8px 16px rgba(0,0,0,0.3)',
    '0px 10px 20px rgba(0,0,0,0.3)',
    '0px 12px 24px rgba(0,0,0,0.3)',
    '0px 14px 28px rgba(0,0,0,0.3)',
    '0px 16px 32px rgba(0,0,0,0.3)',
    '0px 18px 36px rgba(0,0,0,0.3)',
    '0px 20px 40px rgba(0,0,0,0.3)',
    '0px 22px 44px rgba(0,0,0,0.3)',
    '0px 24px 48px rgba(0,0,0,0.3)',
    '0px 26px 52px rgba(0,0,0,0.3)',
    '0px 28px 56px rgba(0,0,0,0.3)',
    '0px 30px 60px rgba(0,0,0,0.3)',
    '0px 32px 64px rgba(0,0,0,0.3)',
    '0px 34px 68px rgba(0,0,0,0.3)',
    '0px 36px 72px rgba(0,0,0,0.3)',
    '0px 38px 76px rgba(0,0,0,0.3)',
    '0px 40px 80px rgba(0,0,0,0.3)',
    '0px 42px 84px rgba(0,0,0,0.3)',
    '0px 44px 88px rgba(0,0,0,0.3)',
    '0px 46px 92px rgba(0,0,0,0.3)',
    '0px 48px 96px rgba(0,0,0,0.3)',
  ],
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 8,
          padding: '10px 24px',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0px 8px 16px rgba(0,0,0,0.4)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: '0px 12px 24px rgba(0,0,0,0.4)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
      },
    },
  },
});

