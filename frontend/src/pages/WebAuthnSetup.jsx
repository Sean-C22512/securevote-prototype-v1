import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Fingerprint, Key, Plus, ChevronLeft, CheckCircle2, Loader2, Gem } from 'lucide-react';
import { startRegistration } from '@simplewebauthn/browser';
import { getCurrentUser, webAuthnRegisterBegin, webAuthnRegisterComplete } from '../api/apiClient';

const WebAuthnSetup = () => {
  // Array of credential objects already registered for this user
  const [credentials,      setCredentials]      = useState([]);
  // Separate count from the backend (mirrors credentials.length, surfaced as a badge)
  const [credentialCount,  setCredentialCount]  = useState(0);
  // True while the initial user profile is being fetched
  const [loading,          setLoading]          = useState(true);
  // True while the WebAuthn registration ceremony is in progress
  const [registering,      setRegistering]      = useState(false);
  // Success message shown after a new biometric is added
  const [message,          setMessage]          = useState('');
  // Error message shown if registration fails
  const [error,            setError]            = useState('');

  // Load the current user's registered WebAuthn credentials from the backend
  // Wrapped in useCallback so it can be safely called after a new registration completes
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

  // Fetch credentials on mount
  useEffect(() => { loadCredentials(); }, [loadCredentials]);

  // Run the full WebAuthn registration ceremony:
  // Step 1 — ask the backend for a challenge (server-side nonce)
  // Step 2 — prompt the browser to generate a credential using the device authenticator
  // Step 3 — send the signed credential back to the backend for verification and storage
  const handleAddBiometric = async () => {
    setError('');
    setMessage('');
    setRegistering(true);
    try {
      const options              = await webAuthnRegisterBegin();
      const registrationResponse = await startRegistration(options);
      await webAuthnRegisterComplete(registrationResponse);
      setMessage('Biometric added successfully!');
      // Refresh the credentials list so the new device appears immediately
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
    <div className="sv-bg min-h-screen">

      {/* Nav */}
      <nav className="sv-nav px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gem className="w-4 h-4 text-tud-cyan" />
            <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote</span>
          </div>
        </div>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-12">

        {/* Back link to the student dashboard */}
        <Link to="/dashboard"
              style={{ textDecoration: 'none' }}
              className="sv-btn-ghost pl-0 text-xs mb-10 inline-flex">
          <ChevronLeft className="w-3.5 h-3.5" /> Back to Dashboard
        </Link>

        {/* Page fade-in animation */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.38 }}
        >
          {/* Header — icon, section label, and page title */}
          <div className="flex items-start gap-4 mb-10">
            <div className="w-12 h-12 flex items-center justify-center shrink-0"
                 style={{ background: 'rgba(0,159,227,0.08)', border: '1px solid rgba(0,159,227,0.16)', borderRadius: 2 }}>
              <Fingerprint className="w-6 h-6 text-tud-cyan" />
            </div>
            <div>
              <p className="font-mono text-[10px] tracking-[0.16em] mb-1" style={{ color: 'var(--sv-text-muted)' }}>
                SECURITY
              </p>
              <h1 className="font-display font-bold text-white text-2xl" style={{ letterSpacing: '-0.02em' }}>
                Biometric Login
              </h1>
              <p className="text-sm mt-0.5" style={{ color: 'var(--sv-text-dim)' }}>
                Register TouchID, FaceID, or Windows Hello
              </p>
            </div>
          </div>

          <div className="sv-card p-8">

            {/* Success banner — appears after a new biometric is successfully registered */}
            {message && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="sv-alert-success mb-6"
              >
                <CheckCircle2 className="w-4 h-4 shrink-0" /> {message}
              </motion.div>
            )}

            {/* Error banner */}
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="sv-alert-error mb-6"
              >
                {error}
              </motion.div>
            )}

            {/* Registered devices section — lists all passkeys already on the account */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <p className="sv-label" style={{ marginBottom: 0 }}>Registered Devices</p>
                {/* Badge showing total active credential count */}
                {credentialCount > 0 && (
                  <span className="sv-badge-official">{credentialCount} active</span>
                )}
              </div>

              {loading ? (
                <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--sv-text-muted)' }}>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="font-mono text-xs tracking-[0.10em]">LOADING&hellip;</span>
                </div>

              ) : credentials.length === 0 ? (
                // Empty state — user has no biometrics registered yet
                <div className="flex items-center gap-3 p-4"
                     style={{ border: '1px solid var(--sv-border)', borderRadius: 2,
                              background: 'rgba(228,235,248,0.02)' }}>
                  <Key className="w-4 h-4 shrink-0" style={{ color: 'var(--sv-text-muted)' }} />
                  <p className="text-sm italic" style={{ color: 'var(--sv-text-muted)' }}>
                    No biometric devices registered yet.
                  </p>
                </div>

              ) : (
                // Render a row for each registered passkey, showing its name and registration date
                <div className="space-y-2">
                  {credentials.map((cred, i) => (
                    <div key={cred.credential_id || i}
                         className="flex items-center gap-3 p-4"
                         style={{ border: '1px solid rgba(0,159,227,0.14)', borderRadius: 2,
                                  background: 'rgba(0,159,227,0.04)' }}>
                      <Key className="w-4 h-4 shrink-0 text-tud-cyan" />
                      <div className="flex-1">
                        <p className="font-display font-semibold text-white text-sm">
                          {cred.friendly_name || 'Passkey'}
                        </p>
                        {cred.created_at && (
                          <p className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--sv-text-muted)' }}>
                            Added {new Date(cred.created_at).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                      <span className="sv-badge-official">Active</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="sv-divider mb-8" />

            {/* Add Biometric button — triggers the WebAuthn registration flow */}
            <motion.button
              whileHover={{ scale: registering ? 1 : 1.012 }}
              whileTap={{ scale: registering ? 1 : 0.988 }}
              onClick={handleAddBiometric}
              disabled={registering}
              className="sv-btn-primary"
            >
              {registering
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Waiting for biometric&hellip;</>
                : <><Plus className="w-3.5 h-3.5" /> Add Biometric</>
              }
            </motion.button>
          </div>

          {/* Privacy note — reassure the user the private key never leaves their device */}
          <p className="font-mono text-[10px] leading-relaxed tracking-[0.08em] mt-5"
             style={{ color: 'var(--sv-text-muted)' }}>
            Your biometric credential is stored only on this device.
            The private key never leaves your device&apos;s Secure Enclave.
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default WebAuthnSetup;
