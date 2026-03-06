import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchElections, fetchElectionResults, verifyChain } from '../../api/apiClient';

const ElectionResults = () => {
  const [elections, setElections] = useState([]);
  const [selectedElection, setSelectedElection] = useState('');
  const [results, setResults] = useState(null);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const userRole = localStorage.getItem('role');

  useEffect(() => {
    loadElections();
  }, []);

  useEffect(() => {
    // Check for election in URL params
    const electionParam = searchParams.get('election');
    if (electionParam && elections.length > 0) {
      setSelectedElection(electionParam);
    }
  }, [searchParams, elections]);

  useEffect(() => {
    if (selectedElection) {
      loadResults();
    } else {
      setResults(null);
    }
  }, [selectedElection]);

  const loadElections = async () => {
    try {
      const data = await fetchElections();
      // Filter to show only active and closed elections
      const filteredElections = (data.elections || []).filter(
        e => e.status === 'active' || e.status === 'closed'
      );
      setElections(filteredElections);
    } catch (err) {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchElectionResults(selectedElection);
      setResults(data);
    } catch (err) {
      setError('Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError('');
    try {
      const result = await verifyChain(selectedElection);
      setVerification(result);
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

  const getMaxVotes = () => {
    if (!results?.results) return 0;
    return Math.max(...results.results.map(r => r.votes), 1);
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <Link to="/official" className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>
            SecureVote SU
          </Link>
          <div className="d-flex align-items-center gap-3">
            <Link to="/official" className="btn btn-outline-secondary btn-sm">
              Back to Dashboard
            </Link>
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
          <h1 className="fw-bold mb-2">Election Results</h1>
          <p className="text-muted">View detailed results and verify blockchain integrity</p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        {/* Election Selector */}
        <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '16px' }}>
          <div className="card-body p-4">
            <div className="row align-items-end">
              <div className="col-md-6">
                <label className="form-label fw-medium">Select Election</label>
                <select
                  className="form-select"
                  value={selectedElection}
                  onChange={(e) => setSelectedElection(e.target.value)}
                >
                  <option value="">Choose an election...</option>
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
                  disabled={!selectedElection || verifying}
                >
                  {verifying ? 'Verifying...' : 'Verify Blockchain'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Results Display */}
        {loading && selectedElection ? (
          <div className="text-center py-5">
            <div className="spinner-border text-secondary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : !selectedElection ? (
          <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
            <div className="card-body text-center py-5">
              <p className="text-muted mb-0">Select an election to view results</p>
            </div>
          </div>
        ) : results ? (
          <div className="row g-4">
            {/* Vote Counts */}
            <div className="col-md-8">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-header bg-white border-0 py-3 px-4">
                  <h5 className="mb-0 fw-bold">Vote Distribution</h5>
                </div>
                <div className="card-body p-4">
                  {results.results && results.results.length > 0 ? (
                    results.results.map((candidate, index) => (
                      <div key={candidate.candidate_id} className="mb-4">
                        <div className="d-flex justify-content-between mb-2">
                          <span className="fw-medium">{candidate.name}</span>
                          <span className="fw-bold" style={{ color: '#6f42c1' }}>
                            {candidate.votes} votes
                            {results.total_votes > 0 && (
                              <small className="text-muted ms-2">
                                ({((candidate.votes / results.total_votes) * 100).toFixed(1)}%)
                              </small>
                            )}
                          </span>
                        </div>
                        <div className="progress" style={{ height: '12px', borderRadius: '6px' }}>
                          <div
                            className="progress-bar"
                            role="progressbar"
                            style={{
                              width: `${(candidate.votes / getMaxVotes()) * 100}%`,
                              background: index === 0 ? 'linear-gradient(90deg, #C594FF 0%, #8A94FF 100%)' : '#e9ecef',
                              borderRadius: '6px'
                            }}
                          ></div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted text-center">No votes cast yet</p>
                  )}
                </div>
              </div>
            </div>

            {/* Statistics */}
            <div className="col-md-4">
              <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '16px' }}>
                <div className="card-body p-4 text-center">
                  <p className="text-muted mb-2">Total Votes</p>
                  <h2 className="fw-bold mb-0" style={{ color: '#6f42c1' }}>
                    {results.total_votes || 0}
                  </h2>
                </div>
              </div>

              <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '16px' }}>
                <div className="card-body p-4 text-center">
                  <p className="text-muted mb-2">Election Status</p>
                  <span className={`badge ${results.status === 'active' ? 'bg-success' : 'bg-secondary'} fs-6`}>
                    {results.status || 'Unknown'}
                  </span>
                </div>
              </div>

              {results.results && results.results.length > 0 && (
                <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
                  <div className="card-body p-4 text-center">
                    <p className="text-muted mb-2">Leading Candidate</p>
                    <h5 className="fw-bold mb-0" style={{ color: '#198754' }}>
                      {results.results[0]?.name || 'N/A'}
                    </h5>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : null}

        {/* Verification Result */}
        {verification && (
          <div className="card border-0 shadow-sm mt-4" style={{ borderRadius: '16px' }}>
            <div className="card-header bg-white border-0 py-3 px-4">
              <h5 className="mb-0 fw-bold">Blockchain Verification</h5>
            </div>
            <div className="card-body p-4">
              <div className={`alert ${verification.valid ? 'alert-success' : 'alert-danger'} mb-4`}>
                <div className="d-flex align-items-center">
                  {verification.valid ? (
                    <svg width="24" height="24" fill="currentColor" className="me-2" viewBox="0 0 16 16">
                      <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                    </svg>
                  ) : (
                    <svg width="24" height="24" fill="currentColor" className="me-2" viewBox="0 0 16 16">
                      <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293 5.354 4.646z"/>
                    </svg>
                  )}
                  <strong>
                    {verification.valid
                      ? 'All votes verified - blockchain integrity confirmed'
                      : 'Verification failed - potential tampering detected'}
                  </strong>
                </div>
              </div>

              <div className="row g-3">
                <div className="col-md-4">
                  <div className="bg-light rounded p-3">
                    <small className="text-muted d-block mb-1">Blocks Verified</small>
                    <strong>{verification.blocks_verified || 0}</strong>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="bg-light rounded p-3">
                    <small className="text-muted d-block mb-1">Hash Chain</small>
                    <strong className={verification.valid ? 'text-success' : 'text-danger'}>
                      {verification.valid ? 'Intact' : 'Broken'}
                    </strong>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="bg-light rounded p-3">
                    <small className="text-muted d-block mb-1">Verified At</small>
                    <strong>{new Date().toLocaleString()}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ElectionResults;
