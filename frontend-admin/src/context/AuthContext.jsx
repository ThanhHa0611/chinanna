import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';
import { requestLoginLocation } from '../utils/loginLocation';

const AuthContext = createContext(null);
const TOKEN_KEY = 'admin_token';
const LAST_EMAIL_KEY = 'admin_last_login_email';

export function AuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrapAuth = async () => {
      const token = localStorage.getItem(TOKEN_KEY);

      if (token) {
        try {
          const me = await api.getMe();
          setAdmin(me);
          localStorage.setItem(LAST_EMAIL_KEY, me.email || '');
          return;
        } catch {
          localStorage.removeItem(TOKEN_KEY);
        }
      }

      const email = (localStorage.getItem(LAST_EMAIL_KEY) || '').trim().toLowerCase();
      if (!email) {
        return;
      }

      try {
        const location = await requestLoginLocation();
        const data = await api.autoLogin({ email, ...location });
        localStorage.setItem(TOKEN_KEY, data.access_token);
        setAdmin(data.admin);
      } catch {
        // Auto-login is best effort: regular login flow remains available.
      }
    };

    bootstrapAuth().finally(() => setLoading(false));
  }, []);

  const login = async (email, password, location = {}) => {
    const data = await api.login({ email, password, ...location });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(LAST_EMAIL_KEY, data.admin?.email || email || '');
    setAdmin(data.admin);
    return data.admin;
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LAST_EMAIL_KEY);
    setAdmin(null);
  };

  return (
    <AuthContext.Provider value={{ admin, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
