import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ForgotPasswordForm from '../components/ForgotPasswordForm';
import LocationPermissionBlock from '../components/LocationPermissionBlock';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { LOCATION_REQUIRED_MESSAGE, requestLoginLocation } from '../utils/loginLocation';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [locationPayload, setLocationPayload] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      let location = locationPayload;
      if (!location) {
        location = await requestLoginLocation();
        setLocationPayload(location);
      }
      const loggedInUser = await login(form.email, form.password, location);
      navigate(loggedInUser?.role === 'parent' ? '/profile' : '/');
    } catch (err) {
      setError(err.message || LOCATION_REQUIRED_MESSAGE);
    } finally {
      setSubmitting(false);
    }
  };

  if (showForgotPassword) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <ForgotPasswordForm
            requestOtp={api.requestForgotPasswordOtp}
            resetPassword={api.resetPasswordWithOtp}
            onBack={() => setShowForgotPassword(false)}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Đăng nhập</h1>
        <p className="auth-subtitle">Chào mừng bạn quay trở lại</p>

        <LocationPermissionBlock
          value={locationPayload}
          onChange={setLocationPayload}
          error={locationError}
          onError={setLocationError}
        />

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Email
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              placeholder="email@example.com"
              required
            />
          </label>

          <label>
            Mật khẩu
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              placeholder="••••••••"
              required
            />
          </label>

          <p className="auth-forgot-row">
            <button
              type="button"
              className="link-button"
              onClick={() => setShowForgotPassword(true)}
            >
              Quên mật khẩu?
            </button>
          </p>

          <button type="submit" className="btn btn-primary btn-full" disabled={submitting}>
            {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>

        <p className="auth-footer">
          Chưa có tài khoản? <Link to="/register">Tạo tài khoản</Link>
        </p>
      </div>
    </div>
  );
}
