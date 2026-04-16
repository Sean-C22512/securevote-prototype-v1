import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Gem, Activity, Users, ClipboardList, Settings, LogOut, Plus, X, Loader2 } from 'lucide-react';
import { fetchUsers, createUser, updateUserRole } from '../../api/apiClient';

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

const getRoleBadge = (role) => {
  switch (role) {
    case 'admin':    return 'sv-badge-admin';
    case 'official': return 'sv-badge-official';
    default:         return 'sv-badge-student';
  }
};

const UserManagement = () => {
  const [users,      setUsers]      = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  const [success,    setSuccess]    = useState('');
  const [showModal,  setShowModal]  = useState(false);
  const [newUser,    setNewUser]    = useState({ studentId: '', role: 'student' });
  const navigate = useNavigate();

  useEffect(() => { loadUsers(); }, []);

  const loadUsers = async () => {
    try {
      const data = await fetchUsers();
      setUsers(data.users || []);
    } catch {
      setError('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await createUser(newUser.studentId, newUser.role);
      setSuccess('User created successfully');
      setShowModal(false);
      setNewUser({ studentId: '', role: 'student' });
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to create user');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleRoleChange = async (studentId, newRole) => {
    try {
      await updateUserRole(studentId, newRole);
      setSuccess(`Role updated for ${studentId}`);
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to update role');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  return (
    <div className="min-h-screen flex sv-bg-admin">
      <AdminSidebar active="/admin/users" onLogout={handleLogout} />

      <main className="flex-1 p-8 overflow-auto">
        <div className="flex items-center justify-between mb-10">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <p className="font-mono text-[10px] tracking-[0.16em] mb-2"
               style={{ color: 'rgba(228,235,248,0.25)' }}>
              ADMINISTRATION
            </p>
            <h1 className="font-display font-black text-white"
                style={{ fontSize: 28, letterSpacing: '-0.02em' }}>
              User Management
            </h1>
            <p className="text-sm mt-1" style={{ color: 'rgba(228,235,248,0.40)' }}>
              Manage accounts and role assignments
            </p>
          </motion.div>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setShowModal(true)}
            className="sv-btn-primary"
          >
            <Plus className="w-3.5 h-3.5" /> Add User
          </motion.button>
        </div>

        {error   && <div className="sv-alert-error mb-5">{error}</div>}
        {success && <div className="sv-alert-success mb-5">{success}</div>}

        {/* Table */}
        <div className="sv-card-admin overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-20"
                 style={{ color: 'rgba(228,235,248,0.30)' }}>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="font-mono text-xs tracking-[0.10em]">LOADING USERS&hellip;</span>
            </div>

          ) : users.length === 0 ? (
            <div className="text-center py-16 font-mono text-xs tracking-[0.10em]"
                 style={{ color: 'rgba(228,235,248,0.25)' }}>
              NO USERS FOUND
            </div>

          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(0,159,227,0.08)' }}>
                    {['Student ID', 'Email', 'Role', 'Password', 'Created', 'Change Role'].map((col) => (
                      <th key={col} className="text-left px-5 py-3">
                        <span className="font-mono text-[10px] tracking-[0.14em] uppercase"
                              style={{ color: 'rgba(228,235,248,0.28)' }}>
                          {col}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((user, i) => (
                    <motion.tr
                      key={user.student_id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.03 }}
                      style={{ borderBottom: '1px solid rgba(0,159,227,0.05)' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,159,227,0.03)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td className="px-5 py-3.5">
                        <span className="font-mono font-semibold text-xs" style={{ color: 'var(--sv-cyan)' }}>
                          {user.student_id}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-sm" style={{ color: 'rgba(228,235,248,0.45)' }}>
                        {user.email || '—'}
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={getRoleBadge(user.role)}>{user.role}</span>
                      </td>
                      <td className="px-5 py-3.5">
                        {user.has_password
                          ? <span className="font-mono text-xs" style={{ color: 'var(--sv-lime)' }}>Yes</span>
                          : <span className="font-mono text-xs" style={{ color: 'rgba(228,235,248,0.25)' }}>No</span>
                        }
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="font-mono text-xs" style={{ color: 'rgba(228,235,248,0.30)' }}>
                          {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <select
                          className="font-mono text-xs px-2 py-1.5"
                          style={{
                            background: 'rgba(228,235,248,0.04)',
                            border: '1px solid rgba(0,159,227,0.12)',
                            color: 'var(--sv-text)',
                            borderRadius: 2,
                            outline: 'none',
                            cursor: 'pointer',
                          }}
                          value={user.role}
                          onChange={(e) => handleRoleChange(user.student_id, e.target.value)}
                        >
                          <option value="student">Student</option>
                          <option value="official">Official</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Add User Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(4,5,12,0.80)', backdropFilter: 'blur(8px)' }}
            onClick={(e) => e.target === e.currentTarget && setShowModal(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="w-full max-w-md sv-card p-8"
              style={{ border: '1px solid rgba(0,159,227,0.18)' }}
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="font-display font-bold text-white" style={{ fontSize: 18 }}>
                  Add New User
                </h2>
                <button onClick={() => setShowModal(false)} className="sv-btn-ghost p-1"
                        style={{ color: 'var(--sv-text-muted)' }}>
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleAddUser} className="space-y-5">
                <div>
                  <label className="sv-label">Student ID</label>
                  <input
                    type="text"
                    className="sv-input-box"
                    value={newUser.studentId}
                    onChange={(e) => setNewUser({ ...newUser, studentId: e.target.value.toUpperCase() })}
                    placeholder="e.g. C22512345"
                    required
                  />
                </div>
                <div>
                  <label className="sv-label">Role</label>
                  <select
                    className="sv-input-box"
                    value={newUser.role}
                    onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  >
                    <option value="student">Student</option>
                    <option value="official">Official</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <p className="font-mono text-[10px] tracking-[0.08em]" style={{ color: 'rgba(228,235,248,0.25)' }}>
                  User must register a password to access the system.
                </p>
                <div className="flex gap-3 pt-2">
                  <button type="button" onClick={() => setShowModal(false)} className="sv-btn-outline flex-1">
                    Cancel
                  </button>
                  <button type="submit" className="sv-btn-primary flex-1">
                    Create User
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default UserManagement;
