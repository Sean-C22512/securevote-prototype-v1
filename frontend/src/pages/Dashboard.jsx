import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();
  const studentId = localStorage.getItem('studentId');

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const webAuthnSupported = typeof window !== 'undefined' && !!window.PublicKeyCredential;

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>
            SecureVote
          </span>
          <div className="d-flex align-items-center gap-3">
            <span className="text-muted d-none d-md-inline">{studentId}</span>
            <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container py-5">
        <div className="mb-5">
          <h1 className="fw-bold mb-2">Welcome to SecureVote</h1>
          <p className="text-muted">TU Dublin Student Elections Platform</p>
        </div>

        <div className="row g-4">
          {/* Cast Vote */}
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
                <h3 className="fw-bold mb-2">Cast Your Vote</h3>
                <p className="text-muted mb-4">Participate in active elections and make your voice heard</p>
                <Link to="/cast-vote" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                  Go to Voting
                </Link>
              </div>
            </div>
          </div>

          {/* View Results */}
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
                <p className="text-muted mb-4">See live election results and vote counts</p>
                <Link to="/results" className="btn btn-outline-secondary px-5 py-3" style={{ borderRadius: '12px', fontWeight: 600 }}>
                  View Results
                </Link>
              </div>
            </div>
          </div>

          {/* Biometric login card — shown only when WebAuthn is supported */}
          {webAuthnSupported && (
            <div className="col-md-6">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-body text-center p-5">
                  <div className="rounded-circle mx-auto mb-4 d-flex align-items-center justify-content-center"
                       style={{ width: '80px', height: '80px', backgroundColor: '#f3f0ff' }}>
                    <span style={{ fontSize: '2rem' }}>&#128272;</span>
                  </div>
                  <h3 className="fw-bold mb-2">Biometric Login</h3>
                  <p className="text-muted mb-4">Register TouchID, FaceID, or Windows Hello for passwordless sign-in</p>
                  <Link to="/webauthn-setup" className="btn btn-outline-secondary px-5 py-3" style={{ borderRadius: '12px', fontWeight: 600 }}>
                    Add Biometric
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Security Notice */}
        <div className="mt-5 text-center">
          <div className="d-inline-flex align-items-center px-4 py-2 rounded-pill" style={{ backgroundColor: '#d1e7dd' }}>
            <svg width="16" height="16" fill="#198754" className="me-2" viewBox="0 0 16 16">
              <path d="M5.338 1.59a61.44 61.44 0 0 0-2.837.856.481.481 0 0 0-.328.39c-.554 4.157.726 7.19 2.253 9.188a10.725 10.725 0 0 0 2.287 2.233c.346.244.652.42.893.533.12.057.218.095.293.118a.55.55 0 0 0 .101.025.615.615 0 0 0 .1-.025c.076-.023.174-.061.294-.118.24-.113.547-.29.893-.533a10.726 10.726 0 0 0 2.287-2.233c1.527-1.997 2.807-5.031 2.253-9.188a.48.48 0 0 0-.328-.39c-.651-.213-1.75-.56-2.837-.855C9.552 1.29 8.531 1.067 8 1.067c-.53 0-1.552.223-2.662.524zM5.072.56C6.157.265 7.31 0 8 0s1.843.265 2.928.56c1.11.3 2.229.655 2.887.87a1.54 1.54 0 0 1 1.044 1.262c.596 4.477-.787 7.795-2.465 9.99a11.775 11.775 0 0 1-2.517 2.453 7.159 7.159 0 0 1-1.048.625c-.28.132-.581.24-.829.24s-.548-.108-.829-.24a7.158 7.158 0 0 1-1.048-.625 11.777 11.777 0 0 1-2.517-2.453C1.928 10.487.545 7.169 1.141 2.692A1.54 1.54 0 0 1 2.185 1.43 62.456 62.456 0 0 1 5.072.56z"/>
              <path d="M10.854 5.146a.5.5 0 0 1 0 .708l-3 3a.5.5 0 0 1-.708 0l-1.5-1.5a.5.5 0 1 1 .708-.708L7.5 7.793l2.646-2.647a.5.5 0 0 1 .708 0z"/>
            </svg>
            <small className="text-success fw-medium">Your vote is encrypted and secured with blockchain technology</small>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
