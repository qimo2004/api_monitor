import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AuthGuard from './shared/AuthGuard';
import AppLayout from './shared/Layout';
import Login from './features/auth/Login';
import Dashboard from './features/dashboard/Dashboard';
import ApiList from './features/apis/ApiList';
import LogList from './features/logs/LogList';
import AlertList from './features/alerts/AlertList';
import Reports from './features/stats/Reports';
import UserManage from './features/users/UserManage';
import UserAuthApis from './features/users/UserAuthApis';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<AuthGuard><AppLayout /></AuthGuard>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="apis" element={<ApiList />} />
          <Route path="logs" element={<LogList />} />
          <Route path="alerts" element={<AlertList />} />
          <Route path="reports" element={<Reports />} />
          <Route path="users" element={<UserManage />} />
          <Route path="users/:userId/auth-apis" element={<UserAuthApis />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
