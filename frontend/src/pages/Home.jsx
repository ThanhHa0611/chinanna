import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const heroImageUrl = `${import.meta.env.BASE_URL}tron-tru-girl.svg`;

export default function Home() {
  const { user } = useAuth();
  const location = useLocation();
  const [quote, setQuote] = useState('');

  useEffect(() => {
    if (!user) {
      setQuote('');
      return;
    }

    import('../data/quotes').then(({ pickRandomQuote }) => {
      setQuote(pickRandomQuote());
    });
  }, [user?.id, location.key]);

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
          Chăm chỉ luyện phỏng vấn để phỏng vấn thật trơn tru nha
        </p>
        <p className="hero-disclaimer">
          Hệ thống chỉ support mentee Du học Trung Quốc (phi lợi nhuận), vui lòng không chia sẻ dưới mọi hình thức
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
            <img
              src={heroImageUrl}
              alt="Du học Trung Quốc"
              className="hero-card-image"
            />
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
