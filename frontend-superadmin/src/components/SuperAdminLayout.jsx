import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import DeviceModeSwitcher from './DeviceModeSwitcher';

import ScreenProtection from './ScreenProtection';

import { useAuth } from '../context/AuthContext';
import { useDeviceMode } from '../context/DeviceModeContext';

const NAV_ITEMS = [
  { to: '/mentors', label: 'Mentor' },
  { to: '/mentees', label: 'Mentee' },
  { to: '/access-requests', label: 'Cấp quyền' },
];



export default function SuperAdminLayout({ mentorAlertCount = 0, menteeCount = null }) {
  const { admin, logout } = useAuth();
  const { isPhone } = useDeviceMode() || {};
  const navigate = useNavigate();



  const handleLogout = async () => {

    await logout();

    navigate('/login');

  };



  return (

    <div className="shell">

      <aside className="sidebar">

        <div className="sidebar-brand">

          <span className="sidebar-brand-title">Du học Trung Quốc</span>

          <span className="sidebar-brand-sub">Super Admin</span>

        </div>

        <nav className="sidebar-nav">

          {NAV_ITEMS.map((item) => (

            <NavLink

              key={item.to}

              to={item.to}

              className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}

            >

              <span className="sidebar-link-label">

                {item.label}

                {item.to === '/mentees' && menteeCount != null && (

                  <span className="sidebar-link-count">({menteeCount})</span>

                )}

              </span>

              {item.to === '/mentors' && mentorAlertCount > 0 && (

                <span className="notify-dot" title="Có hoạt động mentor mới" />

              )}

            </NavLink>

          ))}

        </nav>

        <div className="sidebar-footer">
          <p className="sidebar-user">{admin?.email}</p>
          <DeviceModeSwitcher compact />
          <button type="button" className="btn btn-sidebar" onClick={handleLogout}>
            Đăng xuất
          </button>
        </div>
        <div className="sidebar-footer-device-mode">
          <DeviceModeSwitcher compact />
        </div>

      </aside>



      <div className="main-shell">

        <header className="topbar">
          <div>
            <h1>Quản trị hệ thống</h1>
            <p>Theo dõi mentor và mentee toàn hệ thống</p>
          </div>
          {isPhone && (
            <button type="button" className="btn btn-outline btn-sm" onClick={handleLogout}>
              Đăng xuất
            </button>
          )}
        </header>

        <main className="main-content protected-main">

          <Outlet />

        </main>

      </div>

      <ScreenProtection account={admin} />

    </div>

  );

}

