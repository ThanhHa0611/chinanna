import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import BrandMark from '../components/BrandMark';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { formatLevel1MentorLine, LEVEL1_MENTORS } from '../utils/mentorDisplay';

export default function Register() {
  const { admin } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    mentor_name: 'Thanh Hà',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (admin) {
    return <Navigate to="/" replace />;
  }

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setSubmitting(true);

    try {
      const result = await api.register(form);
      setSuccess(result.message);
      setTimeout(() => navigate('/login'), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="center-page">
      <div className="auth-shell auth-card-wide">
        <div className="auth-brand">
          <BrandMark subtitle="Mentor Trơn Tru" />
        </div>
        <div className="auth-card">
          <h2>Đăng ký mới</h2>
          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              Email
              <input type="email" value={form.email} onChange={handleChange('email')} required />
            </label>
            <label>
              Tên đăng nhập
              <input
                type="text"
                value={form.username}
                onChange={handleChange('username')}
                required
              />
            </label>
            <label>
              Họ tên
              <input
                type="text"
                value={form.full_name}
                onChange={handleChange('full_name')}
                placeholder="Họ và tên trong hộ chiếu (có dấu)"
              />
              <span className="field-hint">
                Bắt buộc: họ và tên trong hộ chiếu, có dấu.
              </span>
            </label>
            <label>
              Mentor cấp 1
              <select value={form.mentor_name} onChange={handleChange('mentor_name')}>
                {LEVEL1_MENTORS.map((name) => (
                  <option key={name} value={name}>
                    {formatLevel1MentorLine(name)}
                  </option>
                ))}
              </select>
              <span className="field-hint">
                Chọn nhánh mentor cấp 1: Mentor Mai Chi hoặc Mentor Thanh Hà.
              </span>
            </label>
            <label>
              Mật khẩu
              <input
                type="password"
                value={form.password}
                onChange={handleChange('password')}
                required
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            {success && <p className="form-success">{success}</p>}
            <button type="submit" className="btn btn-primary btn-full" disabled={submitting}>
              {submitting ? 'Đang gửi...' : 'Đăng ký'}
            </button>
          </form>
          <p className="auth-footer">
            Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
