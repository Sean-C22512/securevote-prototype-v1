import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchElections, castVote } from '../api/apiClient';

const CastVote = () => {
  const [elections, setElections] = useState([]);
  const [selectedElection, setSelectedElection] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadElections();
  }, []);

  const loadElections = async () => {
    try {
      const data = await fetchElections('active');
      const activeElections = (data.elections || []).filter(e => e.status === 'active');
      setElections(activeElections);

      // Auto-select if only one election
      if (activeElections.length === 1) {
        setSelectedElection(activeElections[0]);
      }
    } catch (err) {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedCandidate || !selectedElection) {
      setError('Please select a candidate');
      return;
    }

    setSubmitting(true);
    try {
      await castVote(selectedCandidate, selectedElection.election_id);
      setSuccess(true);
      setError('');
    } catch (err) {
      setError(err?.error || 'Failed to cast vote. You may have already voted in this election.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const handleBack = () => {
    setSelectedElection(null);
    setSelectedCandidate(null);
    setError('');
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
            <span className="nav-link active" style={{ color: '#6f42c1' }}>Elections</span>
            <Link to="/results" className="nav-link">Results</Link>
            <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="page-container">
        <div className="vote-card">
          {success ? (
            <div className="text-center">
              <div className="rounded-circle mx-auto mb-4 d-flex align-items-center justify-content-center"
                   style={{ width: '80px', height: '80px', backgroundColor: '#d1e7dd' }}>
                <svg width="40" height="40" fill="#198754" viewBox="0 0 16 16">
                  <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                </svg>
              </div>
              <h2 className="vote-title" style={{ color: '#198754' }}>Vote Submitted!</h2>
              <p className="vote-subtitle">Thank you for participating in the election.</p>
              <p className="text-muted mb-4">Your vote has been securely recorded on the blockchain.</p>
              <Link to="/results" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                View Results
              </Link>
            </div>
          ) : loading ? (
            <div className="text-center py-5">
              <div className="spinner-border text-secondary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              <p className="text-muted mt-3">Loading elections...</p>
            </div>
          ) : elections.length === 0 ? (
            <div className="text-center py-4">
              <div className="rounded-circle mx-auto mb-4 d-flex align-items-center justify-content-center"
                   style={{ width: '80px', height: '80px', backgroundColor: '#e9ecef' }}>
                <svg width="40" height="40" fill="#6c757d" viewBox="0 0 16 16">
                  <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                  <path d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 4.995z"/>
                </svg>
              </div>
              <h2 className="vote-title">No Active Elections</h2>
              <p className="vote-subtitle">There are no elections currently open for voting.</p>
              <Link to="/dashboard" className="submit-btn text-decoration-none d-inline-block px-5 py-3">
                Back to Dashboard
              </Link>
            </div>
          ) : !selectedElection ? (
            <>
              <h2 className="vote-title text-center">Select an Election</h2>
              <p className="vote-subtitle text-center">Choose an election to cast your vote.</p>

              {error && <div className="alert alert-danger">{error}</div>}

              <div className="elections-list">
                {elections.map((election) => (
                  <div
                    key={election.election_id}
                    className="candidate-option"
                    onClick={() => setSelectedElection(election)}
                  >
                    <div>
                      <span className="candidate-name d-block">{election.title}</span>
                      {election.description && (
                        <small className="text-muted">{election.description}</small>
                      )}
                    </div>
                    <span style={{ color: '#6f42c1' }}>
                      {election.candidates?.length || 0} candidates
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="d-flex align-items-center mb-4">
                <button
                  className="btn btn-link p-0 me-3"
                  onClick={handleBack}
                  style={{ color: '#6f42c1' }}
                >
                  <svg width="20" height="20" fill="currentColor" viewBox="0 0 16 16">
                    <path fillRule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"/>
                  </svg>
                </button>
                <div>
                  <h2 className="vote-title mb-0">{selectedElection.title}</h2>
                  <p className="vote-subtitle mb-0">{selectedElection.description || 'Select a candidate below'}</p>
                </div>
              </div>

              {error && <div className="alert alert-danger">{error}</div>}

              <div className="candidates-list">
                {selectedElection.candidates && selectedElection.candidates.length > 0 ? (
                  selectedElection.candidates.map((candidate) => (
                    <div
                      key={candidate.candidate_id}
                      className={`candidate-option ${selectedCandidate === candidate.candidate_id ? 'selected' : ''}`}
                      onClick={() => setSelectedCandidate(candidate.candidate_id)}
                    >
                      <div>
                        <span className="candidate-name d-block">{candidate.name}</span>
                        {candidate.description && (
                          <small className="text-muted">{candidate.description}</small>
                        )}
                      </div>
                      {selectedCandidate === candidate.candidate_id && (
                        <svg width="24" height="24" fill="#6f42c1" viewBox="0 0 16 16">
                          <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                        </svg>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-muted text-center py-3">No candidates available</p>
                )}
              </div>

              <button
                className="submit-btn"
                onClick={handleSubmit}
                disabled={submitting || !selectedCandidate}
              >
                {submitting ? 'Submitting...' : 'Submit Vote'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default CastVote;

