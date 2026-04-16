import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Gem, Activity, Users, ClipboardList, Settings, LogOut,
  CheckCircle2, Loader2, AlertTriangle, Clock, Hash,
  RefreshCw, Link2, ShieldAlert, List, LayoutGrid,
} from 'lucide-react';
import { fetchAuditBlocks, fetchElections } from '../../api/apiClient';

// ─── Sidebar ─────────────────────────────────────────────────────────────────

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

// ─── Block Card ───────────────────────────────────────────────────────────────

const truncateHash = (hash) => hash ? `${hash.slice(0, 10)}...` : '—';

const fmt = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-IE', { day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false });
};

const BlockCard = ({ block, index: animIdx }) => {
  const verified = block.verified;
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: animIdx * 0.05 }}
      className="sv-card-admin relative flex-shrink-0"
      style={{
        width: 200,
        padding: '16px',
        borderColor: verified ? 'rgba(132,189,0,0.25)' : 'rgba(200,0,90,0.30)',
        borderWidth: 1,
        borderStyle: 'solid',
      }}
    >
      {/* Block number + badge */}
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-[11px] font-bold" style={{ color: 'rgba(228,235,248,0.45)' }}>
          Block #{block.index}
        </span>
        <span
          className="font-mono text-[9px] font-bold px-2 py-0.5 rounded-sm tracking-wider"
          style={{
            background: verified ? 'rgba(132,189,0,0.15)' : 'rgba(200,0,90,0.15)',
            color: verified ? 'var(--sv-lime)' : 'var(--sv-magenta)',
            border: `1px solid ${verified ? 'rgba(132,189,0,0.30)' : 'rgba(200,0,90,0.35)'}`,
          }}
        >
          {verified ? 'verified' : 'tampered'}
        </span>
      </div>

      {/* Fields */}
      <div className="space-y-2">
        <div>
          <p className="font-mono text-[9px] tracking-widest mb-0.5" style={{ color: 'rgba(228,235,248,0.30)' }}>VOTE ID</p>
          <p className="font-mono text-xs font-bold" style={{ color: 'var(--sv-cyan)' }}>{block.vote_id}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] tracking-widest mb-0.5" style={{ color: 'rgba(228,235,248,0.30)' }}>TIMESTAMP</p>
          <p className="font-mono text-[10px]" style={{ color: 'rgba(228,235,248,0.55)' }}>{fmt(block.timestamp)}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] tracking-widest mb-0.5" style={{ color: 'rgba(228,235,248,0.30)' }}>HASH</p>
          <p className="font-mono text-[10px]" style={{ color: verified ? 'var(--sv-lime)' : 'var(--sv-magenta)' }}>
            {truncateHash(block.current_hash)}
          </p>
        </div>
        <div>
          <p className="font-mono text-[9px] tracking-widest mb-0.5" style={{ color: 'rgba(228,235,248,0.30)' }}>PREV</p>
          <p className="font-mono text-[10px]" style={{ color: 'rgba(228,235,248,0.40)' }}>
            {truncateHash(block.previous_hash === 'GENESIS' ? '0000000000000000' : block.previous_hash)}
          </p>
        </div>
      </div>
    </motion.div>
  );
};

// ─── Table Row ────────────────────────────────────────────────────────────────

const TableView = ({ blocks }) => (
  <div className="sv-card-admin overflow-hidden">
    <table className="w-full text-left font-mono text-xs">
      <thead>
        <tr style={{ borderBottom: '1px solid rgba(0,159,227,0.10)' }}>
          {['#', 'Vote ID', 'Timestamp', 'Hash', 'Prev Hash', 'Status'].map(h => (
            <th key={h} className="px-4 py-3 uppercase tracking-wider text-[10px]"
                style={{ color: 'rgba(228,235,248,0.30)', fontWeight: 600 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {blocks.map((b, i) => (
          <motion.tr
            key={b.index}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: i * 0.03 }}
            style={{ borderBottom: '1px solid rgba(0,159,227,0.06)' }}
          >
            <td className="px-4 py-3" style={{ color: 'rgba(228,235,248,0.35)' }}>{b.index}</td>
            <td className="px-4 py-3" style={{ color: 'var(--sv-cyan)' }}>{b.vote_id}</td>
            <td className="px-4 py-3" style={{ color: 'rgba(228,235,248,0.50)' }}>{fmt(b.timestamp)}</td>
            <td className="px-4 py-3" style={{ color: b.verified ? 'var(--sv-lime)' : 'var(--sv-magenta)' }}>
              {truncateHash(b.current_hash)}
            </td>
            <td className="px-4 py-3" style={{ color: 'rgba(228,235,248,0.40)' }}>
              {truncateHash(b.previous_hash === 'GENESIS' ? '0000000000000000' : b.previous_hash)}
            </td>
            <td className="px-4 py-3">
              <span
                className="px-2 py-0.5 rounded-sm text-[9px] tracking-wider font-bold"
                style={{
                  background: b.verified ? 'rgba(132,189,0,0.12)' : 'rgba(200,0,90,0.12)',
                  color: b.verified ? 'var(--sv-lime)' : 'var(--sv-magenta)',
                }}
              >
                {b.verified ? 'VERIFIED' : 'TAMPERED'}
              </span>
            </td>
          </motion.tr>
        ))}
      </tbody>
    </table>
    {blocks.length === 0 && (
      <p className="font-mono text-xs text-center py-10" style={{ color: 'rgba(228,235,248,0.25)' }}>
        No blocks match the current filter.
      </p>
    )}
  </div>
);

// ─── Main Component ───────────────────────────────────────────────────────────

const AuditLog = () => {
  const [elections,        setElections]        = useState([]);
  const [selectedElection, setSelectedElection] = useState('');
  const [statusFilter,     setStatusFilter]     = useState('');
  const [view,             setView]             = useState('blockchain'); // 'blockchain' | 'table'
  const [blockData,        setBlockData]        = useState(null);

  const [loading,          setLoading]          = useState(true);
  const [running,          setRunning]          = useState(false);
  const [error,            setError]            = useState('');
  const navigate = useNavigate();

  // Load elections + auto-select the most recent one
  useEffect(() => {
    const init = async () => {
      try {
        const electionsData = await fetchElections();
        const electionsList = electionsData.elections || [];
        setElections(electionsList);

        // Auto-select the most recent election
        const first = electionsList[electionsList.length - 1];
        const defaultId = first ? first.election_id : '';
        setSelectedElection(defaultId);

        const blocks = await fetchAuditBlocks(defaultId || null);
        setBlockData(blocks);
      } catch {
        setError('Failed to load audit data');
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const runIntegrityCheck = useCallback(async () => {
    setRunning(true);
    setError('');
    try {
      const blocks = await fetchAuditBlocks(selectedElection || null, statusFilter);
      setBlockData(blocks);
    } catch {
      setError('Integrity check failed');
    } finally {
      setRunning(false);
    }
  }, [selectedElection, statusFilter]);

  // Re-fetch when filters change (without full spinner)
  useEffect(() => {
    if (!loading) runIntegrityCheck();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedElection, statusFilter]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const blocks      = blockData?.blocks ?? [];
  const chainValid  = blockData?.chain_valid ?? true;
  const verifiedCt  = blockData?.verified_count ?? 0;
  const tamperedCt  = blockData?.tampered_count ?? 0;
  const lastVerified = blockData?.last_verified;
  const integrityPct = blockData?.total
    ? Math.round((verifiedCt / blockData.total) * 100)
    : 100;

  const fmtLastVerified = lastVerified
    ? new Date(lastVerified).toLocaleString('en-IE', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: false,
      })
    : null;

  const timeSinceScan = lastVerified
    ? (() => {
        const diff = Math.round((Date.now() - new Date(lastVerified)) / 60000);
        return diff < 1 ? 'just now' : `${diff} min ago`;
      })()
    : '—';

  return (
    <div className="min-h-screen flex sv-bg-admin">
      <AdminSidebar active="/admin/audit" onLogout={handleLogout} />

      <main className="flex-1 p-8 overflow-auto">

        {/* ── Header ── */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between mb-8">
          <div>
            <p className="font-mono text-[10px] tracking-[0.16em] mb-1.5"
               style={{ color: 'rgba(228,235,248,0.25)' }}>
              BLOCKCHAIN AUDIT
            </p>
            <h1 className="font-display font-black text-white mb-1"
                style={{ fontSize: 26, letterSpacing: '-0.02em' }}>
              Audit Trail Verification
            </h1>
            <p className="text-sm" style={{ color: 'rgba(228,235,248,0.40)' }}>
              Monitor cryptographic vote logs and detect integrity breaches.
            </p>
          </div>

          {/* System integrity badge */}
          {!loading && blockData && (
            <div
              className="flex items-center gap-2 px-3 py-2 rounded font-mono text-xs font-bold flex-shrink-0 mt-1"
              style={{
                background: chainValid ? 'rgba(132,189,0,0.10)' : 'rgba(200,0,90,0.10)',
                border: `1px solid ${chainValid ? 'rgba(132,189,0,0.30)' : 'rgba(200,0,90,0.30)'}`,
                color: chainValid ? 'var(--sv-lime)' : 'var(--sv-magenta)',
              }}
            >
              {chainValid
                ? <><CheckCircle2 className="w-3.5 h-3.5" /> System Integrity: {integrityPct}% Verified</>
                : <><ShieldAlert  className="w-3.5 h-3.5" /> Integrity Breach Detected</>
              }
            </div>
          )}
        </motion.div>

        {error && <div className="sv-alert-error mb-5">{error}</div>}

        {/* ── Filters ── */}
        <div className="sv-card-admin p-5 mb-3">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-40">
              <label className="sv-label">Election</label>
              <select className="sv-input-box" value={selectedElection}
                onChange={e => setSelectedElection(e.target.value)}>
                <option value="">All Elections</option>
                {elections.map(e => (
                  <option key={e.election_id} value={e.election_id}>
                    {e.title} ({e.status})
                  </option>
                ))}
              </select>
            </div>
            <div className="w-44">
              <label className="sv-label">Status Filter</label>
              <select className="sv-input-box" value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}>
                <option value="">All Status</option>
                <option value="verified">Verified Only</option>
                <option value="tampered">Tampered Only</option>
              </select>
            </div>
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={runIntegrityCheck}
              disabled={running}
              className="sv-btn-primary shrink-0 flex items-center gap-2"
            >
              {running
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Checking&hellip;</>
                : <><RefreshCw className="w-3.5 h-3.5" /> Run Integrity Check</>
              }
            </motion.button>
          </div>

          {/* Last verified line */}
          {fmtLastVerified && (
            <p className="mt-3 font-mono text-[10px]" style={{ color: 'rgba(228,235,248,0.30)' }}>
              Last Verified: {fmtLastVerified}&nbsp;
              {tamperedCt === 0
                ? <span style={{ color: 'var(--sv-lime)' }}>— No anomalies detected.</span>
                : <span style={{ color: 'var(--sv-magenta)' }}>— {tamperedCt} anomal{tamperedCt > 1 ? 'ies' : 'y'} detected.</span>
              }
            </p>
          )}
        </div>

        {/* ── View Toggle ── */}
        <div className="flex items-center gap-1 mb-5">
          {[
            { key: 'blockchain', icon: <LayoutGrid className="w-3.5 h-3.5" />, label: 'Blockchain View' },
            { key: 'table',      icon: <List        className="w-3.5 h-3.5" />, label: 'Table View' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setView(tab.key)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded font-mono text-xs font-semibold transition-all"
              style={{
                background: view === tab.key ? 'var(--sv-cyan)' : 'transparent',
                color: view === tab.key ? '#06091A' : 'rgba(228,235,248,0.40)',
                border: `1px solid ${view === tab.key ? 'var(--sv-cyan)' : 'rgba(0,159,227,0.15)'}`,
                cursor: 'pointer',
              }}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* ── Block Content ── */}
        {loading ? (
          <div className="flex items-center gap-2 py-16" style={{ color: 'rgba(228,235,248,0.30)' }}>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="font-mono text-xs tracking-[0.10em]">LOADING CHAIN&hellip;</span>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {view === 'blockchain' ? (
              <motion.div key="blockchain"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {blocks.length === 0 ? (
                  <div className="sv-card-admin p-10 text-center">
                    <p className="font-mono text-xs" style={{ color: 'rgba(228,235,248,0.25)' }}>
                      No blocks found for this election.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto pb-2">
                    <div className="flex items-center gap-0 min-w-max">
                      {blocks.map((block, i) => (
                        <React.Fragment key={block.index}>
                          <BlockCard block={block} index={i} />
                          {i < blocks.length - 1 && (
                            <div className="flex-shrink-0 flex items-center px-1"
                                 style={{ color: 'rgba(0,159,227,0.35)' }}>
                              <Link2 className="w-4 h-4" />
                            </div>
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div key="table"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <TableView blocks={blocks} />
              </motion.div>
            )}
          </AnimatePresence>
        )}

        {/* ── Summary Cards ── */}
        {!loading && blockData && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-6">
            {[
              {
                icon: <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--sv-lime)' }} />,
                label: 'Verified Votes',
                value: verifiedCt,
                color: 'var(--sv-lime)',
              },
              {
                icon: <AlertTriangle className="w-4 h-4" style={{ color: '#F59E0B' }} />,
                label: 'Tampered Votes',
                value: tamperedCt,
                color: tamperedCt > 0 ? 'var(--sv-magenta)' : 'rgba(228,235,248,0.35)',
              },
              {
                icon: <Clock className="w-4 h-4" style={{ color: 'var(--sv-cyan)' }} />,
                label: 'Last Integrity Scan',
                value: timeSinceScan,
                color: 'var(--sv-cyan)',
                small: true,
              },
              {
                icon: <Hash className="w-4 h-4" style={{ color: 'rgba(228,235,248,0.40)' }} />,
                label: 'Hash Length (bits)',
                value: verifiedCt > 0 ? 256 : 0,
                color: 'rgba(228,235,248,0.50)',
              },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="sv-card-admin p-4 flex items-center gap-3"
              >
                <div className="flex-shrink-0">{s.icon}</div>
                <div>
                  <p className="font-mono text-[9px] tracking-widest uppercase mb-0.5"
                     style={{ color: 'rgba(228,235,248,0.28)' }}>
                    {s.label}
                  </p>
                  <p className="font-display font-black"
                     style={{ fontSize: s.small ? 16 : 22, lineHeight: 1.2, color: s.color }}>
                    {s.value}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default AuditLog;
