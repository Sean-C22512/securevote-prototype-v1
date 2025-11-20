import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  return (
    <div className="container mt-5">
      <div className="d-flex justify-content-between align-items-center mb-5">
        <h1>Dashboard</h1>
        <button onClick={handleLogout} className="btn btn-outline-danger">Logout</button>
      </div>
      
      <div className="row g-4">
        <div className="col-md-6">
          <div className="card h-100 shadow-sm">
            <div className="card-body text-center p-5">
              <h3>Cast Your Vote</h3>
              <p className="text-muted mb-4">Vote for your class representative</p>
              <Link to="/cast-vote" className="btn btn-primary btn-lg">Go to Voting</Link>
            </div>
          </div>
        </div>
        
        <div className="col-md-6">
          <div className="card h-100 shadow-sm">
            <div className="card-body text-center p-5">
              <h3>View Results</h3>
              <p className="text-muted mb-4">See live election results</p>
              <Link to="/results" className="btn btn-outline-primary btn-lg">View Results</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

