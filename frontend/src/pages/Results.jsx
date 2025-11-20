import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchResults } from '../api/apiClient';

const Results = () => {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadResults = async () => {
      try {
        const data = await fetchResults();
        setResults(data);
      } catch (err) {
        setError('Failed to load results');
      } finally {
        setLoading(false);
      }
    };
    loadResults();
  }, []);

  return (
    <div className="container mt-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1>Live Results</h1>
        <Link to="/dashboard" className="btn btn-outline-secondary">Back to Dashboard</Link>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <div className="text-center">Loading...</div>
      ) : (
        <div className="card shadow-sm">
          <div className="card-body">
            {Object.keys(results).length === 0 ? (
              <p className="text-center my-4">No votes cast yet.</p>
            ) : (
              <ul className="list-group list-group-flush">
                {Object.entries(results).map(([candidate, count]) => (
                  <li key={candidate} className="list-group-item d-flex justify-content-between align-items-center py-3">
                    <span className="h5 mb-0">{candidate}</span>
                    <span className="badge bg-primary rounded-pill fs-6">{count} Votes</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Results;

