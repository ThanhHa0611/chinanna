import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import LocationPermissionBlock from '../components/LocationPermissionBlock';
import { useAuth } from '../context/AuthContext';
import { LOCATION_REQUIRED_MESSAGE, requestLoginLocation } from '../utils/loginLocation';

export default function Login() {
  const { admin, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [locationPayload, setLocationPayload] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (admin?.is_super_admin) {
    return <Navigate to="/mentors" replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      let location = locationPayload;
      if (!location) {
        location = await requestLoginLocation();
        setLocationPayload(location);
      }
      await login(email, password, location);
      navigate('/mentors');
    } catch (err) {
      setError(err.message || LOCATION_REQUIRED_MESSAGE);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="center-page">
      <div className="auth-shell">
        <div className="auth-brand">
          <h1>Du học Trung Quốc</h1>
          <p>Super Admin</p>
        </div>
        <div className="auth-card">
          <h2>Đăng nhập hệ thống</h2>
          <p className="auth-note">
            Máy tổng quản trị — xem mentor và mentee toàn hệ thống.
          </p>
          <LocationPermissionBlock
            value={locationPayload}
            onChange={setLocationPayload}
            error={locationError}
            onError={setLocationError}
          />
          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="username"
              />
            </label>
            <label>
              Mật khẩu
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button type="submit" className="btn btn-primary btn-full" disabled={submitting}>
              {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
