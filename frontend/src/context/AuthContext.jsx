import { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentUser, loginUser, registerUser, persistGuestIdentity } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('fixsembly_auth_token'));
  const [guestName, setGuestName] = useState(() => localStorage.getItem('fixsembly_guest_name') || '');
  const [guestSessionId, setGuestSessionId] = useState(() => {
    let sid = localStorage.getItem('fixsembly_guest_session_id');
    if (!sid) {
      sid = 'guest-' + Math.random().toString(36).substring(2, 12) + Date.now().toString(36);
      localStorage.setItem('fixsembly_guest_session_id', sid);
    }
    return sid;
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (token) {
      getCurrentUser()
        .then((userData) => {
          setUser(userData);
        })
        .catch(() => {
          // Token expired or invalid
          logout();
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [token]);

  const login = async (email, password) => {
    const data = await loginUser(email, password);
    setToken(data.access_token);
    localStorage.setItem('fixsembly_auth_token', data.access_token);
    setUser(data.user);
    return data;
  };

  const register = async (params) => {
    const data = await registerUser(params);
    return data;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('fixsembly_auth_token');
  };

  const enterAsGuest = async (name) => {
    const cleanName = name?.trim() || 'Guest Engineer';
    setGuestName(cleanName);
    localStorage.setItem('fixsembly_guest_name', cleanName);
    try {
      await persistGuestIdentity(cleanName, guestSessionId);
    } catch (err) {
      console.warn('Could not persist guest identity to backend:', err);
    }
  };

  const clearGuest = () => {
    setGuestName('');
    localStorage.removeItem('fixsembly_guest_name');
  };

  const value = {
    user,
    token,
    isAuthenticated: !!user,
    isGuest: !user && !!guestName,
    guestName,
    guestSessionId,
    isLoading,
    login,
    register,
    logout,
    enterAsGuest,
    clearGuest,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
