import { useState, useEffect, useRef } from 'react';
import { getAuthHeaders } from './client';
import { getRunStatus } from './runs';

/**
 * Custom React hook connecting to Fixsembly Server-Sent Events (SSE)
 * with automatic fallback to REST polling if SSE is disconnected or unsupported.
 */
export function useRunStream(runId, { enabled = true, onComplete = null } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  useEffect(() => {
    if (!runId || !enabled) {
      return;
    }

    setIsStreaming(true);
    setError(null);

    // Terminal statuses: stream closes and onComplete fires when any of these is received
    const TERMINAL_STATUSES = [
      'passed', 'already_passing', 'failed', 'stalled', 'error', 'cancelled',
      'partially_repaired', 'reviewer_rejected', 'test_error', 'timeout',
    ];

    // Initial snapshot fetch
    getRunStatus(runId)
      .then((initialData) => {
        setData(initialData);
        if (TERMINAL_STATUSES.includes(initialData.status)) {
          setIsStreaming(false);
          if (onComplete) onComplete(initialData);
        }
      })
      .catch((err) => {
        console.warn('[SSE] Initial status check failed, falling back to stream:', err);
      });

    // Setup Server-Sent Events
    const base = import.meta.env.VITE_BACKEND_URL || '';
    const streamUrl = `${base}/api/runs/${encodeURIComponent(runId)}/stream`;

    try {
      const eventSource = new EventSource(streamUrl);
      eventSourceRef.current = eventSource;

      eventSource.addEventListener('status', (e) => {
        try {
          const payload = JSON.parse(e.data);
          setData(payload);

          if (TERMINAL_STATUSES.includes(payload.status)) {
            setIsStreaming(false);
            eventSource.close();
            if (onComplete) onComplete(payload);
          }
        } catch (err) {
          console.error('[SSE] Failed to parse status payload:', err);
        }
      });

      eventSource.addEventListener('complete', (e) => {
        setIsStreaming(false);
        eventSource.close();
        getRunStatus(runId).then((final) => {
          setData(final);
          if (onComplete) onComplete(final);
        });
      });

      eventSource.addEventListener('error', (e) => {
        console.warn('[SSE] SSE connection error, switching to polling fallback');
        eventSource.close();
        startPollingFallback();
      });
    } catch (err) {
      console.warn('[SSE] Failed to instantiate EventSource, using polling:', err);
      startPollingFallback();
    }

    function startPollingFallback() {
      if (pollingIntervalRef.current) return;

      pollingIntervalRef.current = setInterval(async () => {
        try {
          const status = await getRunStatus(runId);
          setData(status);

          if (TERMINAL_STATUSES.includes(status.status)) {
            clearInterval(pollingIntervalRef.current);
            setIsStreaming(false);
            if (onComplete) onComplete(status);
          }
        } catch (err) {
          setError(err.message);
        }
      }, 1500);
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      setIsStreaming(false);
    };
  }, [runId, enabled]);

  return { data, error, isStreaming, refresh: () => getRunStatus(runId).then(setData) };
}
