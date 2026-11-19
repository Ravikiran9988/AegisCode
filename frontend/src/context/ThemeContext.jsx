import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext(null);
const THEME_STORAGE_KEY = 'fixsembly_theme';
const THEME_VERSION_STORAGE_KEY = 'fixsembly_theme_version';
const THEME_VERSION = '2';

function getInitialTheme() {
  try {
    const storedVersion = localStorage.getItem(THEME_VERSION_STORAGE_KEY);

    // Previous releases persisted the original dark default. Migrate those
    // browsers to light once, then respect any theme choice made afterwards.
    if (storedVersion !== THEME_VERSION) {
      localStorage.setItem(THEME_STORAGE_KEY, 'light');
      localStorage.setItem(THEME_VERSION_STORAGE_KEY, THEME_VERSION);
      return 'light';
    }

    return localStorage.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
      root.style.colorScheme = 'dark';
    } else {
      root.classList.remove('dark');
      root.classList.add('light');
      root.style.colorScheme = 'light';
    }

    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
      localStorage.setItem(THEME_VERSION_STORAGE_KEY, THEME_VERSION);
    } catch {
      // Theme still works for the current session when storage is unavailable.
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <ThemeContext.Provider value={{ theme, isDark: theme === 'dark', toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
