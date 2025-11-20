import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:5001';

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
      // Clear invalid token and redirect to login
      localStorage.removeItem('token');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

// API Functions
export const login = async (studentId) => {
  try {
    const response = await apiClient.post('/auth/login', { student_id: studentId });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchCandidates = async () => {
  try {
    const response = await apiClient.get('/candidates');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const castVote = async (candidateId) => {
  try {
    const response = await apiClient.post('/vote', { candidate_id: candidateId });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export const fetchResults = async () => {
  try {
    const response = await apiClient.get('/results');
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error.message;
  }
};

export default apiClient;

