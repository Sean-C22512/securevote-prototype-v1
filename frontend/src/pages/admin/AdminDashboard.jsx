import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Gem, Users, Vote, Link2, Settings, ClipboardList, LogOut, ArrowRight, Activity } from 'lucide-react';
import { fetchUsers, fetchAuditStats } from '../../api/apiClient';

const AdminSidebar = ({ active, onLogout }) => {
  const links = [
    { icon: <Activity    className="w-3.5 h-3.5" />, label: 'Dashboard',       href: '/admin' },
    { icon: <Users       className="w-3.5 h-3.5" />, label: 'User Management', href: '/admin/users' },
    { icon: <ClipboardList className="w-3.5 h-3.5" />, label: 'Audit Log',     href: '/admin/audit' },
    { icon: <Settings    className="w-3.5 h-3.5" />, label: 'Elections',        href: '/official' },
  ];
  return (
    <aside className="sv-sidebar">
      {/* Logo */}
      <div className="px-4 mb-10">
        <div className="flex items-center gap-2 mb-1">
          <Gem className="w-4 h-4 text-tud-cyan" />
          <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote</span>
        </div>
        <p className="font-mono text-[9px] tracking-[0.20em] ml-6"
           style={{ color: 'var(--sv-magenta)', letterSpacing: '0.18em' }}>
          ADMIN CONSOLE
        </p>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-2 space-y-0.5">
        {links.map((l) => {
          const isActive = l.href === active;
          return (
            <Link
              key={l.href}
              to={l.href}
              className={`flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'text-white'
                  : 'hover:text-white/70'
              }`}
              style={{
                textDecoration: 'none',
                borderLeft: `2px solid ${isActive ? 'var(--sv-cyan)' : 'transparent'}`,
                color: isActive ? 'white' : 'rgba(228,235,248,0.32)',
              }}
            >
              <span style={{ color: isActive ? 'var(--sv-cyan)' : 'inherit' }}>{l.icon}</span>
              <span>{l.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="px-2 mt-auto">
        <button
          onClick={onLogout}
          className="flex items-center gap-3 px-3 py-2.5 text-sm w-full text-left transition-colors"
          style={{ color: 'rgba(228,235,248,0.22)', background: 'none', border: 'none', cursor: 'pointer' }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--sv-magenta)'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(228,235,248,0.22)'}
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
};

const StatCard = ({ label, value, icon, color, loading, delay }) => (
  <motion.div
    initial={{ opacity: 0, y: 14 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay, duration: 0.38 }}
    className="sv-card-admin p-5"
  >
    <div className="flex items-start justify-between">
      <div>
        <p className="font-mono text-[10px] tracking-[0.14em] uppercase mb-3"
           style={{ color: 'rgba(228,235,248,0.30)' }}>
          {label}
        </p>
        <p className={`font-display font-black animate-flicker`}
           style={{ fontSize: 40, lineHeight: 1, color: loading ? 'rgba(228,235,248,0.10)' : color }}>
          {loading ? '—' : value}
        </p>
      </div>
      <div className="w-9 h-9 flex items-center justify-center"
           style={{ background: 'rgba(228,235,248,0.04)', border: '1px solid rgba(228,235,248,0.06)', borderRadius: 2 }}>
        <span style={{ color }}>{icon}</span>
      </div>
    </div>
  </motion.div>
);

const AdminDashboard = () => {
  const [stats,   setStats]   = useState({ users: 0, totalVotes: 0, chainValid: true });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { loadStats(); }, []);

  const loadStats = async () => {
    try {
      const [usersData, auditData] = await Promise.all([fetchUsers(), fetchAuditStats()]);
      setStats({
        users:      usersData.users?.length || 0,
        totalVotes: auditData.total_votes || 0,
        chainValid: auditData.chain_valid !== false,
      });
    } catch (err) {
      console.error('Failed to load stats:', err);
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

  const actionCards = [
    {
      icon:  <Users className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
      title: 'User Management',
      desc:  'Manage user accounts and role assignments',
      href:  '/admin/users',
    },
    {
      icon:  <ClipboardList className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
      title: 'Audit Log',
      desc:  'Blockchain verification and system security audit',
      href:  '/admin/audit',
    },
  ];

  return (
    <div className="min-h-screen flex sv-bg-admin">
      <AdminSidebar active="/admin" onLogout={handleLogout} />

      <main className="flex-1 p-8 overflow-auto">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="font-mono text-[10px] tracking-[0.16em] mb-2"
             style={{ color: 'rgba(228,235,248,0.25)' }}>
            SYSTEM OVERVIEW
          </p>
          <h1 className="font-display font-black text-white"
              style={{ fontSize: 28, letterSpacing: '-0.02em' }}>
            Admin Dashboard
          </h1>
          <p className="text-sm mt-1" style={{ color: 'rgba(228,235,248,0.40)' }}>
            System administration &amp; monitoring
          </p>
        </motion.div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          <StatCard
            label="Total Users"
            value={stats.users}
            icon={<Users className="w-4 h-4" />}
            color="var(--sv-cyan)"
            loading={loading}
            delay={0}
          />
          <StatCard
            label="Votes Cast"
            value={stats.totalVotes}
            icon={<Vote className="w-4 h-4" />}
            color="var(--sv-lime)"
            loading={loading}
            delay={0.08}
          />
          <StatCard
            label="Chain Status"
            value={stats.chainValid ? 'Valid' : 'Invalid'}
            icon={<Link2 className="w-4 h-4" />}
            color={stats.chainValid ? 'var(--sv-lime)' : 'var(--sv-magenta)'}
            loading={loading}
            delay={0.16}
          />
        </div>

        {/* Divider */}
        <div className="mb-8" style={{ height: 1, background: 'rgba(0,159,227,0.07)' }} />

        {/* Action cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {actionCards.map((card, i) => (
            <motion.div
              key={card.href}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.28 + i * 0.08 }}
            >
              <Link
                to={card.href}
                className="sv-card-admin group p-6 relative overflow-hidden"
                style={{
                  textDecoration: 'none', display: 'block',
                  transition: 'border-color 0.2s',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(0,159,227,0.22)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(0,159,227,0.08)'}
              >
                <div className="w-10 h-10 flex items-center justify-center mb-4"
                     style={{ background: 'rgba(0,159,227,0.07)', border: '1px solid rgba(0,159,227,0.12)', borderRadius: 2 }}>
                  {card.icon}
                </div>
                <h3 className="font-display font-bold text-white mb-1 text-sm">{card.title}</h3>
                <p className="text-sm leading-relaxed mb-4" style={{ color: 'rgba(228,235,248,0.40)' }}>
                  {card.desc}
                </p>
                <span className="inline-flex items-center gap-1.5 font-mono text-[10px] tracking-[0.10em] uppercase"
                      style={{ color: 'var(--sv-cyan)' }}>
                  Open <ArrowRight className="w-3 h-3" />
                </span>
              </Link>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;
