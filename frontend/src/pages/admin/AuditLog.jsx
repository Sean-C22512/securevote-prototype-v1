import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Gem, Activity, Users, ClipboardList, Settings, LogOut,
         CheckCircle2, Loader2, Terminal } from 'lucide-react';
import { verifyChain, fetchAuditStats, fetchElections } from '../../api/apiClient';

const AdminSidebar = ({ active, onLogout }) => {
  const links = [
    { icon: <Activity      className="w-3.5 h-3.5" />, label: 'Dashboard',       href: '/admin' },
    { icon: <Users         className="w-3.5 h-3.5" />, label: 'User Management', href: '/admin/users' },
    { icon: <ClipboardList className="w-3.5 h-3.5" />, label: 'Audit Log',       href: '/admin/audit' },
    { icon: <Settings      className="w-3.5 h-3.5" />, label: 'Elections',        href: '/official' },
  ];
  return (
    <aside className="sv-sidebar">
      <div className="px-4 mb-10">
        <div className="flex items-center gap-2 mb-1">
          <Gem className="w-4 h-4 text-tud-cyan" />
          <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote</span>
        </div>
        <p className="font-mono text-[9px] tracking-[0.20em] ml-6" style={{ color: 'var(--sv-magenta)' }}>
          ADMIN CONSOLE
        </p>
      </div>
      <nav className="flex-1 px-2 space-y-0.5">
        {links.map((l) => {
          const isActive = l.href === active;
          return (
            <Link key={l.href} to={l.href}
              style={{
                textDecoration: 'none',
                borderLeft: `2px solid ${isActive ? 'var(--sv-cyan)' : 'transparent'}`,
                color: isActive ? 'white' : 'rgba(228,235,248,0.32)',
              }}
              className="flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-colors"
            >
              <span style={{ color: isActive ? 'var(--sv-cyan)' : 'inherit' }}>{l.icon}</span>
              <span>{l.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="px-2 mt-auto">
        <button onClick={onLogout}
          className="flex items-center gap-3 px-3 py-2.5 text-sm w-full text-left"
          style={{ color: 'rgba(228,235,248,0.22)', background: 'none', border: 'none', cursor: 'pointer' }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--sv-magenta)'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(228,235,248,0.22)'}>
          <LogOut className="w-3.5 h-3.5" /><span>Logout</span>
        </button>
      </div>
    </aside>
  );
};

const AuditLog = () => {
  const [stats,              setStats]              = useState(null);
  const [elections,          setElections]          = useState([]);
  const [selectedElection,   setSelectedElection]   = useState('');
  const [verificationResult, setVerificationResult] = useState(null);
  const [loading,            setLoading]            = useState(true);
  const [verifying,          setVerifying]          = useState(false);
  const [error,              setError]              = useState('');
  const navigate = useNavigate();

  useEffect(() => { loadData(); }, []);

  useEffect(() => {
    if (selectedElection !== undefined) loadStats();
  }, [selectedElection]);

  const loadData = async () => {
    try {
      const [electionsData, statsData] = await Promise.all([fetchElections(), fetchAuditStats()]);
      setElections(electionsData.elections || []);
      setStats(statsData);
    } catch {
      setError('Failed to load audit data');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const statsData = await fetchAuditStats(selectedElection || null);
      setStats(statsData);
    } catch {
      console.error('Failed to load stats');
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError('');
    setVerificationResult(null);
    try {
      const result = await verifyChain(selectedElection || null);
      setVerificationResult(result);
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

  const statItems = stats ? [
    { label: 'Total Votes',   value: stats.total_votes  || 0,  color: 'var(--sv-cyan)' },
    { label: 'Chain Length',  value: stats.chain_length || 0,  color: 'var(--sv-lime)' },
    { label: 'Chain Status',  value: stats.chain_valid !== false ? 'Valid' : 'Invalid',
      color: stats.chain_valid !== false ? 'var(--sv-lime)' : 'var(--sv-magenta)' },
    { label: 'Unique Voters', value: stats.unique_voters || 0, color: 'var(--sv-cyan)' },
  ] : [];

  return (
    <div className="min-h-screen flex sv-bg-admin">
      <AdminSidebar active="/admin/audit" onLogout={handleLogout} />

      <main className="flex-1 p-8 overflow-auto">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="font-mono text-[10px] tracking-[0.16em] mb-2"
             style={{ color: 'rgba(228,235,248,0.25)' }}>
            BLOCKCHAIN AUDIT
          </p>
          <h1 className="font-display font-black text-white"
              style={{ fontSize: 28, letterSpacing: '-0.02em' }}>
            Audit Log
          </h1>
          <p className="text-sm mt-1" style={{ color: 'rgba(228,235,248,0.40)' }}>
            Blockchain verification &amp; system audit
          </p>
        </motion.div>

        {error && <div className="sv-alert-error mb-5">{error}</div>}

        {/* Filter + verify */}
        <div className="sv-card-admin p-5 mb-6">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1">
              <label className="sv-label">Filter by Election</label>
              <select
                className="sv-input-box"
                value={selectedElection}
                onChange={(e) => setSelectedElection(e.target.value)}
              >
                <option value="">All Elections</option>
                {elections.map((e) => (
                  <option key={e.election_id} value={e.election_id}>
                    {e.title} ({e.status})
                  </option>
                ))}
              </select>
            </div>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleVerify}
              disabled={verifying}
              className="sv-btn-primary shrink-0"
            >
              {verifying
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Verifying&hellip;</>
                : <><CheckCircle2 className="w-3.5 h-3.5" /> Verify Blockchain</>
              }
            </motion.button>
          </div>
        </div>

        {/* Stats */}
        {loading ? (
          <div className="flex items-center gap-2 py-10"
               style={{ color: 'rgba(228,235,248,0.30)' }}>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="font-mono text-xs tracking-[0.10em]">LOADING&hellip;</span>
          </div>
        ) : stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            {statItems.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="sv-card-admin p-4 text-center"
              >
                <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-2"
                   style={{ color: 'rgba(228,235,248,0.28)' }}>
                  {s.label}
                </p>
                <p className="font-display font-black animate-flicker"
                   style={{ fontSize: 32, lineHeight: 1, color: s.color }}>
                  {s.value}
                </p>
              </motion.div>
            ))}
          </div>
        )}

        {/* Terminal verification output */}
        {verificationResult && (
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="sv-terminal"
          >
            {/* Terminal chrome */}
            <div className="flex items-center gap-2 px-5 py-3"
                 style={{ borderBottom: '1px solid rgba(0,159,227,0.12)', background: 'rgba(0,159,227,0.03)' }}>
              <Terminal className="w-3.5 h-3.5" style={{ color: 'var(--sv-cyan)' }} />
              <span className="font-mono text-[10px] tracking-[0.16em] uppercase"
                    style={{ color: 'var(--sv-cyan)' }}>
                BLOCKCHAIN_VERIFICATION_RESULT
              </span>
              <div className="ml-auto flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(200,0,90,0.5)' }} />
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(251,191,36,0.5)' }} />
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(132,189,0,0.5)' }} />
              </div>
            </div>

            {/* Terminal content */}
            <div className="p-6 space-y-2 font-mono text-sm">
              <p style={{ color: verificationResult.valid ? 'var(--sv-lime)' : 'var(--sv-magenta)' }}>
                {verificationResult.valid ? '✓' : '✗'}{' '}
                STATUS: {verificationResult.valid ? 'INTEGRITY_VERIFIED' : 'INTEGRITY_FAILED'}
              </p>
              <p style={{ color: 'rgba(228,235,248,0.45)' }}>
                {'> '} BLOCKS_VERIFIED: {verificationResult.total_votes || 0}
              </p>
              <p style={{ color: 'rgba(228,235,248,0.45)' }}>
                {'> '} HASH_CHAIN:{' '}
                <span style={{ color: verificationResult.valid ? 'var(--sv-lime)' : 'var(--sv-magenta)' }}>
                  {verificationResult.valid ? 'INTACT' : 'BROKEN'}
                </span>
              </p>
              <p style={{ color: 'rgba(228,235,248,0.45)' }}>
                {'> '} VERIFIED_AT: {new Date().toISOString()}
              </p>
              {verificationResult.errors && verificationResult.errors.length > 0 && (
                <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(0,159,227,0.08)' }}>
                  {verificationResult.errors.map((err, i) => (
                    <p key={i} style={{ color: 'var(--sv-magenta)' }}>! {err}</p>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
};

export default AuditLog;
