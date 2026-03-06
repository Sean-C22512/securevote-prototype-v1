import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchElections } from '../../api/apiClient';

const OfficialDashboard = () => {
  const [stats, setStats] = useState({ active: 0, draft: 0, closed: 0 });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const userRole = localStorage.getItem('role');

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await fetchElections();
      const elections = data.elections || [];
      setStats({
        active: elections.filter(e => e.status === 'active').length,
        draft: elections.filter(e => e.status === 'draft').length,
        closed: elections.filter(e => e.status === 'closed').length,
        total: elections.length
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
            SecureVote SU
          </span>
          <div className="d-flex align-items-center gap-3">
            {userRole === 'admin' && (
              <Link to="/admin" className="btn btn-outline-secondary btn-sm">
                Admin Panel
              </Link>
            )}
            <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container py-5">
        <div className="mb-5">
          <h1 className="fw-bold mb-2">Student Union Dashboard</h1>
          <p className="text-muted">Manage elections and view results</p>
        </div>

        {/* Stats Cards */}
        <div className="row g-4 mb-5">
          <div className="col-md-3">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Active Elections</p>
                    <h2 className="fw-bold mb-0" style={{ color: '#198754' }}>
                      {loading ? '...' : stats.active}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: '#d1e7dd' }}>
                    <svg width="24" height="24" fill="#198754" viewBox="0 0 16 16">
                      <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                      <path d="M10.97 4.97a.235.235 0 0 0-.02.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-1.071-1.05z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-md-3">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Draft Elections</p>
                    <h2 className="fw-bold mb-0" style={{ color: '#ffc107' }}>
                      {loading ? '...' : stats.draft}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: '#fff3cd' }}>
                    <svg width="24" height="24" fill="#ffc107" viewBox="0 0 16 16">
                      <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-md-3">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Closed Elections</p>
                    <h2 className="fw-bold mb-0" style={{ color: '#6c757d' }}>
                      {loading ? '...' : stats.closed}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: '#e9ecef' }}>
                    <svg width="24" height="24" fill="#6c757d" viewBox="0 0 16 16">
                      <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                      <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-md-3">
            <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center justify-content-between">
                  <div>
                    <p className="text-muted mb-1">Total Elections</p>
                    <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                      {loading ? '...' : stats.total}
                    </h2>
                  </div>
                  <div className="rounded-circle p-3" style={{ backgroundColor: '#f3f0ff' }}>
                    <svg width="24" height="24" fill="#6f42c1" viewBox="0 0 16 16">
                      <path d="M4 0h5.293A1 1 0 0 1 10 .293L13.707 4a1 1 0 0 1 .293.707V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zm5.5 1.5v2a1 1 0 0 0 1 1h2l-3-3z"/>
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
                    <path d="M14.5 3a.5.5 0 0 1 .5.5v9a.5.5 0 0 1-.5.5h-13a.5.5 0 0 1-.5-.5v-9a.5.5 0 0 1 .5-.5h13zm-13-1A1.5 1.5 0 0 0 0 3.5v9A1.5 1.5 0 0 0 1.5 14h13a1.5 1.5 0 0 0 1.5-1.5v-9A1.5 1.5 0 0 0 14.5 2h-13z"/>
                    <path d="M7 5.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5zm-1.496-.854a.5.5 0 0 1 0 .708l-1.5 1.5a.5.5 0 0 1-.708 0l-.5-.5a.5.5 0 1 1 .708-.708l.146.147 1.146-1.147a.5.5 0 0 1 .708 0zM7 9.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5zm-1.496-.854a.5.5 0 0 1 0 .708l-1.5 1.5a.5.5 0 0 1-.708 0l-.5-.5a.5.5 0 0 1 .708-.708l.146.147 1.146-1.147a.5.5 0 0 1 .708 0z"/>
                  </svg>
                </div>
                <h3 className="fw-bold mb-2">Manage Elections</h3>
                <p className="text-muted mb-4">Create, edit, and manage election campaigns</p>
                <Link to="/official/elections" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                  Manage Elections
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
                    <path d="M4 11H2v3h2v-3zm5-4H7v7h2V7zm5-5h-2v12h2V2zm-2-1a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1h-2zM6 7a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V7zm-5 4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1v-3z"/>
                  </svg>
                </div>
                <h3 className="fw-bold mb-2">View Results</h3>
                <p className="text-muted mb-4">View detailed election results and analytics</p>
                <Link to="/official/results" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                  View Results
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OfficialDashboard;
