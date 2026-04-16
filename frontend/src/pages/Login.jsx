import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Fingerprint, Gem } from 'lucide-react';
import { startAuthentication } from '@simplewebauthn/browser';
import { login, webAuthnLoginBegin, webAuthnLoginComplete } from '../api/apiClient';

// Check once at module level whether this browser supports WebAuthn (PassKeys / biometrics)
const supportsWebAuthn = typeof window !== 'undefined' && !!window.PublicKeyCredential;

const Login = () => {
  // Track the values typed into the Student ID and password fields
  const [studentId, setStudentId]           = useState('');
  const [password, setPassword]             = useState('');
  // Error message shown in the red alert banner
  const [error, setError]                   = useState('');
  // True while the normal password login API call is in flight
  const [loading, setLoading]               = useState(false);
  // True while the biometric login flow is waiting for the device authenticator
  const [biometricLoading, setBiometricLoading] = useState(false);
  const navigate = useNavigate();

  // Send the user to the correct dashboard based on their role after login
  const routeByRole = (role) => {
    switch (role) {
      case 'admin':    navigate('/admin');     break;
      case 'official': navigate('/official');  break;
      default:         navigate('/dashboard'); break;
    }
  };

  // Persist the JWT token and user info in localStorage so they survive page refreshes
  const storeSession = (data) => {
    localStorage.setItem('token',     data.token);
    localStorage.setItem('role',      data.role);
    localStorage.setItem('studentId', data.student_id);
  };

  // Handle normal username + password form submission
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

  // Handle biometric (WebAuthn) login — requires the student ID to be filled in first
  // Step 1: ask the backend for a challenge, Step 2: prompt the device, Step 3: verify the response
  const handleBiometricLogin = async () => {
    if (!studentId.trim()) {
      setError('Enter your Student ID above before using biometric login.');
      return;
    }
    setError('');
    setBiometricLoading(true);
    try {
      const options   = await webAuthnLoginBegin(studentId);
      const assertion = await startAuthentication(options);
      const data      = await webAuthnLoginComplete(studentId, assertion);
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

  // Combine both loading states so we can disable all inputs while any request is in flight
  const busy = loading || biometricLoading;

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--sv-bg)' }}>

      {/* ── Left branding panel (desktop only) ── */}
      <div className="sv-login-panel hidden lg:flex flex-col justify-between p-14 relative"
           style={{ width: 400, borderRight: '1px solid rgba(0,159,227,0.08)', flexShrink: 0 }}>

        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <Gem className="w-5 h-5 text-tud-cyan" />
          <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote</span>
        </div>

        {/* Hero text */}
        <div>
          <p className="font-display font-black leading-[0.88] tracking-tight"
             style={{ fontSize: 80, color: 'rgba(228,235,248,0.90)' }}>
            SECURE<br />VOTE
          </p>
          <p className="font-mono text-[10px] tracking-[0.20em] mt-5"
             style={{ color: 'rgba(0,159,227,0.45)' }}>
            TU DUBLIN &middot; 2026
          </p>
        </div>

        {/* Bottom caption */}
        <div style={{ borderTop: '1px solid rgba(0,159,227,0.10)', paddingTop: 20 }}>
          <p className="font-mono text-[10px] leading-loose tracking-[0.14em] uppercase"
             style={{ color: 'rgba(228,235,248,0.22)' }}>
            End-to-end encrypted<br />
            Blockchain verified<br />
            WebAuthn ready
          </p>
        </div>

        {/* Decorative corner accent */}
        <div className="absolute bottom-0 right-0 w-16 h-16 opacity-20"
             style={{ borderTop: '1px solid var(--sv-cyan)', borderLeft: '1px solid var(--sv-cyan)' }} />
      </div>

      {/* ── Right form panel ── */}
      <div className="sv-bg flex-1 flex items-center justify-center p-8">
        {/* Fade-and-slide in animation on mount */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.40, ease: 'easeOut' }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo — only shown when the left panel is hidden */}
          <div className="flex lg:hidden items-center gap-2 mb-12">
            <Gem className="w-5 h-5 text-tud-cyan" />
            <span className="font-display font-bold text-white tracking-wide">SecureVote</span>
          </div>

          <h2 className="font-display font-bold text-white mb-1" style={{ fontSize: 28, letterSpacing: '-0.02em' }}>
            Sign in
          </h2>
          <p className="text-sm mb-10" style={{ color: 'var(--sv-text-dim)' }}>
            TU Dublin Student Elections
          </p>

          {/* Animated error banner — only rendered when there is an error message */}
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="sv-alert-error mb-8"
            >
              {error}
            </motion.div>
          )}

          {/* Password login form */}
          <form onSubmit={handleSubmit} className="space-y-8">
            <div>
              <label className="sv-label">Student ID</label>
              {/* Force uppercase input so IDs like C22512345 are consistent */}
              <input
                type="text"
                className="sv-input"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value.toUpperCase())}
                placeholder="e.g. C22512345"
                required
                disabled={busy}
                autoComplete="username"
              />
            </div>

            <div>
              <label className="sv-label">Password</label>
              <input
                type="password"
                className="sv-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                disabled={busy}
                autoComplete="current-password"
              />
            </div>

            {/* Submit button — scales slightly on hover/tap for tactile feel; freezes scale when busy */}
            <motion.button
              whileHover={{ scale: busy ? 1 : 1.015 }}
              whileTap={{ scale: busy ? 1 : 0.980 }}
              type="submit"
              className="sv-btn-primary w-full"
              disabled={busy}
            >
              {loading ? 'Signing in\u2026' : (<>Sign In <ArrowRight className="w-3.5 h-3.5" /></>)}
            </motion.button>
          </form>

          {/* Biometric login section — only rendered if the browser supports WebAuthn */}
          {supportsWebAuthn && (
            <>
              {/* Visual divider between the two login methods */}
              <div className="sv-divider my-8 flex items-center justify-center">
                <span className="font-mono text-[10px] px-4 tracking-[0.14em]"
                      style={{ color: 'var(--sv-text-muted)', background: 'var(--sv-bg)', position: 'relative', zIndex: 1 }}>
                  OR
                </span>
              </div>
              {/* Biometric login button — triggers WebAuthn challenge flow */}
              <motion.button
                whileHover={{ scale: busy ? 1 : 1.015 }}
                whileTap={{ scale: busy ? 1 : 0.980 }}
                type="button"
                className="sv-btn-outline w-full"
                onClick={handleBiometricLogin}
                disabled={busy}
              >
                <Fingerprint className="w-3.5 h-3.5" />
                {biometricLoading ? 'Waiting for biometric\u2026' : 'Biometric Login'}
              </motion.button>
            </>
          )}

          {/* Link to registration page for users who don't yet have an account */}
          <p className="text-center text-sm mt-10" style={{ color: 'var(--sv-text-muted)' }}>
            No account?{' '}
            <Link to="/register"
                  className="font-semibold transition-colors"
                  style={{ color: 'var(--sv-cyan)', textDecoration: 'none' }}
                  onMouseEnter={e => e.target.style.color = '#20b3f5'}
                  onMouseLeave={e => e.target.style.color = 'var(--sv-cyan)'}>
              Register
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default Login;
