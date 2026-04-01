import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:5001';

// Create an axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add JWT token to headers
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle 401 errors (token expired/invalid)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Don't redirect if on login/register pages
      const path = window.location.pathname;
      if (path !== '/' && path !== '/register') {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('studentId');
        window.location.href = '/';
      }
    }
    return Promise.reject(error);
  }
);

// ============================================================================
// Authentication API
// ============================================================================

export const login = async (studentId, password) => {
  try {
    const payload = { student_id: studentId };
    if (password) {
      payload.password = password;
    }
    const response = await apiClient.post('/auth/login', payload);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const register = async (studentId, password, email, programme) => {
  try {
    const payload = { student_id: studentId, password, programme };
    if (email) payload.email = email;
    const response = await apiClient.post('/auth/register', payload);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchProgrammes = async () => {
  try {
    const response = await apiClient.get('/programmes');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const getCurrentUser = async () => {
  try {
    const response = await apiClient.get('/auth/me');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const changePassword = async (currentPassword, newPassword) => {
  try {
    const response = await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const setPassword = async (password) => {
  try {
    const response = await apiClient.post('/auth/set-password', { password });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const getPasswordRequirements = async () => {
  try {
    const response = await apiClient.get('/auth/password-requirements');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

// ============================================================================
// Elections API
// ============================================================================

export const fetchElections = async (status = null) => {
  try {
    const params = status ? { status } : {};
    const response = await apiClient.get('/elections', { params });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchElection = async (electionId) => {
  try {
    const response = await apiClient.get(`/elections/${electionId}`);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const createElection = async (electionData) => {
  try {
    const response = await apiClient.post('/elections', electionData);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const updateElection = async (electionId, electionData) => {
  try {
    const response = await apiClient.put(`/elections/${electionId}`, electionData);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const deleteElection = async (electionId) => {
  try {
    const response = await apiClient.delete(`/elections/${electionId}`);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const startElection = async (electionId) => {
  try {
    const response = await apiClient.post(`/elections/${electionId}/start`);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const endElection = async (electionId) => {
  try {
    const response = await apiClient.post(`/elections/${electionId}/end`);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchElectionResults = async (electionId) => {
  try {
    const response = await apiClient.get(`/elections/${electionId}/results`);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const addCandidate = async (electionId, candidateData) => {
  try {
    const response = await apiClient.post(`/elections/${electionId}/candidates`, candidateData);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const removeCandidate = async (electionId, candidateId) => {
  try {
    const response = await apiClient.delete(`/elections/${electionId}/candidates/${candidateId}`);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

// ============================================================================
// Voting API
// ============================================================================

export const fetchCandidates = async () => {
  try {
    const response = await apiClient.get('/candidates');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const castVote = async (candidateId, electionId = null) => {
  try {
    const payload = { candidate_id: candidateId };
    if (electionId) {
      payload.election_id = electionId;
    }
    const response = await apiClient.post('/vote', payload);
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchResults = async (electionId = null) => {
  try {
    const params = electionId ? { election_id: electionId } : {};
    const response = await apiClient.get('/results', { params });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

// ============================================================================
// Admin API
// ============================================================================

export const fetchUsers = async () => {
  try {
    const response = await apiClient.get('/admin/users');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const createUser = async (studentId, role) => {
  try {
    const response = await apiClient.post('/admin/users', {
      student_id: studentId,
      role
    });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const updateUserRole = async (studentId, role) => {
  try {
    const response = await apiClient.put(`/admin/users/${studentId}/role`, { role });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

// ============================================================================
// WebAuthn API
// ============================================================================

export const webAuthnRegisterBegin = async () => {
  try {
    const response = await apiClient.post('/auth/webauthn/register/begin');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const webAuthnRegisterComplete = async (registrationResp) => {
  try {
    const response = await apiClient.post('/auth/webauthn/register/complete', registrationResp, {
      headers: { 'Content-Type': 'application/json' },
    });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const webAuthnLoginBegin = async (studentId) => {
  try {
    const response = await apiClient.post('/auth/webauthn/login/begin', { student_id: studentId });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const webAuthnLoginComplete = async (studentId, assertion) => {
  try {
    const response = await apiClient.post('/auth/webauthn/login/complete', {
      student_id: studentId,
      assertion,
    });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

// ============================================================================
// Audit API
// ============================================================================

export const verifyChain = async (electionId = null) => {
  try {
    const params = electionId ? { election_id: electionId } : {};
    const response = await apiClient.get('/audit/verify', { params });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchAuditStats = async (electionId = null) => {
  try {
    const params = electionId ? { election_id: electionId } : {};
    const response = await apiClient.get('/audit/stats', { params });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export default apiClient;
