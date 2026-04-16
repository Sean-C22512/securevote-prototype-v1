import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Gem, LogOut, BarChart3, Loader2, TrendingUp, Users } from 'lucide-react';
import { fetchElections, fetchElectionResults } from '../api/apiClient';

const Results = () => {
  const [elections,        setElections]        = useState([]);
  const [selectedElection, setSelectedElection] = useState('');
  const [results,          setResults]          = useState(null);
  const [loading,          setLoading]          = useState(true);
  const [error,            setError]            = useState('');
  const navigate = useNavigate();

  useEffect(() => { loadElections(); }, []);

  useEffect(() => {
    if (selectedElection) loadResults();
  }, [selectedElection]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadElections = async () => {
    try {
      const data    = await fetchElections();
      const role = localStorage.getItem('role');
      const visible = (data.elections || []).filter(e =>
        e.status === 'closed' || (e.status === 'active' && role !== 'student')
      );
      setElections(visible);
      if (visible.length === 1) setSelectedElection(visible[0].election_id);
    } catch {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    setLoading(true);
    try {
      const data = await fetchElectionResults(selectedElection);
      setResults(data);
    } catch {
      setError('Failed to load results');
    } finally {
      setLoading(false);
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
            <Link to="/cast-vote"
                  className="font-mono text-[11px] tracking-[0.10em] uppercase transition-colors"
                  style={{ color: 'var(--sv-text-muted)', textDecoration: 'none' }}>
              Vote
            </Link>
            <span className="font-mono text-[11px] tracking-[0.10em] uppercase" style={{ color: 'var(--sv-cyan)' }}>
              Results
            </span>
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
          <p className="font-mono text-[10px] tracking-[0.16em] mb-3" style={{ color: 'var(--sv-text-muted)' }}>
            ELECTION RESULTS
          </p>
          <h1 className="font-display font-black text-white" style={{ fontSize: 'clamp(1.8rem, 4vw, 2.8rem)', letterSpacing: '-0.02em' }}>
            Results
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--sv-text-dim)' }}>
            View results for completed elections
          </p>
        </motion.div>

        {error && <div className="sv-alert-error mb-6">{error}</div>}

        {/* Election selector */}
        {elections.length > 1 && (
          <div className="sv-card p-5 mb-8">
            <label className="sv-label">Select Election</label>
            <select
              className="sv-input-box"
              value={selectedElection}
              onChange={(e) => setSelectedElection(e.target.value)}
            >
              <option value="">Choose an election&hellip;</option>
              {elections.map((e) => (
                <option key={e.election_id} value={e.election_id}>
                  {e.title} ({e.status})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* States */}
        {loading ? (
          <div className="text-center py-24">
            <Loader2 className="w-7 h-7 animate-spin mx-auto mb-4 text-tud-cyan" />
            <p className="font-mono text-xs tracking-[0.12em]" style={{ color: 'var(--sv-text-muted)' }}>
              LOADING&hellip;
            </p>
          </div>

        ) : elections.length === 0 ? (
          <div className="text-center py-20">
            <BarChart3 className="w-8 h-8 mx-auto mb-4" style={{ color: 'var(--sv-text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--sv-text-muted)' }}>No elections with results available</p>
          </div>

        ) : !selectedElection ? (
          <div className="sv-card p-12 text-center">
            <p className="text-sm" style={{ color: 'var(--sv-text-muted)' }}>Select an election above to view results</p>
          </div>

        ) : results ? (
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 lg:grid-cols-3 gap-5"
          >
            {/* Chart panel */}
            <div className="lg:col-span-2 sv-card p-8">
              <h2 className="font-display font-bold text-white mb-8" style={{ fontSize: 18 }}>
                {results.title || 'Vote Distribution'}
              </h2>

              {results.results && results.results.length > 0 ? (
                <div className="space-y-7">
                  {results.results.map((candidate, i) => {
                    const pct  = results.total_votes > 0
                      ? ((candidate.votes / results.total_votes) * 100).toFixed(1)
                      : 0;
                    const barW = getMaxVotes() > 0
                      ? (candidate.votes / getMaxVotes()) * 100
                      : 0;
                    const accent = barAccents[i % barAccents.length];
                    return (
                      <div key={candidate.candidate_id ?? candidate.id ?? i}>
                        <div className="flex items-end justify-between mb-2.5">
                          <span className="font-display font-semibold text-sm text-white">
                            {candidate.name}
                          </span>
                          <div className="flex items-baseline gap-3">
                            <span className="font-mono font-semibold text-sm" style={{ color: accent }}>
                              {candidate.votes}
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
                            transition={{ duration: 0.8, delay: i * 0.12, ease: 'easeOut' }}
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

            {/* Stats column */}
            <div className="space-y-4">
              <div className="sv-card p-6 text-center">
                <div className="w-9 h-9 flex items-center justify-center mx-auto mb-3"
                     style={{ background: 'rgba(0,159,227,0.08)', border: '1px solid rgba(0,159,227,0.14)', borderRadius: 2 }}>
                  <Users className="w-4 h-4 text-tud-cyan" />
                </div>
                <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-2"
                   style={{ color: 'var(--sv-text-muted)' }}>
                  Total Votes
                </p>
                <p className="font-display font-black text-white animate-flicker"
                   style={{ fontSize: 40, lineHeight: 1 }}>
                  {results.total_votes || 0}
                </p>
              </div>

              <div className="sv-card p-6 text-center">
                <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-3"
                   style={{ color: 'var(--sv-text-muted)' }}>
                  Status
                </p>
                {results.status === 'active'
                  ? <span className="sv-badge-active text-sm px-4 py-1.5">Live</span>
                  : <span className="sv-badge-closed text-sm px-4 py-1.5">Closed</span>
                }
              </div>

              {results.results && results.results.length > 0 && results.total_votes > 0 && (
                <div className="sv-card p-6 text-center">
                  <div className="w-9 h-9 flex items-center justify-center mx-auto mb-3"
                       style={{ background: 'rgba(132,189,0,0.08)', border: '1px solid rgba(132,189,0,0.14)', borderRadius: 2 }}>
                    <TrendingUp className="w-4 h-4" style={{ color: 'var(--sv-lime)' }} />
                  </div>
                  <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-2"
                     style={{ color: 'var(--sv-text-muted)' }}>
                    Leading
                  </p>
                  <p className="font-display font-bold text-white text-base">
                    {results.results[0]?.name}
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        ) : null}
      </div>
    </div>
  );
};

export default Results;
