import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, CheckCircle2, Gem, ChevronDown, X } from 'lucide-react';
import { register, getPasswordRequirements, fetchProgrammes } from '../api/apiClient';
import DOMPurify from 'dompurify';

const Register = () => {
  // Core form fields
  const [studentId,        setStudentId]        = useState('');
  const [password,         setPassword]         = useState('');
  const [confirmPassword,  setConfirmPassword]  = useState('');
  const [email,            setEmail]            = useState('');
  // Feedback messages for the user
  const [error,            setError]            = useState('');
  const [success,          setSuccess]          = useState('');
  // True while the registration API call is in flight
  const [loading,          setLoading]          = useState(false);
  // Password rules fetched from the backend (min length, complexity, etc.)
  const [requirements,     setRequirements]     = useState(null);

  // Programme picker state
  const [programmes,       setProgrammes]       = useState([]);
  // True while the programmes list is being fetched
  const [progLoading,      setProgLoading]      = useState(true);
  // True if the fetch failed so we can offer a retry button
  const [progError,        setProgError]        = useState(false);
  // The currently selected programme object: {code, name, faculty}
  const [selectedProg,     setSelectedProg]     = useState(null);   // {code, name, faculty}
  // Text typed into the dropdown search box
  const [progSearch,       setProgSearch]       = useState('');
  // Whether the dropdown list is currently open
  const [progOpen,         setProgOpen]         = useState(false);

  // Ref attached to the dropdown wrapper so we can detect outside clicks
  const dropdownRef = useRef(null);
  const navigate    = useNavigate();

  // Fetch the full list of TU Dublin programmes from the backend
  const loadProgrammes = () => {
    setProgLoading(true);
    setProgError(false);
    fetchProgrammes()
      .then(d => { setProgrammes(d.programmes || []); setProgLoading(false); })
      .catch(() => { setProgError(true); setProgLoading(false); });
  };

  // On mount, load password requirements and the programmes list in parallel
  useEffect(() => {
    getPasswordRequirements().then(setRequirements).catch(() => {});
    loadProgrammes();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setProgOpen(false);
      }
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, []);

  // Filter the full list by whatever the user has typed — matches code, name, or faculty
  const filteredProgrammes = programmes.filter(p => {
    const q = progSearch.toLowerCase();
    return p.code.toLowerCase().includes(q) || p.name.toLowerCase().includes(q) || p.faculty.toLowerCase().includes(q);
  });

  // Group filtered results by faculty for display
  const grouped = filteredProgrammes.reduce((acc, p) => {
    if (!acc[p.faculty]) acc[p.faculty] = [];
    acc[p.faculty].push(p);
    return acc;
  }, {});

  // Store the chosen programme and close the dropdown
  const handleSelectProg = (prog) => {
    setSelectedProg(prog);
    setProgSearch('');
    setProgOpen(false);
  };

  // Clear the programme selection when the user clicks the X button
  const handleClearProg = (e) => {
    e.stopPropagation();
    setSelectedProg(null);
    setProgSearch('');
  };

  // Validate and submit the registration form to the backend
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // Client-side guard: passwords must match and a programme must be selected
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    if (!selectedProg) { setError('Please select your programme'); return; }

    setLoading(true);
    try {
      // Sanitise user-supplied text before sending to the backend (XSS prevention)
      const cleanStudentId = DOMPurify.sanitize(studentId.trim());
      const cleanEmail     = email ? DOMPurify.sanitize(email.trim()) : undefined;
      await register(cleanStudentId, password, cleanEmail, { code: selectedProg.code, name: selectedProg.name });
      setSuccess('Registration successful! Redirecting to login\u2026');
      // Brief delay so the user can read the success message before being redirected
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

      {/* Left panel — branding column shown only on large screens */}
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
        {/* Fade-and-slide in animation on mount */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.40, ease: 'easeOut' }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo — only visible when the left panel is hidden */}
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

          {/* Error and success banners — animate in when they appear */}
          {error && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                        className="sv-alert-error mb-8">
              {error}
            </motion.div>
          )}
          {success && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                        className="sv-alert-success mb-8">
              <CheckCircle2 className="w-4 h-4 shrink-0" /> {success}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-7">

            {/* Student ID */}
            <div>
              <label className="sv-label">Student ID <span style={{ color: 'var(--sv-magenta)' }}>*</span></label>
              {/* Force uppercase so IDs are stored consistently */}
              <input type="text" className="sv-input" value={studentId}
                onChange={(e) => setStudentId(e.target.value.toUpperCase())}
                required placeholder="e.g. C22512345" disabled={loading} />
            </div>

            {/* Programme picker — custom searchable dropdown grouped by faculty */}
            <div ref={dropdownRef}>
              <label className="sv-label">Programme <span style={{ color: 'var(--sv-magenta)' }}>*</span></label>

              {/* Trigger — clicking this box opens or closes the dropdown */}
              <div
                onClick={() => !loading && setProgOpen(o => !o)}
                className="sv-input-box flex items-center justify-between cursor-pointer select-none"
                style={{ padding: '10px 12px', minHeight: 42 }}
              >
                {selectedProg ? (
                  <span className="text-sm text-white truncate pr-2">
                    <span className="font-mono text-[11px] mr-2" style={{ color: 'var(--sv-cyan)' }}>
                      {selectedProg.code}
                    </span>
                    {selectedProg.name}
                  </span>
                ) : (
                  <span className="text-sm" style={{ color: 'var(--sv-text-muted)' }}>Search your programme…</span>
                )}
                <div className="flex items-center gap-1 shrink-0">
                  {/* X button clears the current selection without reopening the dropdown */}
                  {selectedProg && (
                    <button type="button" onClick={handleClearProg}
                            className="p-0.5 rounded-sm transition-colors hover:text-white"
                            style={{ color: 'var(--sv-text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}>
                      <X className="w-3 h-3" />
                    </button>
                  )}
                  {/* Chevron rotates 180° when the dropdown is open */}
                  <ChevronDown className="w-3.5 h-3.5" style={{ color: 'var(--sv-text-muted)',
                    transform: progOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
                </div>
              </div>

              {/* Dropdown — animated in/out with Framer Motion */}
              <AnimatePresence>
                {progOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.12 }}
                    className="absolute z-50 w-full max-w-sm"
                    style={{
                      background: 'var(--sv-raised)',
                      border: '1px solid rgba(0,159,227,0.18)',
                      borderRadius: 2,
                      boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
                      marginTop: 4,
                    }}
                  >
                    {/* Search input — autofocused so users can type immediately */}
                    <div style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0,159,227,0.10)' }}>
                      <input
                        autoFocus
                        type="text"
                        value={progSearch}
                        onChange={(e) => setProgSearch(e.target.value)}
                        placeholder="Type code or course name…"
                        className="w-full bg-transparent outline-none text-sm text-white placeholder-gray-500"
                        style={{ border: 'none' }}
                      />
                    </div>

                    {/* Results — shows loading spinner, error/retry, empty state, or grouped list */}
                    <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                      {progLoading ? (
                        <p className="text-xs text-center py-6" style={{ color: 'var(--sv-text-muted)' }}>
                          Loading programmes…
                        </p>
                      ) : progError ? (
                        <div className="text-center py-6">
                          <p className="text-xs mb-2" style={{ color: 'var(--sv-text-muted)' }}>Failed to load programmes</p>
                          <button type="button" onClick={loadProgrammes}
                                  className="text-xs underline" style={{ color: 'var(--sv-cyan)', background: 'none', border: 'none', cursor: 'pointer' }}>
                            Retry
                          </button>
                        </div>
                      ) : Object.keys(grouped).length === 0 ? (
                        <p className="text-xs text-center py-6" style={{ color: 'var(--sv-text-muted)' }}>
                          No programmes match
                        </p>
                      ) : (
                        // Render each faculty as a group header, then list its programmes below
                        Object.entries(grouped).map(([faculty, progs]) => (
                          <div key={faculty}>
                            <p className="font-mono text-[9px] tracking-[0.14em] uppercase px-3 pt-3 pb-1"
                               style={{ color: 'var(--sv-text-muted)' }}>
                              {faculty}
                            </p>
                            {progs.map(p => (
                              <div
                                key={p.code}
                                onClick={() => handleSelectProg(p)}
                                className="flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors"
                                style={{
                                  // Highlight the row if this programme is already selected
                                  background: selectedProg?.code === p.code ? 'rgba(0,159,227,0.08)' : 'transparent',
                                }}
                                onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,159,227,0.06)'}
                                onMouseLeave={e => e.currentTarget.style.background =
                                  selectedProg?.code === p.code ? 'rgba(0,159,227,0.08)' : 'transparent'}
                              >
                                <span className="font-mono text-[11px] shrink-0" style={{ color: 'var(--sv-cyan)', width: 52 }}>
                                  {p.code}
                                </span>
                                <span className="text-sm text-white leading-snug">{p.name}</span>
                              </div>
                            ))}
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Email — optional, used for future notifications */}
            <div>
              <label className="sv-label">
                Email <span className="normal-case font-normal" style={{ color: 'var(--sv-text-muted)', letterSpacing: 0 }}>(optional)</span>
              </label>
              <input type="email" className="sv-input" value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@tudublin.ie" disabled={loading} />
            </div>

            {/* Password */}
            <div>
              <label className="sv-label">Password <span style={{ color: 'var(--sv-magenta)' }}>*</span></label>
              <input type="password" className="sv-input" value={password}
                onChange={(e) => setPassword(e.target.value)}
                required placeholder="Create a strong password"
                disabled={loading} autoComplete="new-password" />
              {/* Show the minimum requirements hint once they've been loaded from the server */}
              {requirements && (
                <p className="font-mono text-[10px] mt-2" style={{ color: 'var(--sv-text-muted)' }}>
                  Min {requirements.min_length} chars &middot; uppercase &middot; lowercase &middot; number
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="sv-label">Confirm Password <span style={{ color: 'var(--sv-magenta)' }}>*</span></label>
              <input type="password" className="sv-input" value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required placeholder="Repeat your password"
                disabled={loading} autoComplete="new-password" />
            </div>

            {/* Submit button — animates on hover/tap; disabled while submitting */}
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

          {/* Link back to the login page */}
          <p className="text-center text-sm mt-10" style={{ color: 'var(--sv-text-muted)' }}>
            Already registered?{' '}
            <Link to="/" className="font-semibold"
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
