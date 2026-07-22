import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const openProfileSection = (event) => {
    if (location.pathname === '/profile') {
      event.preventDefault();
      window.dispatchEvent(
        new CustomEvent('profile-open-section', { detail: { section: 'account' } }),
      );
      return;
    }
    navigate('/profile', { state: { section: 'account' } });
  };

  return (
    <nav className="navbar">
      <div className="navbar-start">
        {user ? (
          <>
            <Link to="/" className="navbar-brand navbar-brand-pearl">
              圆梦轩
            </Link>
            <NavLink to="/profile" className="nav-link" onClick={openProfileSection}>
              Tôi
            </NavLink>
            <NavLink to="/interview" className="nav-link">
              Luyện phỏng vấn
            </NavLink>
          </>
        ) : (
          <Link to="/" className="navbar-brand navbar-brand-pearl">
            圆梦轩
          </Link>
        )}
      </div>

      <div className="navbar-end">
        {user ? (
          <button type="button" className="btn btn-outline" onClick={logout}>
            Đăng xuất
          </button>
        ) : (
          <>
            <Link to="/login" className="btn btn-outline">
              Đăng nhập
            </Link>
            <Link to="/register" className="btn btn-primary">
              Tạo tài khoản
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
