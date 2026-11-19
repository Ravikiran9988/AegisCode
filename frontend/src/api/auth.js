import { apiRequest } from './client';

export async function loginUser(email, password) {
  return apiRequest('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function registerUser({ email, password, confirmPassword, nickname }) {
  return apiRequest('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
      confirm_password: confirmPassword,
      nickname,
    }),
  });
}

export async function getCurrentUser() {
  return apiRequest('/api/auth/me');
}

export async function persistGuestIdentity(name, sessionId) {
  return apiRequest('/api/guests', {
    method: 'POST',
    body: JSON.stringify({
      name,
      session_id: sessionId,
    }),
  });
}

export async function getSystemHealth() {
  return apiRequest('/health');
}
