import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  fetchElections,
  createElection,
  updateElection,
  deleteElection,
  startElection,
  endElection,
  addCandidate,
  removeCandidate
} from '../../api/apiClient';

const ElectionManagement = () => {
  const [elections, setElections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showCandidateModal, setShowCandidateModal] = useState(false);
  const [selectedElection, setSelectedElection] = useState(null);
  const [newElection, setNewElection] = useState({ title: '', description: '', candidates: [{ name: '', party: '' }, { name: '', party: '' }] });
  const [newCandidate, setNewCandidate] = useState({ name: '', description: '' });
  const navigate = useNavigate();
  const userRole = localStorage.getItem('role');

  useEffect(() => {
    loadElections();
  }, []);

  const loadElections = async () => {
    try {
      const data = await fetchElections();
      setElections(data.elections || []);
    } catch (err) {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...newElection,
        candidates: newElection.candidates
          .filter(c => c.name.trim())
          .map(c => ({ name: c.name.trim(), party: c.party.trim() || undefined }))
      };
      if (payload.candidates.length < 2) {
        setError('At least 2 candidates are required');
        return;
      }
      await createElection(payload);
      setSuccess('Election created successfully');
      setShowCreateModal(false);
      setNewElection({ title: '', description: '', candidates: [{ name: '', party: '' }, { name: '', party: '' }] });
      loadElections();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to create election');
    }
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await updateElection(selectedElection.election_id, {
        title: selectedElection.title,
        description: selectedElection.description
      });
      setSuccess('Election updated successfully');
      setShowEditModal(false);
      loadElections();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to update election');
    }
  };

  const handleDelete = async (electionId) => {
    if (!window.confirm('Are you sure you want to delete this election?')) return;
    try {
      await deleteElection(electionId);
      setSuccess('Election deleted successfully');
      loadElections();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to delete election');
    }
  };

  const handleStart = async (electionId) => {
    if (!window.confirm('Are you sure you want to start this election? Voting will begin immediately.')) return;
    try {
      await startElection(electionId);
      setSuccess('Election started successfully');
      loadElections();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to start election');
    }
  };

  const handleEnd = async (electionId) => {
    if (!window.confirm('Are you sure you want to end this election? Voting will be closed.')) return;
    try {
      await endElection(electionId);
      setSuccess('Election ended successfully');
      loadElections();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to end election');
    }
  };

  const handleAddCandidate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await addCandidate(selectedElection.election_id, newCandidate);
      setSuccess('Candidate added successfully');
      setNewCandidate({ name: '', description: '' });
      loadElections();
      // Update selected election with new data
      const updated = await fetchElections();
      const current = updated.elections.find(e => e.election_id === selectedElection.election_id);
      setSelectedElection(current);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to add candidate');
    }
  };

  const handleRemoveCandidate = async (candidateId) => {
    if (!window.confirm('Remove this candidate?')) return;
    try {
      await removeCandidate(selectedElection.election_id, candidateId);
      setSuccess('Candidate removed');
      loadElections();
      const updated = await fetchElections();
      const current = updated.elections.find(e => e.election_id === selectedElection.election_id);
      setSelectedElection(current);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err?.error || 'Failed to remove candidate');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'active': return 'bg-success';
      case 'draft': return 'bg-warning text-dark';
      case 'closed': return 'bg-secondary';
      default: return 'bg-light text-dark';
    }
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: '#F8F9FA' }}>
      {/* Navigation */}
      <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div className="container">
          <Link to="/official" className="navbar-brand fw-bold" style={{ color: '#6f42c1' }}>
            SecureVote SU
          </Link>
          <div className="d-flex align-items-center gap-3">
            <Link to="/official" className="btn btn-outline-secondary btn-sm">
              Back to Dashboard
            </Link>
            {userRole === 'admin' && (
              <Link to="/admin" className="btn btn-outline-secondary btn-sm">
                Admin Panel
              </Link>
            )}
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
            <h1 className="fw-bold mb-2">Election Management</h1>
            <p className="text-muted">Create and manage election campaigns</p>
          </div>
          <button
            className="submit-btn px-4 py-2"
            onClick={() => setShowCreateModal(true)}
          >
            Create Election
          </button>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {/* Elections List */}
        {loading ? (
          <div className="text-center py-5">
            <div className="spinner-border text-secondary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : elections.length === 0 ? (
          <div className="card border-0 shadow-sm" style={{ borderRadius: '16px' }}>
            <div className="card-body text-center py-5">
              <p className="text-muted mb-3">No elections found</p>
              <button
                className="submit-btn px-4 py-2"
                onClick={() => setShowCreateModal(true)}
              >
                Create Your First Election
              </button>
            </div>
          </div>
        ) : (
          <div className="row g-4">
            {elections.map((election) => (
              <div key={election.election_id} className="col-md-6">
                <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '16px' }}>
                  <div className="card-body p-4">
                    <div className="d-flex justify-content-between align-items-start mb-3">
                      <h5 className="fw-bold mb-0">{election.title}</h5>
                      <span className={`badge ${getStatusBadgeClass(election.status)}`}>
                        {election.status}
                      </span>
                    </div>
                    <p className="text-muted mb-3">{election.description || 'No description'}</p>

                    <div className="mb-3">
                      <small className="text-muted">
                        Candidates: {election.candidates?.length || 0}
                      </small>
                    </div>

                    <div className="d-flex flex-wrap gap-2">
                      {election.status === 'draft' && (
                        <>
                          <button
                            className="btn btn-sm btn-outline-primary"
                            onClick={() => {
                              setSelectedElection(election);
                              setShowEditModal(true);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => {
                              setSelectedElection(election);
                              setShowCandidateModal(true);
                            }}
                          >
                            Candidates
                          </button>
                          <button
                            className="btn btn-sm btn-success"
                            onClick={() => handleStart(election.election_id)}
                            disabled={!election.candidates || election.candidates.length < 2}
                          >
                            Start
                          </button>
                          <button
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => handleDelete(election.election_id)}
                          >
                            Delete
                          </button>
                        </>
                      )}
                      {election.status === 'active' && (
                        <button
                          className="btn btn-sm btn-warning"
                          onClick={() => handleEnd(election.election_id)}
                        >
                          End Election
                        </button>
                      )}
                      {election.status === 'closed' && (
                        <Link
                          to={`/official/results?election=${election.election_id}`}
                          className="btn btn-sm btn-outline-primary"
                        >
                          View Results
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Election Modal */}
      {showCreateModal && (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0" style={{ borderRadius: '16px' }}>
              <div className="modal-header border-0 pb-0">
                <h5 className="modal-title fw-bold">Create New Election</h5>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => setShowCreateModal(false)}
                ></button>
              </div>
              <form onSubmit={handleCreate}>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Title</label>
                    <input
                      type="text"
                      className="form-control"
                      value={newElection.title}
                      onChange={(e) => setNewElection({ ...newElection, title: e.target.value })}
                      placeholder="e.g. Class Representative Election 2024"
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-control"
                      rows="3"
                      value={newElection.description}
                      onChange={(e) => setNewElection({ ...newElection, description: e.target.value })}
                      placeholder="Describe the election..."
                    ></textarea>
                  </div>
                  <div className="mb-3">
                    <label className="form-label fw-medium">Candidates (minimum 2)</label>
                    {newElection.candidates.map((candidate, index) => (
                      <div key={index} className="d-flex gap-2 mb-2 align-items-center">
                        <input
                          type="text"
                          className="form-control"
                          placeholder={`Candidate ${index + 1} name`}
                          value={candidate.name}
                          onChange={(e) => {
                            const updated = [...newElection.candidates];
                            updated[index] = { ...updated[index], name: e.target.value };
                            setNewElection({ ...newElection, candidates: updated });
                          }}
                          required
                        />
                        <input
                          type="text"
                          className="form-control"
                          placeholder="Party (optional)"
                          value={candidate.party}
                          onChange={(e) => {
                            const updated = [...newElection.candidates];
                            updated[index] = { ...updated[index], party: e.target.value };
                            setNewElection({ ...newElection, candidates: updated });
                          }}
                        />
                        {newElection.candidates.length > 2 && (
                          <button
                            type="button"
                            className="btn btn-outline-danger btn-sm"
                            onClick={() => {
                              const updated = newElection.candidates.filter((_, i) => i !== index);
                              setNewElection({ ...newElection, candidates: updated });
                            }}
                          >
                            &times;
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      className="btn btn-outline-secondary btn-sm mt-1"
                      onClick={() => setNewElection({
                        ...newElection,
                        candidates: [...newElection.candidates, { name: '', party: '' }]
                      })}
                    >
                      + Add Candidate
                    </button>
                  </div>
                </div>
                <div className="modal-footer border-0 pt-0">
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="submit-btn px-4 py-2"
                    disabled={newElection.candidates.filter(c => c.name.trim()).length < 2}
                  >
                    Create Election
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Edit Election Modal */}
      {showEditModal && selectedElection && (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0" style={{ borderRadius: '16px' }}>
              <div className="modal-header border-0 pb-0">
                <h5 className="modal-title fw-bold">Edit Election</h5>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => setShowEditModal(false)}
                ></button>
              </div>
              <form onSubmit={handleUpdate}>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Title</label>
                    <input
                      type="text"
                      className="form-control"
                      value={selectedElection.title}
                      onChange={(e) => setSelectedElection({ ...selectedElection, title: e.target.value })}
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-control"
                      rows="3"
                      value={selectedElection.description || ''}
                      onChange={(e) => setSelectedElection({ ...selectedElection, description: e.target.value })}
                    ></textarea>
                  </div>
                </div>
                <div className="modal-footer border-0 pt-0">
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={() => setShowEditModal(false)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="submit-btn px-4 py-2">
                    Save Changes
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Manage Candidates Modal */}
      {showCandidateModal && selectedElection && (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered modal-lg">
            <div className="modal-content border-0" style={{ borderRadius: '16px' }}>
              <div className="modal-header border-0 pb-0">
                <h5 className="modal-title fw-bold">Manage Candidates - {selectedElection.title}</h5>
                <button
                  type="button"
                  className="btn-close"
                  onClick={() => {
                    setShowCandidateModal(false);
                    setNewCandidate({ name: '', description: '' });
                  }}
                ></button>
              </div>
              <div className="modal-body">
                {/* Add Candidate Form */}
                <form onSubmit={handleAddCandidate} className="mb-4 p-3 bg-light rounded">
                  <h6 className="fw-bold mb-3">Add New Candidate</h6>
                  <div className="row g-3">
                    <div className="col-md-5">
                      <input
                        type="text"
                        className="form-control"
                        placeholder="Candidate name"
                        value={newCandidate.name}
                        onChange={(e) => setNewCandidate({ ...newCandidate, name: e.target.value })}
                        required
                      />
                    </div>
                    <div className="col-md-5">
                      <input
                        type="text"
                        className="form-control"
                        placeholder="Description (optional)"
                        value={newCandidate.description}
                        onChange={(e) => setNewCandidate({ ...newCandidate, description: e.target.value })}
                      />
                    </div>
                    <div className="col-md-2">
                      <button type="submit" className="btn btn-success w-100">
                        Add
                      </button>
                    </div>
                  </div>
                </form>

                {/* Candidates List */}
                <h6 className="fw-bold mb-3">Current Candidates ({selectedElection.candidates?.length || 0})</h6>
                {!selectedElection.candidates || selectedElection.candidates.length === 0 ? (
                  <p className="text-muted">No candidates added yet. Add at least 2 candidates to start the election.</p>
                ) : (
                  <div className="list-group">
                    {selectedElection.candidates.map((candidate) => (
                      <div key={candidate.candidate_id} className="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                          <strong>{candidate.name}</strong>
                          {candidate.description && (
                            <small className="text-muted d-block">{candidate.description}</small>
                          )}
                        </div>
                        <button
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => handleRemoveCandidate(candidate.candidate_id)}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="modal-footer border-0 pt-0">
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => {
                    setShowCandidateModal(false);
                    setNewCandidate({ name: '', description: '' });
                  }}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ElectionManagement;
