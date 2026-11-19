import { apiRequest } from './client';

export async function createRun(projectId, maxIterations = 5) {
  return apiRequest('/api/runs', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      max_iterations: maxIterations,
    }),
  });
}

export async function startRepair(runId) {
  return apiRequest(`/api/runs/${runId}/repair`, {
    method: 'POST',
  });
}

export async function cancelRun(runId) {
  return apiRequest(`/api/runs/${runId}/cancel`, {
    method: 'POST',
  });
}

export async function getRunStatus(runId) {
  return apiRequest(`/api/runs/${runId}/status`);
}

export async function getRunResults(runId) {
  return apiRequest(`/api/runs/${runId}/results`);
}

export async function downloadRunZip(runId) {
  return apiRequest(`/api/runs/${runId}/download`);
}

export async function listRuns(limit = 50, offset = 0) {
  return apiRequest(`/api/runs?limit=${limit}&offset=${offset}`);
}

export async function listActiveRuns() {
  return apiRequest('/api/runs/active');
}

export async function listHistoryRuns(status = null, limit = 50, offset = 0) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) params.set('status', status);
  return apiRequest(`/api/runs/history?${params.toString()}`);
}
