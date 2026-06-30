import { useState } from 'react';

export default function ForgotPasswordForm({
  requestOtp,
  resetPassword,
  onBack,
  emailLabel = 'Email đăng ký',
}) {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSendOtp = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setSubmitting(true);
    try {
      const data = await requestOtp(email.trim().toLowerCase());
      setMessage(data.message || 'Đã gửi mã OTP tới email của bạn.');
      setStep('reset');
    } catch (err) {
      setError(err.message || 'Không gửi được mã OTP');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');

    if (newPassword !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp');
      return;
    }

    setSubmitting(true);
    try {
      const data = await resetPassword({
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      setMessage(data.message || 'Đặt lại mật khẩu thành công.');
      setStep('done');
    } catch (err) {
      setError(err.message || 'Không đặt lại được mật khẩu');
    } finally {
      setSubmitting(false);
    }
  };

  if (step === 'done') {
    return (
      <div className="forgot-password-panel">
        <div className="auth-success">{message}</div>
        <button type="button" className="btn btn-primary btn-full" onClick={onBack}>
          Quay lại đăng nhập
        </button>
      </div>
    );
  }

  if (step === 'reset') {
    return (
      <div className="forgot-password-panel">
        <h2 className="forgot-password-title">Nhập mã OTP</h2>
        <p className="auth-subtitle">
          Mã 6 số đã gửi tới <strong>{email}</strong>
        </p>
        {message && <div className="auth-success">{message}</div>}
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleResetPassword} className="auth-form">
          <label>
            Mã OTP
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              required
            />
          </label>
          <label>
            Mật khẩu mới
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={6}
              required
            />
          </label>
          <label>
            Xác nhận mật khẩu
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={6}
              required
            />
          </label>
          <button type="submit" className="btn btn-primary btn-full" disabled={submitting}>
            {submitting ? 'Đang xử lý...' : 'Đặt lại mật khẩu'}
          </button>
        </form>
        <p className="auth-footer">
          <button type="button" className="link-button" onClick={() => setStep('email')}>
            Gửi lại mã OTP
          </button>
          {' · '}
          <button type="button" className="link-button" onClick={onBack}>
            Quay lại đăng nhập
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="forgot-password-panel">
      <h2 className="forgot-password-title">Quên mật khẩu</h2>
      <p className="auth-subtitle">Nhập email để nhận mã OTP đặt lại mật khẩu</p>
      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={handleSendOtp} className="auth-form">
        <label>
          {emailLabel}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@example.com"
            required
          />
        </label>
        <button type="submit" className="btn btn-primary btn-full" disabled={submitting}>
          {submitting ? 'Đang gửi...' : 'Gửi mã OTP'}
        </button>
      </form>
      <p className="auth-footer">
        <button type="button" className="link-button" onClick={onBack}>
          Quay lại đăng nhập
        </button>
      </p>
    </div>
  );
}
