const BASE = '';

function getToken() {
  return localStorage.getItem('token');
}

export async function api(path, options = {}) {
  const headers = { ...options.headers };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.hash = '#/login';
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// Auth
export const register = (email, password) => api('/api/auth/register', { method: 'POST', body: { email, password } });
export const login = (email, password) => api('/api/auth/login', { method: 'POST', body: { email, password } });
export const getMe = () => api('/api/auth/me');

export function logout() {
  localStorage.removeItem('token');
  window.location.hash = '#/login';
}

// Session
export const createSession = (data) => api('/api/sessions', { method: 'POST', body: data });
export const getSession = (id) => api(`/api/sessions/${id}`);
export const updateBackground = (id, bg) => api(`/api/sessions/${id}/background`, { method: 'PUT', body: { background: bg } });
export const addGoal = (id, topic, depth) => api(`/api/sessions/${id}/goals`, { method: 'POST', body: { topic, depth } });
export const removeGoal = (id, idx) => api(`/api/sessions/${id}/goals/${idx}`, { method: 'DELETE' });

// Gathering
export const startGathering = (data) => api('/api/gathering/start', { method: 'POST', body: data });
export const getGatheringStatus = (taskId, sessionId) => api(`/api/gathering/status/${taskId}?session_id=${sessionId}`);
export const getGatheringResults = (taskId, sessionId) => api(`/api/gathering/results/${taskId}?session_id=${sessionId}`);

// Curriculum
export const generateCurriculum = (data) => api('/api/curriculum/generate', { method: 'POST', body: data });
export const getCurriculum = (id, sessionId) => api(`/api/curriculum/${id}?session_id=${sessionId}`);
export const addCurriculumItem = (currId, data) => api(`/api/curriculum/${currId}/items`, { method: 'POST', body: data });
export const updateCurriculumItem = (currId, itemId, sessionId, data) => api(`/api/curriculum/${currId}/items/${itemId}?session_id=${sessionId}`, { method: 'PUT', body: data });
export const deleteCurriculumItem = (currId, itemId, sessionId) => api(`/api/curriculum/${currId}/items/${itemId}?session_id=${sessionId}`, { method: 'DELETE' });

// Materials
export const uploadPdf = (formData) => api('/api/materials/upload', { method: 'POST', body: formData });
export const listPdfs = (sessionId) => api(`/api/materials/pdfs/${sessionId}`);
export const addManualMaterial = (data) => api('/api/materials/manual', { method: 'POST', body: data });
export const deleteMaterial = (sessionId, materialId) => api(`/api/materials/${sessionId}/${materialId}`, { method: 'DELETE' });

// OpenStax
export const listOpenStaxBooks = () => api('/api/openstax/books');
export const uploadOpenStaxBook = (formData) => api('/api/openstax/upload', { method: 'POST', body: formData });
export const deleteOpenStaxBook = (bookId) => api(`/api/openstax/books/${bookId}`, { method: 'DELETE' });
export const reindexOpenStaxBook = (bookId) => api(`/api/openstax/books/${bookId}/reindex`, { method: 'POST' });
