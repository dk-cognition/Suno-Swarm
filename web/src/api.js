const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/** Access tokens are kept in localStorage so the embedded player can reuse them. */
export function setToken(token) {
  window.localStorage.setItem('swarm.access_token', token);
}

export function getToken() {
  return window.localStorage.getItem('swarm.access_token') || '';
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  login: (email, password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request('/users/me'),
  submitPrompt: (prompt) =>
    request('/prompts', { method: 'POST', body: JSON.stringify(prompt) }),
  job: (jobId) => request(`/prompts/jobs/${jobId}`),
  tracks: () => request('/tracks'),
  search: (q) => request(`/tracks/search?q=${encodeURIComponent(q)}`),
  track: (id) => request(`/tracks/${id}`),
  renameTrack: (id, title) =>
    request(`/tracks/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  downloadUrl: (id) =>
    `${API_BASE}/tracks/${id}/download?token=${encodeURIComponent(getToken())}`,
};
