import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register, getPasswordRequirements } from '../api/apiClient';

const Register = () => {
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [requirements, setRequirements] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Load password requirements
    const loadRequirements = async () => {
      try {
        const data = await getPasswordRequirements();
        setRequirements(data);
      } catch (err) {
        console.error('Failed to load password requirements');
      }
    };
    loadRequirements();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // Client-side validation
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      await register(studentId, password, email || undefined);
      setSuccess('Registration successful! Redirecting to login...');
      setTimeout(() => navigate('/'), 2000);
    } catch (err) {
      if (err?.details) {
        setError(err.details.join('. '));
      } else {
        setError(err?.error || err?.message || 'Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="vote-card" style={{ maxWidth: '460px' }}>
        <div className="text-center mb-4">
          <h2 className="vote-title">Create Account</h2>
          <p className="vote-subtitle">Register for SecureVote</p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="form-label">Student ID <span className="text-danger">*</span></label>
            <input
              type="text"
              className="form-control"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value.toUpperCase())}
              required
              placeholder="e.g. C22512345"
              disabled={loading}
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Email <span className="text-muted">(optional)</span></label>
            <input
              type="email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="student@tudublin.ie"
              disabled={loading}
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Password <span className="text-danger">*</span></label>
            <input
              type="password"
              className="form-control"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Create a password"
              disabled={loading}
            />
            {requirements && (
              <small className="text-muted">
                Min {requirements.min_length} characters, include uppercase, lowercase, and a number
              </small>
            )}
          </div>

          <div className="mb-4">
            <label className="form-label">Confirm Password <span className="text-danger">*</span></label>
            <input
              type="password"
              className="form-control"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder="Confirm your password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="submit-btn"
            disabled={loading}
          >
            {loading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="text-center mt-4">
          <p className="text-muted mb-0">
            Already have an account?{' '}
            <Link to="/" className="text-decoration-none" style={{ color: '#6f42c1', fontWeight: 500 }}>
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
