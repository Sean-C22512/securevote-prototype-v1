import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchCandidates, castVote } from '../api/apiClient';

const CastVote = () => {
  const [candidates, setCandidates] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const loadCandidates = async () => {
      try {
        const data = await fetchCandidates();
        setCandidates(data);
      } catch (err) {
        setError('Failed to load candidates');
      } finally {
        setLoading(false);
      }
    };
    loadCandidates();
  }, []);

  const handleSubmit = async () => {
    if (!selectedCandidate) {
      setError('Please select a candidate');
      return;
    }

    try {
      await castVote(selectedCandidate);
      setSuccess(true);
      setError('');
    } catch (err) {
      setError(err.error || 'Failed to cast vote');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  return (
    <div>
      {/* Navigation Bar */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white mb-4 px-4">
        <div className="container-fluid">
          <Link className="navbar-brand" to="/dashboard">
             <span style={{ marginRight: '8px' }}>🗳️</span> SecureVote
          </Link>
          <div className="d-flex">
            <Link to="/dashboard" className="nav-link mx-2">Home</Link>
            <span className="nav-link mx-2 active">Elections</span>
            <Link to="/results" className="nav-link mx-2">Past Results</Link>
            <span className="nav-link mx-2" style={{cursor: 'not-allowed', opacity: 0.5}}>Settings</span>
            <button onClick={handleLogout} className="btn btn-link nav-link text-danger" style={{textDecoration: 'none'}}>Logout</button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="page-container">
        <div className="vote-card">
          {success ? (
            <div className="text-center">
              <h2 className="text-success mb-3">Vote Submitted!</h2>
              <p className="mb-4">Thank you for participating in the election.</p>
              <Link to="/results" className="btn btn-primary">View Results</Link>
            </div>
          ) : (
            <>
              <h2 className="vote-title text-center">Choose Your TU-857/1 Class Rep</h2>
              <p className="vote-subtitle text-center">Select one option below to cast your vote.</p>

              {error && <div className="alert alert-danger">{error}</div>}
              
              {loading ? (
                <div className="text-center py-4">Loading candidates...</div>
              ) : (
                <div className="candidates-list">
                  {candidates.map((candidate) => (
                    <div 
                      key={candidate.id}
                      className={`candidate-option ${selectedCandidate === candidate.id ? 'selected' : ''}`}
                      onClick={() => setSelectedCandidate(candidate.id)}
                    >
                      <span className="candidate-name">{candidate.name}</span>
                      {selectedCandidate === candidate.id && (
                        <span className="text-primary">✓</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <button 
                className="submit-btn"
                onClick={handleSubmit}
                disabled={loading || !selectedCandidate}
              >
                Submit Vote
              </button>
            </>
          )}
        </div>
      </div>
      
      {/* Placeholder Comments */}
      {/* Future: Results visualisation charts */}
      {/* Future: Election creation (admin) */}
      {/* Future: Admin dashboard */}
      {/* Future: UX enhancements */}
    </div>
  );
};

export default CastVote;

