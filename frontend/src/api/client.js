/**
 * Fixsembly API Client
 * Centralized fetch wrapper handling JWT authentication, Guest headers, and unified error handling.
 */

const BASE_URL = import.meta.env.VITE_BACKEND_URL || '';

export function getAuthHeaders() {
  const headers = {};
  const token = localStorage.getItem('fixsembly_auth_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const guestSessionId = localStorage.getItem('fixsembly_guest_session_id');
  const guestName = localStorage.getItem('fixsembly_guest_name');
  if (guestSessionId) {
    headers['X-Guest-Session-ID'] = guestSessionId;
  }
  if (guestName) {
    headers['X-Guest-Name'] = guestName;
  }

  return headers;
}

export async function apiRequest(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    ...getAuthHeaders(),
    ...(options.headers || {}),
  };

  // Don't set Content-Type for FormData (browser sets boundary)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);

    if (response.status === 204) {
      return null;
    }

    // For file downloads (ZIP)
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/zip') || contentType.includes('application/octet-stream')) {
      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}`);
      }
      return response.blob();
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data.detail || data.message || `Request failed with status ${response.status}`;
      const error = new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (err) {
    console.error(`[API Error] ${options.method || 'GET'} ${endpoint}:`, err);
    throw err;
  }
}
