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
    borderRadius: 0, // Sharp edges
  },
  shadows: [
    'none',
    '0px 1px 2px rgba(0,0,0,0.2)',
    '0px 1px 3px rgba(0,0,0,0.2)',
    '0px 1px 4px rgba(0,0,0,0.2)',
    '0px 2px 4px rgba(0,0,0,0.2)',
    '0px 2px 5px rgba(0,0,0,0.2)',
    '0px 2px 6px rgba(0,0,0,0.2)',
    '0px 3px 6px rgba(0,0,0,0.2)',
    '0px 3px 7px rgba(0,0,0,0.2)',
    '0px 3px 8px rgba(0,0,0,0.2)',
    '0px 4px 8px rgba(0,0,0,0.2)',
    '0px 4px 9px rgba(0,0,0,0.2)',
    '0px 4px 10px rgba(0,0,0,0.2)',
    '0px 5px 10px rgba(0,0,0,0.2)',
    '0px 5px 11px rgba(0,0,0,0.2)',
    '0px 5px 12px rgba(0,0,0,0.2)',
    '0px 6px 12px rgba(0,0,0,0.2)',
    '0px 6px 13px rgba(0,0,0,0.2)',
    '0px 6px 14px rgba(0,0,0,0.2)',
    '0px 7px 14px rgba(0,0,0,0.2)',
    '0px 7px 15px rgba(0,0,0,0.2)',
    '0px 7px 16px rgba(0,0,0,0.2)',
    '0px 8px 16px rgba(0,0,0,0.2)',
    '0px 8px 17px rgba(0,0,0,0.2)',
    '0px 8px 18px rgba(0,0,0,0.2)',
  ],
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 0, // Sharp edges
          padding: '10px 24px',
          transition: 'none', // No animations
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderRadius: 0, // Sharp edges
          transition: 'none', // No animations
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderRadius: 0, // Sharp edges
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 0, // Sharp edges
        },
      },
    },
  },
});

