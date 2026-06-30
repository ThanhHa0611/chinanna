import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';
import { requestLoginLocation } from '../utils/loginLocation';

const AuthContext = createContext(null);
const TOKEN_KEY = 'token';
const LAST_EMAIL_KEY = 'last_login_email';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrapAuth = async () => {
      const token = localStorage.getItem(TOKEN_KEY);

      if (token) {
        try {
          const me = await api.getMe();
          setUser(me);
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
        setUser(data.user);
      } catch {
        // Auto-login is best effort: regular login flow remains available.
      }
    };

    bootstrapAuth().finally(() => setLoading(false));
  }, []);

  const login = async (email, password, location = {}) => {
    const data = await api.login({ email, password, ...location });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(LAST_EMAIL_KEY, data.user?.email || email || '');
    setUser(data.user);
    return data.user;
  };

  const register = async (username, email, password, mentor, zaloPhone, location = {}) => {
    const data = await api.register({
      username,
      email,
      password,
      mentor,
      zalo_phone: zaloPhone,
      ...location,
    });
    if (data.access_token) {
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(LAST_EMAIL_KEY, data.user?.email || email || '');
      setUser(data.user);
    }
    return data;
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore logout errors
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LAST_EMAIL_KEY);
    setUser(null);
  };

  const updateUser = (nextUser) => {
    setUser(nextUser);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateUser }}>
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
