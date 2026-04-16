import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Gem, Vote, BarChart3, ClipboardEdit, LogOut, ArrowRight,
         CheckCircle2, PenSquare, Archive } from 'lucide-react';
import { fetchElections } from '../../api/apiClient';

const OfficialDashboard = () => {
  // Counts of elections broken down by lifecycle status
  const [stats,   setStats]   = useState({ active: 0, draft: 0, closed: 0, total: 0 });
  // True while the elections list is being fetched
  const [loading, setLoading] = useState(true);
  const navigate  = useNavigate();
  // Read the role so we can conditionally show the Admin Panel link for admins
  const userRole  = localStorage.getItem('role');

  // Load election stats on mount
  useEffect(() => { loadStats(); }, []);

  // Fetch all elections and count them by status for the summary stats cards
  const loadStats = async () => {
    try {
      const data      = await fetchElections();
      const elections = data.elections || [];
      setStats({
        active: elections.filter(e => e.status === 'active').length,
        draft:  elections.filter(e => e.status === 'draft').length,
        closed: elections.filter(e => e.status === 'closed').length,
        total:  elections.length,
      });
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  };

  // Clear session and redirect to login
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  // Config for the four summary metric cards — each gets its own accent colour
  const statCards = [
    { label: 'Active',  value: stats.active,  icon: <CheckCircle2 className="w-4 h-4" />, color: 'var(--sv-lime)',    bg: 'rgba(132,189,0,0.08)',   border: 'rgba(132,189,0,0.18)' },
    { label: 'Draft',   value: stats.draft,   icon: <PenSquare    className="w-4 h-4" />, color: '#fbbf24',           bg: 'rgba(251,191,36,0.08)',  border: 'rgba(251,191,36,0.18)' },
    { label: 'Closed',  value: stats.closed,  icon: <Archive      className="w-4 h-4" />, color: 'var(--sv-text-dim)', bg: 'rgba(228,235,248,0.04)', border: 'var(--sv-border)' },
    { label: 'Total',   value: stats.total,   icon: <Vote         className="w-4 h-4" />, color: 'var(--sv-cyan)',    bg: 'rgba(0,159,227,0.08)',   border: 'rgba(0,159,227,0.18)' },
  ];

  return (
    <div className="sv-bg min-h-screen">

      {/* Nav */}
      <nav className="sv-nav px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gem className="w-4 h-4 text-tud-cyan" />
            <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote SU</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="sv-badge-official">Official</span>
            {/* Admins who navigate to this page also see a quick link back to the admin panel */}
            {userRole === 'admin' && (
              <Link to="/admin" className="sv-btn-outline" style={{ textDecoration: 'none' }}>
                Admin Panel
              </Link>
            )}
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                           onClick={handleLogout} className="sv-btn-ghost text-xs">
              <LogOut className="w-3.5 h-3.5" />
            </motion.button>
          </div>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-14">

        {/* Page header */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-12">
          <p className="font-mono text-[10px] tracking-[0.16em] mb-3" style={{ color: 'var(--sv-text-muted)' }}>
            STUDENT UNION
          </p>
          <h1 className="font-display font-black text-white"
              style={{ fontSize: 'clamp(1.8rem, 4vw, 2.8rem)', letterSpacing: '-0.02em' }}>
            Election Dashboard
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--sv-text-dim)' }}>
            Manage elections and view results
          </p>
        </motion.div>

        {/* Stats grid — four metric cards, each staggered by 70ms */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-12">
          {statCards.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
              className="sv-card p-5 relative overflow-hidden"
            >
              {/* Faded ordinal background number — purely decorative */}
              <span className="absolute bottom-1 right-2 font-display font-black leading-none pointer-events-none select-none"
                    style={{ fontSize: 56, color: 'rgba(228,235,248,0.03)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="w-8 h-8 flex items-center justify-center mb-3 rounded"
                   style={{ background: s.bg, border: `1px solid ${s.border}` }}>
                <span style={{ color: s.color }}>{s.icon}</span>
              </div>
              <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-1"
                 style={{ color: 'var(--sv-text-muted)' }}>
                {s.label}
              </p>
              {/* Show a dash while loading so the layout doesn't jump */}
              <p className="font-display font-black"
                 style={{ fontSize: 36, lineHeight: 1, color: loading ? 'rgba(228,235,248,0.12)' : s.color }}>
                {loading ? '—' : s.value}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Action cards — two main sub-pages: Manage Elections and Results */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {[
            {
              ordinal: '01',
              icon:    <ClipboardEdit className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
              title:   'Manage Elections',
              desc:    'Create, edit, and manage election campaigns. Add candidates and control election lifecycle.',
              href:    '/official/elections',
            },
            {
              ordinal: '02',
              icon:    <BarChart3 className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
              title:   'Results',
              desc:    'View results for active and completed elections, and blockchain integrity verification.',
              href:    '/official/results',
            },
          ].map((card, i) => (
            <motion.div
              key={card.href}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.30 + i * 0.10 }}
            >
              <Link
                to={card.href}
                style={{ textDecoration: 'none', display: 'block' }}
                className="sv-card-interactive h-full p-8 group relative overflow-hidden"
              >
                {/* Large faded ordinal (01, 02) — decorative background element */}
                <span className="absolute top-3 right-4 font-display font-black leading-none pointer-events-none select-none"
                      style={{ fontSize: 88, color: 'rgba(0,159,227,0.04)' }}>
                  {card.ordinal}
                </span>
                <div className="w-10 h-10 flex items-center justify-center mb-5 rounded"
                     style={{ background: 'rgba(0,159,227,0.08)', border: '1px solid rgba(0,159,227,0.14)' }}>
                  {card.icon}
                </div>
                <h3 className="font-display font-bold text-white mb-2" style={{ fontSize: 17 }}>
                  {card.title}
                </h3>
                <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--sv-text-dim)' }}>
                  {card.desc}
                </p>
                {/* Arrow slides right on card hover */}
                <span className="inline-flex items-center gap-1.5 font-mono text-[11px] tracking-[0.10em] uppercase"
                      style={{ color: 'var(--sv-cyan)' }}>
                  Open <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                </span>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default OfficialDashboard;
