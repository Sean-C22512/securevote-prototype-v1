import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchUsers, createUser, updateUserRole } from '../../api/apiClient';

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newUser, setNewUser] = useState({ studentId: '', role: 'student' });
  const navigate = useNavigate();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const data = await fetchUsers();
      setUsers(data.users || []);
    } catch (err) {
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
      setShowAddModal(false);
      setNewUser({ studentId: '', role: 'student' });
      loadUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to create user');
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
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const getRoleBadgeClass = (role) => {
    switch (role) {
      case 'admin': return 'bg-danger';
      case 'official': return 'bg-warning text-dark';
      default: return 'bg-secondary';
    }
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <Link to="/admin" className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>
            SecureVote Admin
          </Link>
          <div className="d-flex align-items-center gap-3">
            <Link to="/admin" className="btn btn-outline-secondary btn-sm">
              Back to Dashboard
            </Link>
            <button onClick={handleLogout} className="btn btn-outline-danger btn-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container py-5">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <div>
            <h1 className="fw-bold mb-2">User Management</h1>
            <p className="text-muted">Manage user accounts and roles</p>
          </div>
          <button
            className="submit-btn px-4 py-2"
            onClick={() => setShowAddModal(true)}
          >
            Add User
          </button>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {/* Users Table */}
        <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
          <div className="card-body p-0">
            {loading ? (
              <div className="text-center py-5">
                <div className="spinner-border text-secondary" role="status">
                  <span className="visually-hidden">Loading...</span>
                </div>
              </div>
            ) : users.length === 0 ? (
              <div className="text-center py-5 text-muted">
                No users found
              </div>
            ) : (
              <div className="table-responsive">
                <table className="table table-hover mb-0">
                  <thead style={{ backgroundColor: '#f8f9fa' }}>
                    <tr>
                      <th className="border-0 py-3 px-4">Student ID</th>
                      <th className="border-0 py-3 px-4">Email</th>
                      <th className="border-0 py-3 px-4">Role</th>
                      <th className="border-0 py-3 px-4">Has Password</th>
                      <th className="border-0 py-3 px-4">Created</th>
                      <th className="border-0 py-3 px-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.student_id}>
                        <td className="py-3 px-4 fw-medium">{user.student_id}</td>
                        <td className="py-3 px-4 text-muted">{user.email || '-'}</td>
                        <td className="py-3 px-4">
                          <span className={`badge ${getRoleBadgeClass(user.role)}`}>
                            {user.role}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          {user.has_password ? (
                            <span className="text-success">Yes</span>
                          ) : (
                            <span className="text-muted">No</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-muted">
                          {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
                        </td>
                        <td className="py-3 px-4">
                          <select
                            className="form-select form-select-sm"
                            value={user.role}
                            onChange={(e) => handleRoleChange(user.student_id, e.target.value)}
                            style={{ width: 'auto', minWidth: '120px' }}
                          >
                            <option value="student">Student</option>
                            <option value="official">Official</option>
                            <option value="admin">Admin</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0" style={{ borderRadius: '16px' }}>
              <div className="modal-header border-0 pb-0">
                <h5 className="modal-title fw-bold">Add New User</h5>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => setShowAddModal(false)}
                ></button>
              </div>
              <form onSubmit={handleAddUser}>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Student ID</label>
                    <input
                      type="text"
                      className="form-control"
                      value={newUser.studentId}
                      onChange={(e) => setNewUser({ ...newUser, studentId: e.target.value.toUpperCase() })}
                      placeholder="e.g. C22512345"
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Role</label>
                    <select
                      className="form-select"
                      value={newUser.role}
                      onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                    >
                      <option value="student">Student</option>
                      <option value="official">Official</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                  <small className="text-muted">
                    User will need to register with a password to access the system.
                  </small>
                </div>
                <div className="modal-footer border-0 pt-0">
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={() => setShowAddModal(false)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="submit-btn px-4 py-2">
                    Create User
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
