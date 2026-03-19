import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Vote, BarChart3, Fingerprint, Gem, LogOut, ArrowRight, ShieldCheck } from 'lucide-react';

const cardVariants = {
  hidden:   { opacity: 0, y: 18 },
  visible:  (i) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.10, duration: 0.38, ease: 'easeOut' },
  }),
};

const Dashboard = () => {
  const navigate  = useNavigate();
  const studentId = localStorage.getItem('studentId');
  const webAuthnSupported = typeof window !== 'undefined' && !!window.PublicKeyCredential;

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const cards = [
    {
      ordinal: '01',
      icon:    <Vote className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
      title:   'Cast Your Vote',
      desc:    'Participate in active elections and make your voice heard.',
      cta:     'Go to Voting',
      href:    '/cast-vote',
    },
    {
      ordinal: '02',
      icon:    <BarChart3 className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
      title:   'View Results',
      desc:    'See live vote counts and election results in real time.',
      cta:     'View Results',
      href:    '/results',
    },
    ...(webAuthnSupported ? [{
      ordinal: '03',
      icon:    <Fingerprint className="w-5 h-5" style={{ color: 'var(--sv-cyan)' }} />,
      title:   'Biometric Login',
      desc:    'Register TouchID, FaceID, or Windows Hello for passwordless sign-in.',
      cta:     'Add Biometric',
      href:    '/webauthn-setup',
    }] : []),
  ];

  return (
    <div className="sv-bg min-h-screen">

      {/* Nav */}
      <nav className="sv-nav px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gem className="w-4 h-4 text-tud-cyan" />
            <span className="font-display font-bold text-white text-sm tracking-wide">SecureVote</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs hidden sm:block" style={{ color: 'var(--sv-text-muted)' }}>
              {studentId}
            </span>
            <span className="sv-badge-student">Student</span>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleLogout}
              className="sv-btn-ghost text-xs"
            >
              <LogOut className="w-3.5 h-3.5" /> Logout
            </motion.button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div className="max-w-5xl mx-auto px-6 pt-14 pb-8">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.38 }}
        >
          <p className="font-mono text-xs tracking-[0.16em] mb-3" style={{ color: 'var(--sv-text-muted)' }}>
            WELCOME BACK
          </p>
          <h1 className="font-display font-black tracking-tight text-white"
              style={{ fontSize: 'clamp(2rem, 5vw, 3.5rem)', lineHeight: 1.0 }}>
            {studentId
              ? <><span style={{ color: 'var(--sv-cyan)' }}>{studentId}</span></>
              : 'Dashboard'}
          </h1>
          <p className="mt-2 text-sm" style={{ color: 'var(--sv-text-dim)' }}>
            TU Dublin Student Elections Platform
          </p>
        </motion.div>
      </div>

      {/* Cards */}
      <div className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((card, i) => (
            <motion.div
              key={card.href}
              custom={i}
              variants={cardVariants}
              initial="hidden"
              animate="visible"
            >
              <Link
                to={card.href}
                style={{ textDecoration: 'none', display: 'block' }}
                className="sv-card-interactive h-full p-7 group relative overflow-hidden"
              >
                {/* Background ordinal */}
                <span
                  className="absolute top-3 right-4 font-display font-black leading-none pointer-events-none select-none"
                  style={{ fontSize: 88, color: 'rgba(0,159,227,0.05)' }}
                >
                  {card.ordinal}
                </span>

                {/* Icon */}
                <div className="w-10 h-10 flex items-center justify-center mb-5 rounded"
                     style={{ background: 'rgba(0,159,227,0.08)', border: '1px solid rgba(0,159,227,0.14)' }}>
                  {card.icon}
                </div>

                {/* Text */}
                <h3 className="font-display font-bold text-white mb-2" style={{ fontSize: 17 }}>
                  {card.title}
                </h3>
                <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--sv-text-dim)' }}>
                  {card.desc}
                </p>

                {/* CTA */}
                <span className="inline-flex items-center gap-1.5 font-mono text-[11px] tracking-[0.10em] uppercase transition-all"
                      style={{ color: 'var(--sv-cyan)' }}>
                  {card.cta} <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                </span>
              </Link>
            </motion.div>
          ))}
        </div>

        {/* Security footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-12 flex justify-center"
        >
          <div className="inline-flex items-center gap-2.5 px-5 py-2.5"
               style={{ border: '1px solid rgba(132,189,0,0.18)', borderRadius: 2, background: 'rgba(132,189,0,0.06)' }}>
            <ShieldCheck className="w-3.5 h-3.5" style={{ color: 'var(--sv-lime)' }} />
            <span className="font-mono text-[10px] tracking-[0.12em] uppercase" style={{ color: 'var(--sv-lime)' }}>
              End-to-end encrypted &middot; Blockchain secured
            </span>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default Dashboard;
