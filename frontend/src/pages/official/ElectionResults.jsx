import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Gem, LogOut, Loader2, CheckCircle2, XCircle, TrendingUp, Users,
         ChevronLeft, Link2 } from 'lucide-react';
import { fetchElections, fetchElectionResults, verifyChain } from '../../api/apiClient';

const ElectionResults = () => {
  const [elections,        setElections]        = useState([]);
  const [selectedElection, setSelectedElection] = useState('');
  const [results,          setResults]          = useState(null);
  const [verification,     setVerification]     = useState(null);
  const [loading,          setLoading]          = useState(true);
  const [verifying,        setVerifying]        = useState(false);
  const [error,            setError]            = useState('');
  const navigate     = useNavigate();
  const [searchParams] = useSearchParams();
  const userRole     = localStorage.getItem('role');

  useEffect(() => { loadElections(); }, []);

  useEffect(() => {
    const electionParam = searchParams.get('election');
    if (electionParam && elections.length > 0) setSelectedElection(electionParam);
  }, [searchParams, elections]);

  useEffect(() => {
    if (selectedElection) loadResults();
    else setResults(null);
  }, [selectedElection]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadElections = async () => {
    try {
      const data     = await fetchElections();
      const filtered = (data.elections || []).filter(e => e.status === 'active' || e.status === 'closed');
      setElections(filtered);
    } catch {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchElectionResults(selectedElection);
      setResults(data);
    } catch {
      setError('Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError('');
    try {
      const result = await verifyChain(selectedElection);
      setVerification(result);
    } catch {
      setError('Verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const getMaxVotes = () => {
    if (!results?.results) return 0;
    return Math.max(...results.results.map(r => r.votes), 1);
  };

  const barAccents = ['var(--sv-cyan)', 'var(--sv-lime)', '#004B87', 'var(--sv-magenta)'];

  return (
    <div className="sv-bg min-h-screen">

      {/* Nav */}
      <nav className="sv-nav px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gem className="w-4 h-4 text-tud-cyan" />
            <Link to="/official" style={{ textDecoration: 'none' }}
                  className="font-display font-bold text-white text-sm tracking-wide">
              SecureVote SU
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/official" className="sv-btn-outline" style={{ textDecoration: 'none' }}>
              <ChevronLeft className="w-3 h-3" /> Dashboard
            </Link>
            {userRole === 'admin' && (
              <Link to="/admin" className="sv-btn-outline" style={{ textDecoration: 'none' }}>Admin</Link>
            )}
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                           onClick={handleLogout} className="sv-btn-ghost text-xs">
              <LogOut className="w-3.5 h-3.5" />
            </motion.button>
          </div>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-12">

        {/* Page header */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="font-mono text-[10px] tracking-[0.16em] mb-2" style={{ color: 'var(--sv-text-muted)' }}>
            OFFICIAL VIEW
          </p>
          <h1 className="font-display font-black text-white"
              style={{ fontSize: 'clamp(1.5rem, 3.5vw, 2.2rem)', letterSpacing: '-0.02em' }}>
            Election Results
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--sv-text-dim)' }}>
            Detailed results and blockchain verification
          </p>
        </motion.div>

        {error && <div className="sv-alert-error mb-5">{error}</div>}

        {/* Selector + Verify */}
        <div className="sv-card p-5 mb-6">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1">
              <label className="sv-label">Select Election</label>
              <select className="sv-input-box" value={selectedElection}
                      onChange={(e) => setSelectedElection(e.target.value)}>
                <option value="">Choose an election&hellip;</option>
                {elections.map((e) => (
                  <option key={e.election_id} value={e.election_id}>{e.title} ({e.status})</option>
                ))}
              </select>
            </div>
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={handleVerify}
              disabled={!selectedElection || verifying}
              className="sv-btn-primary shrink-0"
            >
              {verifying
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Verifying&hellip;</>
                : <><Link2 className="w-3.5 h-3.5" /> Verify Blockchain</>
              }
            </motion.button>
          </div>
        </div>

        {/* States */}
        {loading && selectedElection ? (
          <div className="text-center py-20">
            <Loader2 className="w-7 h-7 animate-spin mx-auto text-tud-cyan" />
          </div>

        ) : !selectedElection ? (
          <div className="sv-card p-12 text-center">
            <p className="text-sm" style={{ color: 'var(--sv-text-muted)' }}>
              Select an election above to view results
            </p>
          </div>

        ) : results ? (
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              {/* Chart */}
              <div className="lg:col-span-2 sv-card p-8">
                <h2 className="font-display font-bold text-white mb-8" style={{ fontSize: 18 }}>
                  Vote Distribution
                </h2>
                {results.results && results.results.length > 0 ? (
                  <div className="space-y-7">
                    {results.results.map((candidate, i) => {
                      const pct  = results.total_votes > 0
                        ? ((candidate.votes / results.total_votes) * 100).toFixed(1) : 0;
                      const barW = getMaxVotes() > 0
                        ? (candidate.votes / getMaxVotes()) * 100 : 0;
                      const accent = barAccents[i % barAccents.length];
                      return (
                        <div key={candidate.candidate_id ?? candidate.id ?? i}>
                          <div className="flex items-end justify-between mb-2.5">
                            <span className="font-display font-semibold text-sm text-white">
                              {candidate.name}
                            </span>
                            <div className="flex items-baseline gap-3">
                              <span className="font-mono text-sm" style={{ color: 'var(--sv-text-dim)' }}>
                                {candidate.votes} votes
                              </span>
                              {results.total_votes > 0 && (
                                <span className="font-mono font-black" style={{ fontSize: 22, color: accent, lineHeight: 1 }}>
                                  {pct}%
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="h-1.5 rounded-sm overflow-hidden"
                               style={{ background: 'rgba(228,235,248,0.06)' }}>
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${barW}%` }}
                              transition={{ duration: 0.8, delay: i * 0.12 }}
                              style={{ height: '100%', background: accent, borderRadius: 1 }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-center text-sm py-10" style={{ color: 'var(--sv-text-muted)' }}>
                    No votes cast yet
                  </p>
                )}
              </div>

              {/* Stats */}
              <div className="space-y-4">
                <div className="sv-card p-6 text-center">
                  <div className="w-9 h-9 flex items-center justify-center mx-auto mb-3"
                       style={{ background: 'rgba(0,159,227,0.08)', border: '1px solid rgba(0,159,227,0.14)', borderRadius: 2 }}>
                    <Users className="w-4 h-4 text-tud-cyan" />
                  </div>
                  <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-2"
                     style={{ color: 'var(--sv-text-muted)' }}>Total Votes</p>
                  <p className="font-display font-black text-white animate-flicker"
                     style={{ fontSize: 40, lineHeight: 1 }}>
                    {results.total_votes || 0}
                  </p>
                </div>
                <div className="sv-card p-6 text-center">
                  <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-3"
                     style={{ color: 'var(--sv-text-muted)' }}>Status</p>
                  {results.status === 'active'
                    ? <span className="sv-badge-active" style={{ fontSize: 11, padding: '5px 14px' }}>Live</span>
                    : <span className="sv-badge-closed" style={{ fontSize: 11, padding: '5px 14px' }}>Closed</span>
                  }
                </div>
                {results.results && results.results.length > 0 && (
                  <div className="sv-card p-6 text-center">
                    <div className="w-9 h-9 flex items-center justify-center mx-auto mb-3"
                         style={{ background: 'rgba(132,189,0,0.08)', border: '1px solid rgba(132,189,0,0.14)', borderRadius: 2 }}>
                      <TrendingUp className="w-4 h-4" style={{ color: 'var(--sv-lime)' }} />
                    </div>
                    <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-2"
                       style={{ color: 'var(--sv-text-muted)' }}>Leading</p>
                    <p className="font-display font-bold text-white text-base">
                      {results.results[0]?.name || 'N/A'}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Verification result */}
            {verification && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="sv-card p-6"
                style={{ borderColor: verification.valid ? 'rgba(132,189,0,0.30)' : 'rgba(200,0,90,0.30)' }}
              >
                <div className="flex items-center gap-3 mb-5"
                     style={{ color: verification.valid ? 'var(--sv-lime)' : 'var(--sv-magenta)' }}>
                  {verification.valid
                    ? <CheckCircle2 className="w-4 h-4" />
                    : <XCircle className="w-4 h-4" />
                  }
                  <p className="font-display font-bold text-sm">
                    {verification.valid
                      ? 'All votes verified — blockchain integrity confirmed'
                      : 'Verification failed — potential tampering detected'}
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: 'Blocks Verified', value: verification.total_votes || verification.blocks_verified || 0 },
                    { label: 'Hash Chain',       value: verification.valid ? 'Intact' : 'Broken' },
                    { label: 'Verified At',      value: new Date().toLocaleTimeString() },
                  ].map((s) => (
                    <div key={s.label} className="p-3 text-center"
                         style={{ background: 'rgba(228,235,248,0.03)', border: '1px solid var(--sv-border)', borderRadius: 2 }}>
                      <p className="font-mono text-[10px] tracking-[0.10em]" style={{ color: 'var(--sv-text-muted)' }}>
                        {s.label}
                      </p>
                      <p className="font-display font-bold text-white text-sm mt-1">{s.value}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </motion.div>
        ) : null}
      </div>
    </div>
  );
};

export default ElectionResults;
