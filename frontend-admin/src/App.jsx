import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AdminLayout from './components/AdminLayout';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './context/AuthContext';
import { DeviceModeProvider } from './context/DeviceModeContext';
import AccessRequests from './pages/AccessRequests';
import Account from './pages/Account';
import ActivityHistory from './pages/ActivityHistory';
import FeedbackPage from './pages/FeedbackPage';
import Home from './pages/Home';
import Login from './pages/Login';
import Mentees from './pages/Mentees';
import ProfileActivities from './pages/ProfileActivities';
import Register from './pages/Register';
import './index.css';
import './device-phone.css';

export default function App() {
  const basename = import.meta.env.BASE_URL.replace(/\/$/, '');

  return (
    <DeviceModeProvider
      appKey="mentor"
      title="Mentor Trơn Tru"
      subtitle="Bạn đang đăng nhập bằng điện thoại hay laptop?"
    >
      <AuthProvider>
      <BrowserRouter
        basename={basename || undefined}
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AdminLayout />}>
              <Route path="/" element={<Home />} />
              <Route path="/access-requests" element={<AccessRequests />} />
              <Route path="/mentees" element={<Mentees />} />
              <Route path="/feedback" element={<FeedbackPage />} />
              <Route path="/profile-activities" element={<ProfileActivities />} />
              <Route path="/account" element={<Account />} />
              <Route path="/history" element={<ActivityHistory />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
      </AuthProvider>
    </DeviceModeProvider>
  );
}
