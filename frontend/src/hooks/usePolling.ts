import { useEffect, useState } from 'react';

/**
 * Generic polling hook to keep data in sync with the backend.
 */
export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number = 5000,
  enabled: boolean = true
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!enabled) return;

    let isMounted = true;

    const performFetch = async () => {
      try {
        const result = await fetchFn();
        if (isMounted) {
          setData(result);
          setError(null);
        }
      } catch (e) {
        if (isMounted) {
          setError(e instanceof Error ? e : new Error('Polling error'));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    // Initial fetch
    performFetch();

    const intervalId = setInterval(performFetch, intervalMs);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [fetchFn, intervalMs, enabled]);

  return { data, error, loading };
}
