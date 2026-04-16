import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Gem, LogOut, Plus, X, Loader2, Play, Square, Trash2, Users2,
         Edit2, ChevronLeft, Search } from 'lucide-react';
import {
  fetchElections, createElection, updateElection, deleteElection,
  startElection, endElection, addCandidate, removeCandidate, fetchProgrammes,
} from '../../api/apiClient';
import DOMPurify from 'dompurify';

// Reusable animated modal wrapper — renders children inside a blurred overlay.
// Clicking outside the white card closes the modal via onClose.
const Modal = ({ show, onClose, title, children }) => (
  <AnimatePresence>
    {show && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(4,5,12,0.75)', backdropFilter: 'blur(8px)' }}
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96 }}
          className="w-full max-w-lg sv-card p-8 shadow-sv-glow"
          style={{ border: '1px solid rgba(0,159,227,0.18)' }}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display font-bold text-white" style={{ fontSize: 18 }}>{title}</h2>
            <button onClick={onClose} className="sv-btn-ghost p-1" style={{ color: 'var(--sv-text-muted)' }}>
              <X className="w-4 h-4" />
            </button>
          </div>
          {children}
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
);

// Map an election status string to the correct CSS badge class
const statusBadge = (status) => {
  switch (status) {
    case 'active': return 'sv-badge-active';
    case 'draft':  return 'sv-badge-draft';
    case 'closed': return 'sv-badge-closed';
    default:       return 'sv-badge-closed';
  }
};

const ElectionManagement = () => {
  // All elections returned by the API
  const [elections,          setElections]          = useState([]);
  // True while the elections list is loading
  const [loading,            setLoading]            = useState(true);
  // Page-level error shown in the red banner
  const [error,              setError]              = useState('');
  // Error displayed inside the Create modal
  const [modalError,         setModalError]         = useState('');
  // Page-level success banner (auto-clears after 3s)
  const [success,            setSuccess]            = useState('');
  // Controls visibility of the three modals
  const [showCreateModal,    setShowCreateModal]    = useState(false);
  const [showEditModal,      setShowEditModal]      = useState(false);
  const [showCandidateModal, setShowCandidateModal] = useState(false);
  // The election currently being edited or whose candidates are being managed
  const [selectedElection,   setSelectedElection]   = useState(null);
  // Form state for the Create Election modal
  const [newElection,        setNewElection]        = useState({
    title: '', description: '',
    candidates: [{ name: '', party: '' }, { name: '', party: '' }],
    eligible_programmes: [],
  });
  // Form state for adding a single candidate in the Candidates modal
  const [newCandidate,       setNewCandidate]       = useState({ name: '', description: '' });
  // Full list of TU Dublin programmes for the eligibility picker
  const [programmes,         setProgrammes]         = useState([]);
  // Text typed into the programme search box
  const [progSearch,         setProgSearch]         = useState('');
  // True = open to all students; false = restricted to specific programmes
  const [allStudents,        setAllStudents]        = useState(true);
  const navigate  = useNavigate();
  const userRole  = localStorage.getItem('role');

  // Load elections and the full programme list on mount
  useEffect(() => {
    loadElections();
    fetchProgrammes().then(d => setProgrammes(d.programmes || [])).catch(() => {});
  }, []);

  // Fetch the latest elections from the backend
  const loadElections = async () => {
    try {
      const data = await fetchElections();
      setElections(data.elections || []);
    } catch {
      setError('Failed to load elections');
    } finally {
      setLoading(false);
    }
  };

  // Show a success message that disappears automatically after 3 seconds
  const flash = (msg) => { setSuccess(msg); setTimeout(() => setSuccess(''), 3000); };

  // Filter the programme list by whatever the user has typed in the search box
  const filteredProgrammes = programmes.filter(p => {
    const q = progSearch.toLowerCase();
    return p.code.toLowerCase().includes(q) || p.name.toLowerCase().includes(q);
  });

  // Toggle a programme in the eligible_programmes array for the election being created
  const toggleProgramme = (prog) => {
    const already = newElection.eligible_programmes.some(p => p.code === prog.code);
    setNewElection({
      ...newElection,
      eligible_programmes: already
        ? newElection.eligible_programmes.filter(p => p.code !== prog.code)
        : [...newElection.eligible_programmes, { code: prog.code, name: prog.name }],
    });
  };

  // Submit the Create Election form — sanitises all text inputs before sending to the backend
  const handleCreate = async (e) => {
    e.preventDefault();
    setModalError('');
    try {
      const payload = {
        title:       DOMPurify.sanitize(newElection.title.trim()),
        description: DOMPurify.sanitize(newElection.description.trim()),
        // Only include candidates that have a non-empty name
        candidates:  newElection.candidates
          .filter(c => c.name.trim())
          .map(c => ({
            name:  DOMPurify.sanitize(c.name.trim()),
            party: c.party.trim() ? DOMPurify.sanitize(c.party.trim()) : undefined,
          })),
        // Empty array means "all students"; otherwise send the specific programme list
        eligible_programmes: allStudents ? [] : newElection.eligible_programmes,
      };

      // Frontend validation with specific messages
      if (!payload.title) { setModalError('Please enter an election title.'); return; }
      if (payload.candidates.length < 2) { setModalError('At least 2 candidates are required.'); return; }
      const names = payload.candidates.map(c => c.name.toLowerCase());
      if (new Set(names).size !== names.length) { setModalError('Candidate names must be unique — remove duplicate entries.'); return; }

      await createElection(payload);
      flash('Election created successfully');
      setShowCreateModal(false);
      setModalError('');
      // Reset the form to its initial blank state
      setNewElection({ title: '', description: '', candidates: [{ name: '', party: '' }, { name: '', party: '' }], eligible_programmes: [] });
      setAllStudents(true);
      setProgSearch('');
      loadElections();
    } catch (err) {
      const msg = err?.error || err?.message || 'Failed to create election';
      setModalError(msg);
    }
  };

  // Submit the Edit Election form — only title and description can be changed after creation
  const handleUpdate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await updateElection(selectedElection.election_id, {
        title:       DOMPurify.sanitize(selectedElection.title.trim()),
        description: DOMPurify.sanitize((selectedElection.description || '').trim()),
      });
      flash('Election updated successfully');
      setShowEditModal(false);
      loadElections();
    } catch (err) {
      setError(err?.error || 'Failed to update election');
    }
  };

  // Delete an election after a browser confirm prompt — only draft elections can be deleted
  const handleDelete = async (electionId) => {
    if (!window.confirm('Delete this election?')) return;
    try {
      await deleteElection(electionId);
      flash('Election deleted');
      loadElections();
    } catch (err) {
      setError(err?.error || 'Failed to delete election');
    }
  };

  // Transition an election from draft to active — requires at least 2 candidates
  const handleStart = async (electionId) => {
    if (!window.confirm('Start this election? Voting will begin immediately.')) return;
    try {
      await startElection(electionId);
      flash('Election started');
      loadElections();
    } catch (err) {
      setError(err?.error || 'Failed to start election');
    }
  };

  // Transition an election from active to closed — voting immediately stops
  const handleEnd = async (electionId) => {
    if (!window.confirm('End this election? Voting will be closed.')) return;
    try {
      await endElection(electionId);
      flash('Election ended');
      loadElections();
    } catch (err) {
      setError(err?.error || 'Failed to end election');
    }
  };

  // Add a new candidate to the selected election and refresh both the list and the modal view
  const handleAddCandidate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await addCandidate(selectedElection.election_id, {
        name:        DOMPurify.sanitize(newCandidate.name.trim()),
        description: DOMPurify.sanitize((newCandidate.description || '').trim()),
      });
      flash('Candidate added');
      setNewCandidate({ name: '', description: '' });
      loadElections();
      // Re-fetch to update the candidate list inside the still-open modal
      const updated = await fetchElections();
      setSelectedElection(updated.elections.find(el => el.election_id === selectedElection.election_id));
    } catch (err) {
      setError(err?.error || 'Failed to add candidate');
    }
  };

  // Remove a candidate from the selected election after confirming
  const handleRemoveCandidate = async (candidateId) => {
    if (!window.confirm('Remove this candidate?')) return;
    try {
      await removeCandidate(selectedElection.election_id, candidateId);
      flash('Candidate removed');
      loadElections();
      // Refresh the modal's candidate list
      const updated = await fetchElections();
      setSelectedElection(updated.elections.find(el => el.election_id === selectedElection.election_id));
    } catch (err) {
      setError(err?.error || 'Failed to remove candidate');
    }
  };

  // Clear session and return to login
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('studentId');
    navigate('/');
  };

  return (
    <div className="sv-bg min-h-screen">

      {/* Nav */}
      <nav className="sv-nav px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gem className="w-4 h-4 text-tud-cyan" />
            <Link to="/official" style={{ textDecoration: 'none' }}
                  className="font-display font-bold text-white text-sm tracking-wide">
              SecureVote SU
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/official" className="sv-btn-outline" style={{ textDecoration: 'none' }}>
              <ChevronLeft className="w-3 h-3" /> Dashboard
            </Link>
            {/* Admin users also get a quick link to the admin panel */}
            {userRole === 'admin' && (
              <Link to="/admin" className="sv-btn-outline" style={{ textDecoration: 'none' }}>Admin</Link>
            )}
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                           onClick={handleLogout} className="sv-btn-ghost text-xs">
              <LogOut className="w-3.5 h-3.5" />
            </motion.button>
          </div>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-12">

        {/* Page header with Create Election button */}
        <div className="flex items-start justify-between mb-10">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
            <p className="font-mono text-[10px] tracking-[0.16em] mb-2" style={{ color: 'var(--sv-text-muted)' }}>
              ELECTION MANAGEMENT
            </p>
            <h1 className="font-display font-black text-white"
                style={{ fontSize: 'clamp(1.5rem, 3.5vw, 2.2rem)', letterSpacing: '-0.02em' }}>
              Elections
            </h1>
          </motion.div>
          {/* Opens the Create Election modal */}
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setShowCreateModal(true)}
            className="sv-btn-primary shrink-0"
          >
            <Plus className="w-3.5 h-3.5" /> Create Election
          </motion.button>
        </div>

        {error   && <div className="sv-alert-error mb-5">{error}</div>}
        {success && <div className="sv-alert-success mb-5">{success}</div>}

        {/* Election list — loading spinner, empty state, or grid of election cards */}
        {loading ? (
          <div className="text-center py-24">
            <Loader2 className="w-7 h-7 animate-spin mx-auto text-tud-cyan" />
          </div>

        ) : elections.length === 0 ? (
          // Empty state with a shortcut to create the first election
          <div className="sv-card p-14 text-center">
            <p className="text-sm mb-6" style={{ color: 'var(--sv-text-muted)' }}>No elections yet.</p>
            <button onClick={() => setShowCreateModal(true)} className="sv-btn-primary">
              <Plus className="w-3.5 h-3.5" /> Create First Election
            </button>
          </div>

        ) : (
          // Grid of election cards — each shows the election details and lifecycle action buttons
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {elections.map((election, i) => (
              <motion.div
                key={election.election_id}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="sv-card p-6"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-display font-bold text-white text-sm leading-snug pr-3">
                    {election.title}
                  </h3>
                  {/* Status badge in the corner — draft / active / closed */}
                  <span className={`${statusBadge(election.status)} shrink-0`}>{election.status}</span>
                </div>
                <p className="text-sm leading-relaxed mb-2" style={{ color: 'var(--sv-text-dim)' }}>
                  {election.description || 'No description'}
                </p>
                <p className="font-mono text-[10px] mb-5" style={{ color: 'var(--sv-text-muted)' }}>
                  {election.candidates?.length || 0} candidates
                </p>

                {/* Action buttons — vary by lifecycle status */}
                <div className="flex flex-wrap gap-2">
                  {/* Draft elections can be edited, have candidates managed, started, or deleted */}
                  {election.status === 'draft' && (
                    <>
                      <button
                        onClick={() => { setSelectedElection(election); setShowEditModal(true); }}
                        className="sv-btn-outline text-xs"
                        style={{ padding: '7px 12px' }}>
                        <Edit2 className="w-3 h-3" /> Edit
                      </button>
                      <button
                        onClick={() => { setSelectedElection(election); setShowCandidateModal(true); }}
                        className="sv-btn-outline text-xs"
                        style={{ padding: '7px 12px', color: 'var(--sv-text-dim)', borderColor: 'var(--sv-border)' }}>
                        <Users2 className="w-3 h-3" /> Candidates
                      </button>
                      {/* Start button is disabled until at least 2 candidates have been added */}
                      <button
                        onClick={() => handleStart(election.election_id)}
                        disabled={!election.candidates || election.candidates.length < 2}
                        className="sv-btn-lime"
                        style={{ padding: '7px 12px', fontSize: 10 }}>
                        <Play className="w-3 h-3" /> Start
                      </button>
                      <button
                        onClick={() => handleDelete(election.election_id)}
                        className="sv-btn-danger"
                        style={{ padding: '7px 12px' }}>
                        <Trash2 className="w-3 h-3" /> Delete
                      </button>
                    </>
                  )}
                  {/* Active elections can only be ended */}
                  {election.status === 'active' && (
                    <button
                      onClick={() => handleEnd(election.election_id)}
                      className="sv-btn-amber"
                      style={{ padding: '7px 14px' }}>
                      <Square className="w-3 h-3" /> End Election
                    </button>
                  )}
                  {/* Closed elections link through to the results page, pre-selecting this election */}
                  {election.status === 'closed' && (
                    <Link
                      to={`/official/results?election=${election.election_id}`}
                      className="sv-btn-outline"
                      style={{ padding: '7px 12px', textDecoration: 'none', fontSize: 10 }}>
                      View Results
                    </Link>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <Modal show={showCreateModal} onClose={() => setShowCreateModal(false)} title="Create New Election">
        <form onSubmit={handleCreate} className="space-y-5">
          <div>
            <label className="sv-label">Title</label>
            <input type="text" className="sv-input-box"
              value={newElection.title}
              onChange={(e) => setNewElection({ ...newElection, title: e.target.value })}
              placeholder="e.g. Class Representative Election 2025" required />
          </div>
          <div>
            <label className="sv-label">Description</label>
            <textarea className="sv-input-box resize-none" rows={3}
              value={newElection.description}
              onChange={(e) => setNewElection({ ...newElection, description: e.target.value })}
              placeholder="Describe the election&hellip;" />
          </div>
          {/* Eligibility — toggle between "all students" and a specific programme list */}
          <div>
            <label className="sv-label">Eligible Students</label>
            <div className="flex items-center gap-3 mb-3">
              {/* All Students button — clears programme restrictions */}
              <button
                type="button"
                onClick={() => setAllStudents(true)}
                className={allStudents ? 'sv-btn-primary' : 'sv-btn-outline'}
                style={{ padding: '6px 14px', fontSize: 11 }}>
                All Students
              </button>
              {/* Specific Programmes button — reveals the searchable programme picker */}
              <button
                type="button"
                onClick={() => setAllStudents(false)}
                className={!allStudents ? 'sv-btn-primary' : 'sv-btn-outline'}
                style={{ padding: '6px 14px', fontSize: 11 }}>
                Specific Programmes
              </button>
            </div>

            {/* Programme picker — only visible when "Specific Programmes" is selected */}
            {!allStudents && (
              <div style={{ border: '1px solid var(--sv-border)', borderRadius: 2, overflow: 'hidden' }}>
                {/* Search box */}
                <div className="flex items-center gap-2 px-3 py-2"
                     style={{ borderBottom: '1px solid var(--sv-border)', background: 'rgba(228,235,248,0.02)' }}>
                  <Search className="w-3 h-3 shrink-0" style={{ color: 'var(--sv-text-muted)' }} />
                  <input
                    type="text"
                    value={progSearch}
                    onChange={(e) => setProgSearch(e.target.value)}
                    placeholder="Search by code or name…"
                    className="flex-1 bg-transparent outline-none text-sm text-white placeholder-gray-500"
                    style={{ border: 'none' }}
                  />
                </div>

                {/* Selected programme tags — each has an X to deselect it */}
                {newElection.eligible_programmes.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 px-3 py-2"
                       style={{ borderBottom: '1px solid var(--sv-border)' }}>
                    {newElection.eligible_programmes.map(p => (
                      <span key={p.code}
                            className="flex items-center gap-1 font-mono text-[10px] px-2 py-1"
                            style={{ background: 'rgba(0,159,227,0.12)', border: '1px solid rgba(0,159,227,0.25)',
                                     borderRadius: 2, color: 'var(--sv-cyan)' }}>
                        {p.code}
                        <button type="button" onClick={() => toggleProgramme(p)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0 }}>
                          <X className="w-2.5 h-2.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Scrollable list of matching programmes — clicking one adds or removes it */}
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {filteredProgrammes.length === 0 ? (
                    <p className="text-xs text-center py-4" style={{ color: 'var(--sv-text-muted)' }}>No matches</p>
                  ) : (
                    filteredProgrammes.map(p => {
                      const selected = newElection.eligible_programmes.some(ep => ep.code === p.code);
                      return (
                        <div key={p.code}
                             onClick={() => toggleProgramme(p)}
                             className="flex items-center gap-3 px-3 py-2 cursor-pointer transition-colors"
                             style={{ background: selected ? 'rgba(0,159,227,0.08)' : 'transparent' }}
                             onMouseEnter={e => { if (!selected) e.currentTarget.style.background = 'rgba(228,235,248,0.03)'; }}
                             onMouseLeave={e => { e.currentTarget.style.background = selected ? 'rgba(0,159,227,0.08)' : 'transparent'; }}>
                          <span className="font-mono text-[11px] shrink-0" style={{ color: 'var(--sv-cyan)', width: 52 }}>
                            {p.code}
                          </span>
                          <span className="text-sm text-white leading-snug flex-1">{p.name}</span>
                          {selected && <span className="font-mono text-[9px]" style={{ color: 'var(--sv-lime)' }}>✓</span>}
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Footer showing how many programmes are currently selected */}
                {newElection.eligible_programmes.length > 0 && (
                  <p className="font-mono text-[10px] px-3 py-2" style={{ color: 'var(--sv-text-muted)', borderTop: '1px solid var(--sv-border)' }}>
                    {newElection.eligible_programmes.length} programme{newElection.eligible_programmes.length !== 1 ? 's' : ''} selected
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Candidate rows — start with 2 blank rows; more can be added dynamically */}
          <div>
            <label className="sv-label">Candidates (min 2)</label>
            <div className="space-y-2">
              {newElection.candidates.map((c, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <input type="text" className="sv-input-box flex-1"
                    placeholder={`Candidate ${idx + 1} name`} value={c.name} required
                    onChange={(e) => {
                      const updated = [...newElection.candidates];
                      updated[idx] = { ...updated[idx], name: e.target.value };
                      setNewElection({ ...newElection, candidates: updated });
                    }} />
                  <input type="text" className="sv-input-box flex-1"
                    placeholder="Party (optional)" value={c.party}
                    onChange={(e) => {
                      const updated = [...newElection.candidates];
                      updated[idx] = { ...updated[idx], party: e.target.value };
                      setNewElection({ ...newElection, candidates: updated });
                    }} />
                  {/* Remove row button — only shown when there are more than the minimum 2 candidates */}
                  {newElection.candidates.length > 2 && (
                    <button type="button" className="sv-btn-ghost p-1"
                      onClick={() => setNewElection({ ...newElection, candidates: newElection.candidates.filter((_, i) => i !== idx) })}>
                      <X className="w-3.5 h-3.5" style={{ color: 'var(--sv-magenta)' }} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            {/* Inline "add candidate" text link appends a new blank row */}
            <button type="button"
              className="mt-2 font-mono text-[11px] tracking-[0.08em]"
              style={{ color: 'var(--sv-cyan)', background: 'none', border: 'none', cursor: 'pointer' }}
              onClick={() => setNewElection({ ...newElection, candidates: [...newElection.candidates, { name: '', party: '' }] })}>
              + Add candidate
            </button>
          </div>
          {/* Error banner inside the modal — shown for validation failures or API errors */}
          {modalError && (
            <div className="sv-alert-error">
              {modalError}
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={() => { setShowCreateModal(false); setModalError(''); }} className="sv-btn-outline flex-1">Cancel</button>
            {/* Submit disabled until at least 2 named candidates exist */}
            <button type="submit"
              disabled={newElection.candidates.filter(c => c.name.trim()).length < 2}
              className="sv-btn-primary flex-1">
              Create Election
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal — only allows changing the title and description of a draft election */}
      <Modal show={showEditModal && !!selectedElection} onClose={() => setShowEditModal(false)} title="Edit Election">
        {selectedElection && (
          <form onSubmit={handleUpdate} className="space-y-5">
            <div>
              <label className="sv-label">Title</label>
              <input type="text" className="sv-input-box"
                value={selectedElection.title} required
                onChange={(e) => setSelectedElection({ ...selectedElection, title: e.target.value })} />
            </div>
            <div>
              <label className="sv-label">Description</label>
              <textarea className="sv-input-box resize-none" rows={3}
                value={selectedElection.description || ''}
                onChange={(e) => setSelectedElection({ ...selectedElection, description: e.target.value })} />
            </div>
            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => setShowEditModal(false)} className="sv-btn-outline flex-1">Cancel</button>
              <button type="submit" className="sv-btn-primary flex-1">Save Changes</button>
            </div>
          </form>
        )}
      </Modal>

      {/* Candidates Modal — add or remove candidates from a draft election */}
      <Modal
        show={showCandidateModal && !!selectedElection}
        onClose={() => { setShowCandidateModal(false); setNewCandidate({ name: '', description: '' }); }}
        title={`Candidates — ${selectedElection?.title || ''}`}
      >
        {selectedElection && (
          <div>
            {/* Inline add form at the top of the modal */}
            <form onSubmit={handleAddCandidate} className="flex gap-2 mb-6">
              <input type="text" className="sv-input-box flex-1" placeholder="Name" value={newCandidate.name}
                onChange={(e) => setNewCandidate({ ...newCandidate, name: e.target.value })} required />
              <input type="text" className="sv-input-box flex-1" placeholder="Description (optional)" value={newCandidate.description}
                onChange={(e) => setNewCandidate({ ...newCandidate, description: e.target.value })} />
              <button type="submit" className="sv-btn-primary shrink-0" style={{ padding: '10px 16px' }}>Add</button>
            </form>

            <p className="sv-label mb-3">
              Current Candidates ({selectedElection.candidates?.length || 0})
            </p>
            {/* Empty state or scrollable list of existing candidates */}
            {!selectedElection.candidates || selectedElection.candidates.length === 0 ? (
              <p className="text-sm italic" style={{ color: 'var(--sv-text-muted)' }}>
                No candidates yet. Add at least 2 to start the election.
              </p>
            ) : (
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {selectedElection.candidates.map((candidate, i) => (
                  <div key={candidate.id ?? i}
                       className="flex items-center justify-between p-3"
                       style={{ border: '1px solid var(--sv-border)', borderRadius: 2,
                                background: 'rgba(228,235,248,0.02)' }}>
                    <div>
                      <p className="font-display font-semibold text-sm text-white">{candidate.name}</p>
                      {candidate.description && (
                        <p className="text-xs mt-0.5" style={{ color: 'var(--sv-text-muted)' }}>
                          {candidate.description}
                        </p>
                      )}
                    </div>
                    {/* REMOVE button fires a confirmation dialog before calling the API */}
                    <button
                      onClick={() => handleRemoveCandidate(candidate.id)}
                      className="font-mono text-[10px] ml-3 shrink-0 transition-colors"
                      style={{ color: 'var(--sv-magenta)', background: 'none', border: 'none', cursor: 'pointer',
                               letterSpacing: '0.08em' }}>
                      REMOVE
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-6">
              <button
                onClick={() => { setShowCandidateModal(false); setNewCandidate({ name: '', description: '' }); }}
                className="sv-btn-outline w-full">
                Close
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ElectionManagement;
