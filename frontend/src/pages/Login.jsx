import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { startAuthentication } from '@simplewebauthn/browser';
import { login, webAuthnLoginBegin, webAuthnLoginComplete } from '../api/apiClient';

const supportsWebAuthn = typeof window !== 'undefined' && !!window.PublicKeyCredential;

const Login = () => {
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [biometricLoading, setBiometricLoading] = useState(false);
  const navigate = useNavigate();

  const routeByRole = (role) => {
    switch (role) {
      case 'admin':    navigate('/admin');     break;
      case 'official': navigate('/official');  break;
      default:         navigate('/dashboard'); break;
    }
  };

  const storeSession = (data) => {
    localStorage.setItem('token',     data.token);
    localStorage.setItem('role',      data.role);
    localStorage.setItem('studentId', data.student_id);
  };

  // ── Password login ────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await login(studentId, password);
      storeSession(data);
      routeByRole(data.role);
    } catch (err) {
      setError(err?.error || err?.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  // ── Biometric login ───────────────────────────────────────────────────────
  const handleBiometricLogin = async () => {
    if (!studentId.trim()) {
      setError('Please enter your Student ID above before using biometric login.');
      return;
    }

    setError('');
    setBiometricLoading(true);

    try {
      // 1. Get authentication options from server
      const options = await webAuthnLoginBegin(studentId);

      // 2. Invoke browser WebAuthn API (triggers TouchID / FaceID / Hello)
      const assertion = await startAuthentication(options);

      // 3. Verify with server and receive JWT
      const data = await webAuthnLoginComplete(studentId, assertion);
      storeSession(data);
      routeByRole(data.role);
    } catch (err) {
      if (err?.name === 'NotAllowedError') {
        setError('Biometric cancelled or not recognised.');
      } else {
        setError(err?.error || err?.message || 'Biometric login failed. Please try again.');
      }
    } finally {
      setBiometricLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="vote-card" style={{ maxWidth: '420px' }}>
        <div className="text-center mb-4">
          <h2 className="vote-title">SecureVote</h2>
          <p className="vote-subtitle">TU Dublin Student Elections</p>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        {/* ── Password form ── */}
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="form-label">Student ID</label>
            <input
              type="text"
              className="form-control"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value.toUpperCase())}
              required
              placeholder="e.g. C22512345"
              disabled={loading || biometricLoading}
            />
          </div>

          <div className="mb-4">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-control"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
              disabled={loading || biometricLoading}
            />
          </div>

          <button type="submit" className="submit-btn" disabled={loading || biometricLoading}>
            {loading ? 'Signing in\u2026' : 'Sign In'}
          </button>
        </form>

        {/* ── Biometric login ── */}
        {supportsWebAuthn ? (
          <>
            <hr className="my-4" />
            <div className="text-center">
              <p className="text-muted mb-3" style={{ fontSize: '0.85rem' }}>
                Or sign in with a registered biometric
              </p>
              <button
                type="button"
                className="btn btn-outline-secondary w-100"
                style={{ borderRadius: '12px', fontWeight: 600, padding: '0.75rem' }}
                onClick={handleBiometricLogin}
                disabled={loading || biometricLoading}
              >
                {biometricLoading ? 'Waiting for biometric\u2026' : '\uD83D\uDD10 Login with Biometrics'}
              </button>
            </div>
          </>
        ) : (
          <p className="text-center text-muted mt-3" style={{ fontSize: '0.8rem' }}>
            Biometric login is not supported in this browser or context.
          </p>
        )}

        <div className="text-center mt-4">
          <p className="text-muted mb-0">
            Don't have an account?{' '}
            <Link to="/register" className="text-decoration-none" style={{ color: '#6f42c1', fontWeight: 500 }}>
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
