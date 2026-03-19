import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Gem, LogOut, CheckCircle2, AlertCircle, ChevronLeft, Vote, Loader2, Check } from 'lucide-react';
import { fetchElections, castVote } from '../api/apiClient';

const StudentNav = ({ handleLogout, activePage }) => (
  <nav className="sv-nav px-6 py-4">
    <div className="max-w-3xl mx-auto flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Gem className="w-4 h-4 text-tud-cyan" />
        <Link to="/dashboard" style={{ textDecoration: 'none' }}
              className="font-display font-bold text-white text-sm tracking-wide">
          SecureVote
        </Link>
      </div>
      <div className="flex items-center gap-5">
        <Link to="/dashboard"
              className="font-mono text-[11px] tracking-[0.10em] uppercase transition-colors"
              style={{ color: 'var(--sv-text-muted)', textDecoration: 'none' }}>
          Home
        </Link>
        <span className="font-mono text-[11px] tracking-[0.10em] uppercase" style={{ color: 'var(--sv-cyan)' }}>
          Vote
        </span>
        <Link to="/results"
              className="font-mono text-[11px] tracking-[0.10em] uppercase transition-colors"
              style={{ color: 'var(--sv-text-muted)', textDecoration: 'none' }}>
          Results
        </Link>
        <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                       onClick={handleLogout} className="sv-btn-ghost text-xs">
          <LogOut className="w-3.5 h-3.5" />
        </motion.button>
      </div>
    </div>
  </nav>
);

const CastVote = () => {
  const [elections,          setElections]          = useState([]);
  const [selectedElection,   setSelectedElection]   = useState(null);
  const [selectedCandidate,  setSelectedCandidate]  = useState(null);
  const [error,              setError]              = useState('');
  const [success,            setSuccess]            = useState(false);
  const [loading,            setLoading]            = useState(true);
  const [submitting,         setSubmitting]         = useState(false);
  const navigate = useNavigate();

  useEffect(() => { loadElections(); }, []);

  const loadElections = async () => {
    try {
      const data   = await fetchElections('active');
      const active = (data.elections || []).filter(e => e.status === 'active');
      setElections(active);
      if (active.length === 1) setSelectedElection(active[0]);
    } catch {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedCandidate || !selectedElection) { setError('Please select a candidate'); return; }
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
    <div className="sv-bg min-h-screen">
      <StudentNav handleLogout={handleLogout} />

      <div className="max-w-3xl mx-auto px-6 py-12">
        <AnimatePresence mode="wait">

          {/* ── Vote confirmed ── */}
          {success ? (
            <motion.div key="success"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center py-20"
            >
              {/* Diamond checkmark */}
              <div className="flex justify-center mb-8">
                <div className="w-20 h-20 flex items-center justify-center"
                     style={{ background: 'rgba(132,189,0,0.10)', border: '1px solid rgba(132,189,0,0.25)', borderRadius: 3 }}>
                  <Check className="w-10 h-10" style={{ color: 'var(--sv-lime)' }} strokeWidth={2.5} />
                </div>
              </div>
              <h2 className="font-display font-black text-white mb-2"
                  style={{ fontSize: 'clamp(2rem, 5vw, 3rem)', letterSpacing: '-0.02em' }}>
                VOTE RECORDED.
              </h2>
              <p className="text-sm mb-2" style={{ color: 'var(--sv-text-dim)' }}>
                Thank you for participating in the election.
              </p>
              <p className="font-mono text-[10px] tracking-[0.14em] mb-10"
                 style={{ color: 'rgba(132,189,0,0.55)' }}>
                ENCRYPTED &middot; SEALED ON BLOCKCHAIN
              </p>
              <Link to="/results" className="sv-btn-primary" style={{ textDecoration: 'none' }}>
                View Results <ChevronLeft className="w-3.5 h-3.5 rotate-180" />
              </Link>
            </motion.div>

          /* ── Loading ── */
          ) : loading ? (
            <motion.div key="loading" className="text-center py-24">
              <Loader2 className="w-7 h-7 animate-spin mx-auto mb-4 text-tud-cyan" />
              <p className="font-mono text-xs tracking-[0.12em]" style={{ color: 'var(--sv-text-muted)' }}>
                LOADING ELECTIONS&hellip;
              </p>
            </motion.div>

          /* ── No elections ── */
          ) : elections.length === 0 ? (
            <motion.div key="empty"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-20"
            >
              <div className="w-14 h-14 flex items-center justify-center mx-auto mb-6"
                   style={{ border: '1px solid var(--sv-border)', borderRadius: 2 }}>
                <AlertCircle className="w-6 h-6" style={{ color: 'var(--sv-text-muted)' }} />
              </div>
              <h2 className="font-display font-bold text-white text-xl mb-2">No Active Elections</h2>
              <p className="text-sm mb-8" style={{ color: 'var(--sv-text-dim)' }}>
                There are no elections currently open for voting.
              </p>
              <Link to="/dashboard" className="sv-btn-outline" style={{ textDecoration: 'none' }}>
                <ChevronLeft className="w-3.5 h-3.5" /> Back to Dashboard
              </Link>
            </motion.div>

          /* ── Election picker ── */
          ) : !selectedElection ? (
            <motion.div key="select"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <p className="font-mono text-[10px] tracking-[0.16em] mb-3" style={{ color: 'var(--sv-text-muted)' }}>
                ACTIVE ELECTIONS
              </p>
              <h2 className="font-display font-bold text-white text-2xl mb-8"
                  style={{ letterSpacing: '-0.02em' }}>
                Select an Election
              </h2>

              {error && (
                <div className="sv-alert-error mb-6">{error}</div>
              )}

              <div className="space-y-3">
                {elections.map((election) => (
                  <motion.button
                    key={election.election_id}
                    whileHover={{ x: 2 }}
                    onClick={() => setSelectedElection(election)}
                    className="sv-vote-card w-full flex items-center justify-between"
                  >
                    <div>
                      <p className="font-display font-semibold text-white text-sm mb-0.5">
                        {election.title}
                      </p>
                      {election.description && (
                        <p className="text-xs" style={{ color: 'var(--sv-text-dim)' }}>
                          {election.description}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-6">
                      <span className="sv-badge-active">{election.candidates?.length || 0} candidates</span>
                      <ChevronLeft className="w-4 h-4 rotate-180" style={{ color: 'var(--sv-text-muted)' }} />
                    </div>
                  </motion.button>
                ))}
              </div>
            </motion.div>

          /* ── Candidate picker ── */
          ) : (
            <motion.div key="vote"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <button
                onClick={handleBack}
                className="sv-btn-ghost mb-8 pl-0 text-xs"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> All Elections
              </button>

              {/* Election header */}
              <div className="flex items-start gap-3 mb-8">
                <div className="w-9 h-9 flex items-center justify-center shrink-0 mt-0.5"
                     style={{ background: 'rgba(0,159,227,0.08)', border: '1px solid rgba(0,159,227,0.14)', borderRadius: 2 }}>
                  <Vote className="w-4 h-4 text-tud-cyan" />
                </div>
                <div>
                  <p className="font-mono text-[10px] tracking-[0.14em] mb-1" style={{ color: 'var(--sv-text-muted)' }}>
                    BALLOT
                  </p>
                  <h2 className="font-display font-bold text-white text-xl" style={{ letterSpacing: '-0.02em' }}>
                    {selectedElection.title}
                  </h2>
                  <p className="text-sm mt-0.5" style={{ color: 'var(--sv-text-dim)' }}>
                    {selectedElection.description || 'Select one candidate below'}
                  </p>
                </div>
              </div>

              {error && (
                <div className="sv-alert-error mb-6">{error}</div>
              )}

              {/* Divider */}
              <div className="sv-divider mb-6" />

              {/* Candidates */}
              <div className="space-y-3 mb-8">
                {selectedElection.candidates && selectedElection.candidates.length > 0 ? (
                  selectedElection.candidates.map((candidate, idx) => {
                    const isSelected = selectedCandidate === candidate.id;
                    return (
                      <button
                        key={candidate.id ?? idx}
                        type="button"
                        onClick={() => setSelectedCandidate(candidate.id)}
                        className={`sv-vote-card ${isSelected ? 'sv-selected' : ''}`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            {/* Position number */}
                            <span className="font-mono font-semibold shrink-0"
                                  style={{ fontSize: 13, color: isSelected ? 'var(--sv-cyan)' : 'var(--sv-text-muted)' }}>
                              {String(idx + 1).padStart(2, '0')}
                            </span>
                            <div>
                              <p className="font-display font-semibold text-sm"
                                 style={{ color: isSelected ? 'white' : 'var(--sv-text)' }}>
                                {candidate.name}
                              </p>
                              {candidate.description && (
                                <p className="text-xs mt-0.5" style={{ color: 'var(--sv-text-dim)' }}>
                                  {candidate.description}
                                </p>
                              )}
                            </div>
                          </div>
                          {/* Selection indicator */}
                          <div className="shrink-0 ml-4 w-5 h-5 flex items-center justify-center"
                               style={{
                                 border: `1px solid ${isSelected ? 'var(--sv-cyan)' : 'var(--sv-border)'}`,
                                 borderRadius: 2,
                                 background: isSelected ? 'var(--sv-cyan)' : 'transparent',
                               }}>
                            {isSelected && (
                              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                                <Check className="w-3 h-3 text-black" strokeWidth={3} />
                              </motion.div>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <p className="text-center text-sm py-6" style={{ color: 'var(--sv-text-muted)' }}>
                    No candidates available
                  </p>
                )}
              </div>

              <motion.button
                whileHover={{ scale: selectedCandidate && !submitting ? 1.012 : 1 }}
                whileTap={{ scale: selectedCandidate && !submitting ? 0.988 : 1 }}
                onClick={handleSubmit}
                disabled={submitting || selectedCandidate === null}
                className="sv-btn-primary w-full"
                style={{ padding: '16px 28px', fontSize: 12 }}
              >
                {submitting
                  ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Submitting&hellip;</>
                  : 'Submit Vote'}
              </motion.button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default CastVote;
