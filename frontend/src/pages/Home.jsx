import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export default function Home() {
  const { user, updateUser } = useAuth();
  const location = useLocation();
  const fileInputRef = useRef(null);
  const [quote, setQuote] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState('');

  useEffect(() => {
    if (!user) {
      setQuote('');
      return;
    }

    import('../data/quotes').then(({ pickRandomQuote }) => {
      setQuote(pickRandomQuote());
    });
  }, [user?.id, location.key]);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = '';

    if (!user?.has_avatar || user?.role === 'parent') {
      setAvatarUrl('');
      setAvatarLoading(false);
      return undefined;
    }

    setAvatarLoading(true);
    setAvatarError('');
    api
      .fetchAvatarObjectUrl()
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setAvatarUrl(url);
      })
      .catch((err) => {
        if (!cancelled) setAvatarError(err.message);
      })
      .finally(() => {
        if (!cancelled) setAvatarLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [user?.id, user?.has_avatar]);

  const handleAvatarPick = () => {
    if (avatarUploading) return;
    fileInputRef.current?.click();
  };

  const handleAvatarChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setAvatarUploading(true);
    setAvatarError('');
    try {
      const updated = await api.uploadAvatar(file);
      updateUser(updated);
    } catch (err) {
      setAvatarError(err.message);
    } finally {
      setAvatarUploading(false);
    }
  };

  const displayName = (user?.full_name || user?.username || 'Mentee').trim();
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');

  return (
    <div className="home-page">
      <section className="hero">
        <div className="hero-badge">Du học Trung Quốc</div>
        <h1>
          Học bổng đang trên đường tới tay{' '}
          <span className="hero-clover" aria-hidden="true">
            🍀
          </span>
        </h1>
        <p className="hero-text">
          Hãy cố gắng mỗi ngày để trở thành phiên bản tốt hơn nhé
        </p>
        <p className="hero-disclaimer">
          Hệ thống chỉ support mentee Viên Mộng Hiên (phi lợi nhuận), vui lòng không chia sẻ dưới mọi hình thức
        </p>

        {user ? (
          <>
            {quote && (
              <blockquote className="hero-quote">
                <span className="hero-quote-mark">“</span>
                {quote.text}
                <span className="hero-quote-mark">”</span>
                {quote.author && <cite className="hero-quote-author">— {quote.author}</cite>}
              </blockquote>
            )}
            <div className="hero-card">
              <div className="hero-card-content">
                <h2>Xin chào, {user.username}!</h2>
                <p>Bạn đã đăng nhập thành công với email: {user.email}</p>
              </div>
              {user.role !== 'parent' && (
              <div className="hero-avatar-wrap">
                <button
                  type="button"
                  className="hero-avatar-btn"
                  onClick={handleAvatarPick}
                  disabled={avatarUploading}
                  aria-label="Đổi ảnh đại diện"
                  title="Bấm để tải ảnh đại diện"
                >
                  {avatarUrl ? (
                    <img src={avatarUrl} alt="Ảnh đại diện của bạn" className="hero-card-image hero-avatar-image" />
                  ) : (
                    <span className="hero-card-image hero-avatar-placeholder" aria-hidden="true">
                      {avatarLoading || avatarUploading ? '…' : initials || 'M'}
                    </span>
                  )}
                  <span className="hero-avatar-hint">
                    {avatarUploading ? 'Đang tải…' : user.has_avatar ? 'Đổi ảnh' : 'Thêm ảnh'}
                  </span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                  hidden
                  onChange={handleAvatarChange}
                />
                {avatarError && <p className="hero-avatar-error">{avatarError}</p>}
              </div>
              )}
            </div>
          </>
        ) : (
          <div className="hero-actions">
            <Link to="/register" className="btn btn-primary">
              Đăng kí
            </Link>
            <Link to="/login" className="btn btn-outline">
              Đăng nhập
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
