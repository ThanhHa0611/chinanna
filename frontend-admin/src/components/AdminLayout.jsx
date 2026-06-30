import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import ScreenProtection from './ScreenProtection';
import BrandMark from './BrandMark';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { getSidebarBrand, isLevel1MentorAccount } from '../utils/mentorDisplay';
import { countMenteesNeedingAttention } from '../utils/menteeAttention';

const NAV_ITEMS = [
  { to: '/', label: 'Trang chủ', end: true },
  { to: '/access-requests', label: 'Cấp quyền' },
  { to: '/mentees', label: 'Mentee' },
  { to: '/profile-activities', label: 'Hoạt động hồ sơ' },
  { to: '/feedback', label: 'Phản hồi' },
  { to: '/account', label: 'Tài khoản' },
];

const SUPER_ADMIN_NAV_ITEMS = [{ to: '/history', label: 'Lịch sử hoạt động' }];

export default function AdminLayout() {
  const { admin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingAccessCount, setPendingAccessCount] = useState(0);
  const [menteeAttentionCount, setMenteeAttentionCount] = useState(0);
  const [profileActivitiesPendingCount, setProfileActivitiesPendingCount] = useState(0);

  useEffect(() => {
    if (!admin) return;

    let cancelled = false;
    const attentionOptions = {
      isSuperAdmin: Boolean(admin.is_super_admin),
      isLevel1: isLevel1MentorAccount(admin),
    };

    Promise.all([api.getStats(), api.getMentees()])
      .then(([statsData, menteeData]) => {
        if (!cancelled) {
          setPendingAccessCount(statsData.pending_access_requests_count || 0);
          setMenteeAttentionCount(
            countMenteesNeedingAttention(menteeData || [], attentionOptions),
          );
          setProfileActivitiesPendingCount(statsData.profile_activities_pending_count || 0);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [admin, location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = admin?.is_super_admin
    ? [...NAV_ITEMS, ...SUPER_ADMIN_NAV_ITEMS]
    : NAV_ITEMS;

  const brandLines = getSidebarBrand(admin);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <BrandMark lines={brandLines} />
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
            >
              <span className="sidebar-link-label">
                {item.label}
                {item.to === '/access-requests' && pendingAccessCount > 0 && (
                  <span className="sidebar-notify-badge" title="Có yêu cầu cấp quyền chờ duyệt">
                    {pendingAccessCount}
                  </span>
                )}
                {item.to === '/mentees' && menteeAttentionCount > 0 && (
                  <span className="sidebar-notify-badge" title="Có mentee cần xử lí">
                    {menteeAttentionCount}
                  </span>
                )}
                {item.to === '/profile-activities' && profileActivitiesPendingCount > 0 && (
                  <span
                    className="sidebar-notify-badge sidebar-notify-badge-activities"
                    title="Có yêu cầu cần duyệt / xử lí"
                  >
                    {profileActivitiesPendingCount}
                  </span>
                )}
              </span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p className="sidebar-user">{admin?.email}</p>
          <button type="button" className="btn btn-sidebar" onClick={handleLogout}>
            Đăng xuất
          </button>
        </div>
      </aside>

      <div className="main-shell">
        <main className="main-content protected-main">
          <Outlet />
        </main>
      </div>
      <ScreenProtection account={admin} />
    </div>
  );
}
