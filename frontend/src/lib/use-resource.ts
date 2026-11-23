"use client";
import { useCallback, useEffect, useState } from "react";
/** Loader must be memoized. Abort and request identity prevent outdated data flashing after filter changes. */
export function useResource<T>(
  loader: ((signal: AbortSignal) => Promise<T>) | null,
  refreshIntervalMs?: number,
) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    loader: typeof loader;
    revision: number;
    data?: T;
    error?: Error;
  }>({ loader: null, revision: -1 });
  useEffect(() => {
    if (!loader) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const data = await loader(controller.signal);
        if (!controller.signal.aborted) setState({ loader, revision, data });
      } catch (error) {
        if (!controller.signal.aborted)
          setState({
            loader,
            revision,
            error:
              error instanceof Error
                ? error
                : new Error("Unable to load data."),
          });
      } finally {
        if (!controller.signal.aborted && refreshIntervalMs)
          timer = setTimeout(refresh, refreshIntervalMs);
      }
    };
    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [loader, revision, refreshIntervalMs]);
  const current = state.loader === loader && state.revision === revision;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: Boolean(loader && (!current || (!state.data && !state.error))),
    retry: useCallback(() => setRevision((n) => n + 1), []),
  };
}
