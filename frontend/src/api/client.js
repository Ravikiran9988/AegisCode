/**
 * Fixsembly API Client
 * Centralized fetch wrapper handling JWT authentication, guest identity and errors.
 */

const configuredBackendUrl = (
  import.meta.env.VITE_BACKEND_URL ||
  import.meta.env.VITE_API_URL ||
  ''
).trim().replace(/\/+$/, '');

const BASE_URL = configuredBackendUrl
  ? (/^https?:\/\//i.test(configuredBackendUrl)
      ? configuredBackendUrl
      : 'https://' + configuredBackendUrl)
  : '';

export function getApiBaseUrl() {
  return BASE_URL;
}

export function getAuthHeaders() {
  const headers = {};
  const token = localStorage.getItem('fixsembly_auth_token');
  if (token) headers.Authorization = 'Bearer ' + token;

  const guestSessionId = localStorage.getItem('fixsembly_guest_session_id');
  const guestName = localStorage.getItem('fixsembly_guest_name');
  if (guestSessionId) headers['X-Guest-Session-ID'] = guestSessionId;
  if (guestName) headers['X-Guest-Name'] = guestName;

  return headers;
}

export async function apiRequest(endpoint, options = {}) {
  const url = BASE_URL + endpoint;
  const headers = {
    ...getAuthHeaders(),
    ...(options.headers || {}),
  };

  // Let the browser set the multipart boundary for FormData uploads.
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const response = await fetch(url, { ...options, headers });

    if (response.status === 204) return null;

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/zip') || contentType.includes('application/octet-stream')) {
      if (!response.ok) {
        const error = new Error('Download failed with status ' + response.status);
        error.status = response.status;
        throw error;
      }
      return response.blob();
    }

    const isJson = contentType.includes('application/json') || contentType.includes('+json');
    if (!isJson) {
      throw new Error(
        'The API returned a non-JSON response. Check that VITE_BACKEND_URL points to the Fixsembly API service.'
      );
    }

    const data = await response.json();
    if (!response.ok) {
      const errorMessage = data.detail || data.message || ('Request failed with status ' + response.status);
      const error = new Error(
        typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage)
      );
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (err) {
    console.error('[API Error] ' + (options.method || 'GET') + ' ' + endpoint + ':', err);
    throw err;
  }
}
