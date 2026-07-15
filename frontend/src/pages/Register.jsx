import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import LocationPermissionBlock from '../components/LocationPermissionBlock';
import { useAuth } from '../context/AuthContext';
import { LOCATION_REQUIRED_MESSAGE, requestLoginLocation } from '../utils/loginLocation';

const MENTOR_TEAMS = [
  { value: 'Thanh Hà', label: 'Team Mentor Thanh Hà' },
];

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    mentor: '',
    zalo_phone: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [locationError, setLocationError] = useState('');
  const [locationPayload, setLocationPayload] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (form.password !== form.confirmPassword) {
      setError('Mật khẩu xác nhận không khớp');
      return;
    }

    if (form.password.length < 6) {
      setError('Mật khẩu phải có ít nhất 6 ký tự');
      return;
    }

    if (!form.mentor) {
      setError('Vui lòng chọn team mentor');
      return;
    }

    if (!form.zalo_phone.trim()) {
      setError('Vui lòng nhập số Zalo');
      return;
    }

    setSubmitting(true);

    try {
      let location = locationPayload;
      if (!location) {
        location = await requestLoginLocation();
        setLocationPayload(location);
      }
      const result = await register(
        form.username,
        form.email,
        form.password,
        form.mentor,
        form.zalo_phone,
        location,
      );
      setSuccess(result.message || 'Đã gửi yêu cầu đăng ký. Mentor sẽ duyệt trước khi bạn đăng nhập.');
      setTimeout(() => navigate('/login'), 2800);
    } catch (err) {
      setError(err.message || LOCATION_REQUIRED_MESSAGE);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Tạo tài khoản</h1>
        <p className="auth-subtitle">Chọn team mentor — tài khoản cần được mentor duyệt trước khi vào hệ thống</p>

        <LocationPermissionBlock
          value={locationPayload}
          onChange={setLocationPayload}
          error={locationError}
          onError={setLocationError}
        />

        {success && <div className="auth-success">{success}</div>}
        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Team mentor <span className="field-required">*</span>
            <select name="mentor" value={form.mentor} onChange={handleChange} required>
              <option value="">Chọn team mentor</option>
              {MENTOR_TEAMS.map((team) => (
                <option key={team.value} value={team.value}>
                  {team.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            Số Zalo <span className="field-required">*</span>
            <input
              type="tel"
              name="zalo_phone"
              value={form.zalo_phone}
              onChange={handleChange}
              placeholder="0901234567"
              inputMode="numeric"
              required
            />
          </label>

          <label>
            Tên đăng nhập
            <input
              type="text"
              name="username"
              value={form.username}
              onChange={handleChange}
              placeholder="username"
              minLength={3}
              required
            />
          </label>

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
              placeholder="Ít nhất 6 ký tự"
              minLength={6}
              required
            />
          </label>

          <label>
            Xác nhận mật khẩu
            <input
              type="password"
              name="confirmPassword"
              value={form.confirmPassword}
              onChange={handleChange}
              placeholder="Nhập lại mật khẩu"
              required
            />
          </label>

          <button type="submit" className="btn btn-primary btn-full" disabled={submitting || Boolean(success)}>
            {submitting ? 'Đang gửi yêu cầu...' : 'Gửi yêu cầu đăng ký'}
          </button>
        </form>

        <p className="auth-footer">
          Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
        </p>
      </div>
    </div>
  );
}
