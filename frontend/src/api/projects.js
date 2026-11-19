import { apiRequest } from './client';

export async function uploadProject(file) {
  const formData = new FormData();
  formData.append('file', file);

  return apiRequest('/api/projects/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function loadDemoProject() {
  return apiRequest('/api/projects/demo', {
    method: 'POST',
  });
}

