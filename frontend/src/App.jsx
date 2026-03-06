import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import CastVote from './pages/CastVote';
import Results from './pages/Results';
import WebAuthnSetup from './pages/WebAuthnSetup';
import AdminDashboard from './pages/admin/AdminDashboard';
import UserManagement from './pages/admin/UserManagement';
import AuditLog from './pages/admin/AuditLog';
import OfficialDashboard from './pages/official/OfficialDashboard';
import ElectionManagement from './pages/official/ElectionManagement';
import ElectionResults from './pages/official/ElectionResults';

// Private route that checks for authentication
const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/" />;
};

// Role-based route that checks for specific roles
const RoleRoute = ({ children, allowedRoles }) => {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');

  if (!token) {
    return <Navigate to="/" />;
  }

  if (!allowedRoles.includes(role)) {
    // Redirect to appropriate dashboard based on role
    switch (role) {
      case 'admin':
        return <Navigate to="/admin" />;
      case 'official':
        return <Navigate to="/official" />;
      default:
        return <Navigate to="/dashboard" />;
    }
  }

  return children;
};

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Student Routes */}
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/cast-vote"
            element={
              <PrivateRoute>
                <CastVote />
              </PrivateRoute>
            }
          />
          <Route
            path="/results"
            element={
              <PrivateRoute>
                <Results />
              </PrivateRoute>
            }
          />

          {/* WebAuthn Setup */}
          <Route
            path="/webauthn-setup"
            element={
              <PrivateRoute>
                <WebAuthnSetup />
              </PrivateRoute>
            }
          />

          {/* Admin Routes */}
          <Route
            path="/admin"
            element={
              <RoleRoute allowedRoles={['admin']}>
                <AdminDashboard />
              </RoleRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <RoleRoute allowedRoles={['admin']}>
                <UserManagement />
              </RoleRoute>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <RoleRoute allowedRoles={['admin']}>
                <AuditLog />
              </RoleRoute>
            }
          />

          {/* Official (Student Union) Routes */}
          <Route
            path="/official"
            element={
              <RoleRoute allowedRoles={['admin', 'official']}>
                <OfficialDashboard />
              </RoleRoute>
            }
          />
          <Route
            path="/official/elections"
            element={
              <RoleRoute allowedRoles={['admin', 'official']}>
                <ElectionManagement />
              </RoleRoute>
            }
          />
          <Route
            path="/official/results"
            element={
              <RoleRoute allowedRoles={['admin', 'official']}>
                <ElectionResults />
              </RoleRoute>
            }
          />

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;

