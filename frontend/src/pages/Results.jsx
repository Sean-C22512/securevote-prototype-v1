import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchElections, fetchElectionResults } from '../api/apiClient';

const Results = () => {
  const [elections, setElections] = useState([]);
  const [selectedElection, setSelectedElection] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    loadElections();
  }, []);

  useEffect(() => {
    if (selectedElection) {
      loadResults();
    }
  }, [selectedElection]);

  const loadElections = async () => {
    try {
      const data = await fetchElections();
      // Show active and closed elections
      const visibleElections = (data.elections || []).filter(
        e => e.status === 'active' || e.status === 'closed'
      );
      setElections(visibleElections);

      // Auto-select if only one election
      if (visibleElections.length === 1) {
        setSelectedElection(visibleElections[0].election_id);
      }
    } catch (err) {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    setLoading(true);
    try {
      const data = await fetchElectionResults(selectedElection);
      setResults(data);
    } catch (err) {
      setError('Failed to load results');
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

  const getMaxVotes = () => {
    if (!results?.results) return 0;
    return Math.max(...results.results.map(r => r.votes), 1);
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      {/* Navigation Bar */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <Link className="navbar-brand fw-bold" to="/dashboard" style={{ color: '#6f42c1' }}>
            SecureVote
          </Link>
          <div className="d-flex align-items-center gap-3">
            <Link to="/dashboard" className="nav-link">Home</Link>
            <Link to="/cast-vote" className="nav-link">Elections</Link>
            <span className="nav-link active" style={{ color: '#6f42c1' }}>Results</span>
            <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container py-5">
        <div className="mb-4">
          <h1 className="fw-bold mb-2">Election Results</h1>
          <p className="text-muted">View live results for active and completed elections</p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        {/* Election Selector */}
        {elections.length > 1 && (
          <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '16px' }}>
            <div className="card-body p-4">
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
          </div>
        )}

        {loading ? (
          <div className="text-center py-5">
            <div className="spinner-border text-secondary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : elections.length === 0 ? (
          <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
            <div className="card-body text-center py-5">
              <p className="text-muted mb-0">No elections with results available</p>
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
            {/* Results Chart */}
            <div className="col-lg-8">
              <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                <div className="card-header bg-white border-0 py-3 px-4">
                  <h5 className="mb-0 fw-bold">{results.title || 'Results'}</h5>
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
                    <p className="text-muted text-center py-4">No votes cast yet</p>
                  )}
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="col-lg-4">
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
                  <p className="text-muted mb-2">Status</p>
                  <span className={`badge fs-6 ${results.status === 'active' ? 'bg-success' : 'bg-secondary'}`}>
                    {results.status === 'active' ? 'Live' : 'Closed'}
                  </span>
                </div>
              </div>

              {results.results && results.results.length > 0 && results.total_votes > 0 && (
                <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
                  <div className="card-body p-4 text-center">
                    <p className="text-muted mb-2">Leading</p>
                    <h5 className="fw-bold mb-0" style={{ color: '#198754' }}>
                      {results.results[0]?.name}
                    </h5>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default Results;

