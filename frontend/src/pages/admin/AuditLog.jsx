import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { verifyChain, fetchAuditStats, fetchElections } from '../../api/apiClient';

const AuditLog = () => {
  const [stats, setStats] = useState(null);
  const [elections, setElections] = useState([]);
  const [selectedElection, setSelectedElection] = useState('');
  const [verificationResult, setVerificationResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedElection !== undefined) {
      loadStats();
    }
  }, [selectedElection]);

  const loadData = async () => {
    try {
      const [electionsData, statsData] = await Promise.all([
        fetchElections(),
        fetchAuditStats()
      ]);
      setElections(electionsData.elections || []);
      setStats(statsData);
    } catch (err) {
      setError('Failed to load audit data');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const statsData = await fetchAuditStats(selectedElection || null);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load stats');
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError('');
    setVerificationResult(null);
    try {
      const result = await verifyChain(selectedElection || null);
      setVerificationResult(result);
    } catch (err) {
      setError('Verification failed');
    } finally {
      setVerifying(false);
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
          <Link to="/admin" className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>
            SecureVote Admin
          </Link>
          <div className="d-flex align-items-center gap-3">
            <Link to="/admin" className="btn btn-outline-secondary btn-sm">
              Back to Dashboard
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
          <h1 className="fw-bold mb-2">Audit Log</h1>
          <p className="text-muted">Blockchain verification and system audit</p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        {/* Filter by Election */}
        <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '16px' }}>
          <div className="card-body p-4">
            <div className="row align-items-end">
              <div className="col-md-6">
                <label className="form-label fw-medium">Filter by Election</label>
                <select
                  className="form-select"
                  value={selectedElection}
                  onChange={(e) => setSelectedElection(e.target.value)}
                >
                  <option value="">All Elections</option>
                  {elections.map((election) => (
                    <option key={election.election_id} value={election.election_id}>
                      {election.title} ({election.status})
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-md-6 text-md-end mt-3 mt-md-0">
                <button
                  className="submit-btn px-4 py-2"
                  onClick={handleVerify}
                  disabled={verifying}
                >
                  {verifying ? 'Verifying...' : 'Verify Blockchain'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        {loading ? (
          <div className="text-center py-5">
            <div className="spinner-border text-secondary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : stats && (
          <div className="row g-4 mb-4">
            <div className="col-md-3">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-body p-4 text-center">
                  <p className="text-muted mb-2">Total Votes</p>
                  <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                    {stats.total_votes || 0}
                  </h2>
                </div>
              </div>
            </div>

            <div className="col-md-3">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-body p-4 text-center">
                  <p className="text-muted mb-2">Chain Length</p>
                  <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                    {stats.chain_length || 0}
                  </h2>
                </div>
              </div>
            </div>

            <div className="col-md-3">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-body p-4 text-center">
                  <p className="text-muted mb-2">Chain Status</p>
                  <h2 className="fw-bold mb-0" style={{ color: stats.chain_valid !== false ? '#198754' : '#dc3545' }}>
                    {stats.chain_valid !== false ? 'Valid' : 'Invalid'}
                  </h2>
                </div>
              </div>
            </div>

            <div className="col-md-3">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-body p-4 text-center">
                  <p className="text-muted mb-2">Unique Voters</p>
                  <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                    {stats.unique_voters || 0}
                  </h2>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Verification Result */}
        {verificationResult && (
          <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
            <div className="card-header bg-white border-0 py-3 px-4">
              <h5 className="mb-0 fw-bold">Verification Result</h5>
            </div>
            <div className="card-body p-4">
              <div className={`alert ${verificationResult.valid ? 'alert-success' : 'alert-danger'} mb-4`}>
                <div className="d-flex align-items-center">
                  {verificationResult.valid ? (
                    <svg width="24" height="24" fill="currentColor" className="me-2" viewBox="0 0 16 16">
                      <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                    </svg>
                  ) : (
                    <svg width="24" height="24" fill="currentColor" className="me-2" viewBox="0 0 16 16">
                      <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293 5.354 4.646z"/>
                    </svg>
                  )}
                  <strong>
                    {verificationResult.valid
                      ? 'Blockchain integrity verified successfully'
                      : 'Blockchain integrity check failed'}
                  </strong>
                </div>
              </div>

              <div className="row g-3">
                <div className="col-md-6">
                  <div className="bg-light rounded p-3">
                    <small className="text-muted d-block mb-1">Blocks Verified</small>
                    <strong>{verificationResult.total_votes || 0}</strong>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="bg-light rounded p-3">
                    <small className="text-muted d-block mb-1">Verified At</small>
                    <strong>{new Date().toLocaleString()}</strong>
                  </div>
                </div>
              </div>

              {verificationResult.errors && verificationResult.errors.length > 0 && (
                <div className="mt-4">
                  <h6 className="fw-bold text-danger">Errors Found:</h6>
                  <ul className="mb-0">
                    {verificationResult.errors.map((error, index) => (
                      <li key={index} className="text-danger">{error}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditLog;
