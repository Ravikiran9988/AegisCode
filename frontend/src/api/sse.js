import { useState, useEffect, useRef, useCallback } from 'react';
import { getAuthHeaders, getApiBaseUrl } from './client';
import { getRunStatus } from './runs';

const TERMINAL_STATUSES = new Set([
  'passed',
  'already_passing',
  'failed',
  'stalled',
  'error',
  'cancelled',
  'partially_repaired',
  'reviewer_rejected',
  'test_error',
  'timeout',
]);

/**
 * Authenticated SSE stream for repair runs.
 *
 * Fetch + ReadableStream is used instead of EventSource because EventSource
 * cannot attach the JWT and guest-session headers required by the API.
 * REST polling remains the fallback when streaming is unavailable.
 */
export function useRunStream(runId, { enabled = true, onComplete = null } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (!runId || !enabled) return undefined;

    const controller = new AbortController();
    let stopped = false;
    let finished = false;
    let pollingTimer = null;

    setIsStreaming(true);
    setError(null);

    const finish = (finalData) => {
      if (stopped || finished) return;
      finished = true;
      setData(finalData);
      setIsStreaming(false);
      if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
      }
      onCompleteRef.current?.(finalData);
    };

    const applyStatus = (payload) => {
      setData(payload);
      if (TERMINAL_STATUSES.has(payload?.status)) finish(payload);
    };

    const pollOnce = async () => {
      try {
        const snapshot = await getRunStatus(runId);
        if (!stopped) applyStatus(snapshot);
      } catch (err) {
        if (!stopped) setError(err.message || 'Unable to refresh repair status.');
      }
    };

    const startPollingFallback = () => {
      if (stopped || finished || pollingTimer) return;
      setIsStreaming(true);
      pollOnce();
      pollingTimer = setInterval(pollOnce, 2000);
    };

    const processFrame = async (frame) => {
      let eventName = 'message';
      const dataLines = [];

      for (const line of frame.split('\n')) {
        if (!line || line.startsWith(':')) continue;
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
      }

      if (!dataLines.length) return;
      const rawData = dataLines.join('\n');

      if (eventName === 'error') {
        let message = 'Repair stream returned an error.';
        try {
          message = JSON.parse(rawData).error || message;
        } catch {
          // Keep the safe fallback message for malformed server events.
        }
        throw new Error(message);
      }

      if (eventName === 'complete') {
        const finalSnapshot = await getRunStatus(runId);
        finish(finalSnapshot);
        return;
      }

      if (eventName === 'status' || eventName === 'message') {
        applyStatus(JSON.parse(rawData));
      }
    };

    const connect = async () => {
      try {
        const response = await fetch(
          `${getApiBaseUrl()}/api/runs/${encodeURIComponent(runId)}/stream`,
          {
            method: 'GET',
            headers: {
              ...getAuthHeaders(),
              Accept: 'text/event-stream',
            },
            cache: 'no-store',
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`Repair stream request failed (${response.status}).`);
        }
        if (!response.body) {
          throw new Error('Streaming is not supported by this browser connection.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!stopped && !finished) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
          let boundary = buffer.indexOf('\n\n');

          while (boundary !== -1 && !stopped && !finished) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            await processFrame(frame);
            boundary = buffer.indexOf('\n\n');
          }
        }

        if (!stopped && !finished) {
          startPollingFallback();
        }
      } catch (err) {
        if (!stopped && err.name !== 'AbortError') {
          setError(err.message || 'Live updates disconnected; switching to polling.');
          startPollingFallback();
        }
      }
    };

    connect();

    return () => {
      stopped = true;
      controller.abort();
      if (pollingTimer) clearInterval(pollingTimer);
    };
  }, [runId, enabled]);

  const refresh = useCallback(async () => {
    const snapshot = await getRunStatus(runId);
    setData(snapshot);
    return snapshot;
  }, [runId]);

  return { data, error, isStreaming, refresh };
}
