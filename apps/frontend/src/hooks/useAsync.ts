/**
 * useAsync — trạng thái dữ liệu bất đồng bộ chuẩn (data/loading/error/reload)
 * dùng chung cho các trang tải từ API.
 */
import { useCallback, useEffect, useState, type DependencyList } from "react";

import { toRequestError } from "@/services/api";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** Gọi lại để fetch lại (sau mutation). */
  reload: () => void;
}

export function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: DependencyList = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (active) {
          setData(result);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(toRequestError(err).detail);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);

  return { data, loading, error, reload };
}
