import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { startRegistration } from '@simplewebauthn/browser';
import { getCurrentUser, webAuthnRegisterBegin, webAuthnRegisterComplete } from '../api/apiClient';

const WebAuthnSetup = () => {
  const [credentials, setCredentials] = useState([]);
  const [credentialCount, setCredentialCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [registering, setRegistering] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadCredentials = useCallback(async () => {
    try {
      const data = await getCurrentUser();
      setCredentials(data.webauthn_credentials || []);
      setCredentialCount(data.credential_count || 0);
    } catch {
      setError('Failed to load credential information.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCredentials();
  }, [loadCredentials]);

  const handleAddBiometric = async () => {
    setError('');
    setMessage('');
    setRegistering(true);

    try {
      // Step 1: get registration options from server
      const options = await webAuthnRegisterBegin();

      // Step 2: invoke browser's WebAuthn API (triggers TouchID / FaceID / Hello)
      const registrationResponse = await startRegistration(options);

      // Step 3: send result to server for verification
      await webAuthnRegisterComplete(registrationResponse);

      setMessage('Biometric added successfully!');
      await loadCredentials();
    } catch (err) {
      if (err?.name === 'NotAllowedError') {
        setError('Biometric cancelled or not recognised.');
      } else if (err?.name === 'InvalidStateError') {
        setError('This device is already registered.');
      } else {
        setError(err?.error || err?.message || 'Failed to register biometric. Please try again.');
      }
    } finally {
      setRegistering(false);
    }
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>SecureVote</span>
        </div>
      </nav>

      <div className="container py-5" style={{ maxWidth: '640px' }}>
        <div className="mb-4">
          <Link to="/dashboard" className="text-decoration-none text-muted" style={{ fontSize: '0.9rem' }}>
            &larr; Back to Dashboard
          </Link>
        </div>

        <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
          <div className="card-body p-5">
            <h2 className="fw-bold mb-1">Biometric Login</h2>
            <p className="text-muted mb-4">
              Register your device's biometric (TouchID, FaceID, or Windows Hello) as a
              passwordless login method.
            </p>

            {message && (
              <div className="alert alert-success">{message}</div>
            )}
            {error && (
              <div className="alert alert-danger">{error}</div>
            )}

            {loading ? (
              <p className="text-muted">Loading credentials&hellip;</p>
            ) : (
              <>
                <h5 className="fw-semibold mb-3">
                  Registered devices
                  {credentialCount > 0 && (
                    <span className="badge ms-2" style={{ backgroundColor: '#6f42c1', fontSize: '0.75rem' }}>
                      {credentialCount}
                    </span>
                  )}
                </h5>

                {credentials.length === 0 ? (
                  <p className="text-muted fst-italic mb-4">No biometric devices registered yet.</p>
                ) : (
                  <ul className="list-group list-group-flush mb-4">
                    {credentials.map((cred, i) => (
                      <li key={cred.credential_id || i} className="list-group-item px-0">
                        <div className="d-flex align-items-center">
                          <span className="me-3" style={{ fontSize: '1.4rem' }}>&#128273;</span>
                          <div>
                            <div className="fw-medium">{cred.friendly_name || 'Passkey'}</div>
                            {cred.created_at && (
                              <small className="text-muted">
                                Added {new Date(cred.created_at).toLocaleDateString()}
                              </small>
                            )}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}

                <button
                  className="submit-btn"
                  onClick={handleAddBiometric}
                  disabled={registering}
                  style={{ width: 'auto', paddingLeft: '2rem', paddingRight: '2rem' }}
                >
                  {registering ? 'Waiting for biometric\u2026' : '\uD83D\uDD10 Add Biometric'}
                </button>
              </>
            )}
          </div>
        </div>

        <p className="text-muted mt-4" style={{ fontSize: '0.8rem' }}>
          Your biometric credential is stored only on this device. The private key never leaves
          your device's Secure Enclave.
        </p>
      </div>
    </div>
  );
};

export default WebAuthnSetup;
