import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchUsers, fetchAuditStats } from '../../api/apiClient';

const AdminDashboard = () => {
  const [stats, setStats] = useState({ users: 0, totalVotes: 0, chainValid: true });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [usersData, auditData] = await Promise.all([
        fetchUsers(),
        fetchAuditStats()
      ]);
      setStats({
        users: usersData.users?.length || 0,
        totalVotes: auditData.total_votes || 0,
        chainValid: auditData.chain_valid !== false
      });
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>
            SecureVote Admin
          </span>
          <div className="d-flex align-items-center gap-3">
            <Link to="/official" className="btn btn-outline-secondary btn-sm">
              Election Management
            </Link>
            <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container py-5">
        <div className="mb-5">
          <h1 className="fw-bold mb-2">Admin Dashboard</h1>
          <p className="text-muted">System administration and monitoring</p>
        </div>

        {/* Stats Cards */}
        <div className="row g-4 mb-5">
          <div className="col-md-4">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Total Users</p>
                    <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                      {loading ? '...' : stats.users}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: '#f3f0ff' }}>
                    <svg width="24" height="24" fill="#6f42c1" viewBox="0 0 16 16">
                      <path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
                      <path fillRule="evenodd" d="M5.216 14A2.238 2.238 0 0 1 5 13c0-1.355.68-2.75 1.936-3.72A6.325 6.325 0 0 0 5 9c-4 0-5 3-5 4s1 1 1 1h4.216z"/>
                      <path d="M4.5 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-md-4">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Total Votes Cast</p>
                    <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                      {loading ? '...' : stats.totalVotes}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: '#f3f0ff' }}>
                    <svg width="24" height="24" fill="#6f42c1" viewBox="0 0 16 16">
                      <path d="M4 0h5.293A1 1 0 0 1 10 .293L13.707 4a1 1 0 0 1 .293.707V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zm5.5 1.5v2a1 1 0 0 0 1 1h2l-3-3zM6.354 9.854a.5.5 0 0 0-.708-.708L4.5 10.293l-.646-.647a.5.5 0 1 0-.708.708l1 1a.5.5 0 0 0 .708 0l1.5-1.5z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-md-4">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Blockchain Status</p>
                    <h2 className="fw-bold mb-0" style={{ color: stats.chainValid ? '#198754' : '#dc3545' }}>
                      {loading ? '...' : (stats.chainValid ? 'Valid' : 'Invalid')}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: stats.chainValid ? '#d1e7dd' : '#f8d7da' }}>
                    <svg width="24" height="24" fill={stats.chainValid ? '#198754' : '#dc3545'} viewBox="0 0 16 16">
                      <path d="M9.05.435c-.58-.58-1.52-.58-2.1 0L.436 6.95c-.58.58-.58 1.519 0 2.098l6.516 6.516c.58.58 1.519.58 2.098 0l6.516-6.516c.58-.58.58-1.519 0-2.098L9.05.435zM8 4c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 4.995A.905.905 0 0 1 8 4zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Cards */}
        <div className="row g-4">
          <div className="col-md-6">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body text-center p-5">
                <div className="rounded-circle mx-auto mb-4 d-flex align-items-center justify-content-center"
                     style={{ width: '80px', height: '80px', backgroundColor: '#f3f0ff' }}>
                  <svg width="36" height="36" fill="#6f42c1" viewBox="0 0 16 16">
                    <path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
                    <path fillRule="evenodd" d="M5.216 14A2.238 2.238 0 0 1 5 13c0-1.355.68-2.75 1.936-3.72A6.325 6.325 0 0 0 5 9c-4 0-5 3-5 4s1 1 1 1h4.216z"/>
                    <path d="M4.5 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"/>
                  </svg>
                </div>
                <h3 className="fw-bold mb-2">User Management</h3>
                <p className="text-muted mb-4">Manage users, roles, and permissions</p>
                <Link to="/admin/users" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                  Manage Users
                </Link>
              </div>
            </div>
          </div>

          <div className="col-md-6">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body text-center p-5">
                <div className="rounded-circle mx-auto mb-4 d-flex align-items-center justify-content-center"
                     style={{ width: '80px', height: '80px', backgroundColor: '#f3f0ff' }}>
                  <svg width="36" height="36" fill="#6f42c1" viewBox="0 0 16 16">
                    <path d="M5 10.5a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 0 1h-2a.5.5 0 0 1-.5-.5zm0-2a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5zm0-2a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5zm0-2a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5z"/>
                    <path d="M3 0h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-1h1v1a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v1H1V2a2 2 0 0 1 2-2z"/>
                    <path d="M1 5v-.5a.5.5 0 0 1 1 0V5h.5a.5.5 0 0 1 0 1h-2a.5.5 0 0 1 0-1H1zm0 3v-.5a.5.5 0 0 1 1 0V8h.5a.5.5 0 0 1 0 1h-2a.5.5 0 0 1 0-1H1zm0 3v-.5a.5.5 0 0 1 1 0v.5h.5a.5.5 0 0 1 0 1h-2a.5.5 0 0 1 0-1H1z"/>
                  </svg>
                </div>
                <h3 className="fw-bold mb-2">Audit Log</h3>
                <p className="text-muted mb-4">View system audit and blockchain verification</p>
                <Link to="/admin/audit" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                  View Audit Log
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
