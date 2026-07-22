import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import ScreenProtection from './components/ScreenProtection';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DeviceModeProvider } from './context/DeviceModeContext';
import Home from './pages/Home';
import InterviewPractice from './pages/InterviewPractice';
import Login from './pages/Login';
import Profile from './pages/Profile';
import Register from './pages/Register';
import './index.css';
import './device-phone.css';

function AppRoutes() {
  const { user } = useAuth();

  return (
    <>
      <Navbar />
      <main className={user ? 'protected-main' : ''}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/profile" element={<Profile />} />
            <Route path="/interview" element={<InterviewPractice />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      {user && <ScreenProtection user={user} />}
    </>
  );
}

function App() {
  const basename = import.meta.env.BASE_URL.replace(/\/$/, '');

  return (
    <DeviceModeProvider
      appKey="mentee"
      title="圆梦轩"
      subtitle="Bạn đang dùng điện thoại hay laptop?"
    >
      <AuthProvider>
        <BrowserRouter
          basename={basename || undefined}
          future={{
            v7_startTransition: true,
            v7_relativeSplatPath: true,
          }}
        >
          <div className="app">
            <AppRoutes />
          </div>
        </BrowserRouter>
      </AuthProvider>
    </DeviceModeProvider>
  );
}

export default App;
