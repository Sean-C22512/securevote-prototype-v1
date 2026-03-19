import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, CheckCircle2, Gem } from 'lucide-react';
import { register, getPasswordRequirements } from '../api/apiClient';

const Register = () => {
  const [studentId,       setStudentId]       = useState('');
  const [password,        setPassword]        = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email,           setEmail]           = useState('');
  const [error,           setError]           = useState('');
  const [success,         setSuccess]         = useState('');
  const [loading,         setLoading]         = useState(false);
  const [requirements,    setRequirements]    = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getPasswordRequirements()
      .then(setRequirements)
      .catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      await register(studentId, password, email || undefined);
      setSuccess('Registration successful! Redirecting to login\u2026');
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
    <div className="min-h-screen flex" style={{ background: 'var(--sv-bg)' }}>

      {/* Left panel */}
      <div className="sv-login-panel hidden lg:flex flex-col justify-between p-14 relative"
           style={{ width: 400, borderRight: '1px solid rgba(0,159,227,0.08)', flexShrink: 0 }}>
        <div className="flex items-center gap-2.5">
          <Gem className="w-5 h-5 text-tud-cyan" />
          <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote</span>
        </div>
        <div>
          <p className="font-display font-black leading-[0.88] tracking-tight"
             style={{ fontSize: 72, color: 'rgba(228,235,248,0.90)' }}>
            CREATE<br />ACCOUNT
          </p>
          <p className="font-mono text-[10px] tracking-[0.20em] mt-5"
             style={{ color: 'rgba(0,159,227,0.45)' }}>
            TU DUBLIN &middot; 2026
          </p>
        </div>
        <div style={{ borderTop: '1px solid rgba(0,159,227,0.10)', paddingTop: 20 }}>
          <p className="font-mono text-[10px] leading-loose tracking-[0.14em] uppercase"
             style={{ color: 'rgba(228,235,248,0.22)' }}>
            Your identity is verified<br />
            by your student credentials.<br />
            One account per student.
          </p>
        </div>
        <div className="absolute bottom-0 right-0 w-16 h-16 opacity-20"
             style={{ borderTop: '1px solid var(--sv-cyan)', borderLeft: '1px solid var(--sv-cyan)' }} />
      </div>

      {/* Right form panel */}
      <div className="sv-bg flex-1 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.40, ease: 'easeOut' }}
          className="w-full max-w-sm"
        >
          <div className="flex lg:hidden items-center gap-2 mb-12">
            <Gem className="w-5 h-5 text-tud-cyan" />
            <span className="font-display font-bold text-white tracking-wide">SecureVote</span>
          </div>

          <h2 className="font-display font-bold text-white mb-1" style={{ fontSize: 28, letterSpacing: '-0.02em' }}>
            Create account
          </h2>
          <p className="text-sm mb-10" style={{ color: 'var(--sv-text-dim)' }}>
            Register for TU Dublin Student Elections
          </p>

          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="sv-alert-error mb-8"
            >
              {error}
            </motion.div>
          )}

          {success && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="sv-alert-success mb-8"
            >
              <CheckCircle2 className="w-4 h-4 shrink-0" /> {success}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-7">
            <div>
              <label className="sv-label">
                Student ID <span style={{ color: 'var(--sv-magenta)' }}>*</span>
              </label>
              <input
                type="text"
                className="sv-input"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value.toUpperCase())}
                required
                placeholder="e.g. C22512345"
                disabled={loading}
              />
            </div>

            <div>
              <label className="sv-label">
                Email <span className="normal-case font-normal" style={{ color: 'var(--sv-text-muted)', letterSpacing: 0 }}>(optional)</span>
              </label>
              <input
                type="email"
                className="sv-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@tudublin.ie"
                disabled={loading}
              />
            </div>

            <div>
              <label className="sv-label">
                Password <span style={{ color: 'var(--sv-magenta)' }}>*</span>
              </label>
              <input
                type="password"
                className="sv-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Create a strong password"
                disabled={loading}
                autoComplete="new-password"
              />
              {requirements && (
                <p className="font-mono text-[10px] mt-2" style={{ color: 'var(--sv-text-muted)' }}>
                  Min {requirements.min_length} chars &middot; uppercase &middot; lowercase &middot; number
                </p>
              )}
            </div>

            <div>
              <label className="sv-label">
                Confirm Password <span style={{ color: 'var(--sv-magenta)' }}>*</span>
              </label>
              <input
                type="password"
                className="sv-input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                placeholder="Repeat your password"
                disabled={loading}
                autoComplete="new-password"
              />
            </div>

            <motion.button
              whileHover={{ scale: loading ? 1 : 1.015 }}
              whileTap={{ scale: loading ? 1 : 0.980 }}
              type="submit"
              className="sv-btn-primary w-full mt-2"
              disabled={loading}
            >
              {loading ? 'Creating account\u2026' : (<>Create Account <ArrowRight className="w-3.5 h-3.5" /></>)}
            </motion.button>
          </form>

          <p className="text-center text-sm mt-10" style={{ color: 'var(--sv-text-muted)' }}>
            Already registered?{' '}
            <Link to="/"
                  className="font-semibold"
                  style={{ color: 'var(--sv-cyan)', textDecoration: 'none' }}
                  onMouseEnter={e => e.target.style.color = '#20b3f5'}
                  onMouseLeave={e => e.target.style.color = 'var(--sv-cyan)'}>
              Sign In
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default Register;
