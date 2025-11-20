import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/apiClient';

const Login = () => {
  const [studentId, setStudentId] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const data = await login(studentId);
      localStorage.setItem('token', data.token);
      navigate('/dashboard');
    } catch (err) {
      setError('Login failed. Please check your Student ID.');
    }
  };

  return (
    <div className="page-container">
      <div className="card p-5 shadow-sm" style={{ maxWidth: '400px', width: '100%' }}>
        <h2 className="text-center mb-4">SecureVote Login</h2>
        {error && <div className="alert alert-danger">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="form-label">Student ID</label>
            <input
              type="text"
              className="form-control"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              required
              placeholder="Enter Student ID"
            />
          </div>
          <button type="submit" className="btn btn-primary w-100">Login</button>
        </form>
      </div>
    </div>
  );
};

export default Login;

