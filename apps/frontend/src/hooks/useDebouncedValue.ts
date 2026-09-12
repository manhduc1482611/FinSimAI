"use client";

/**
 * useDebouncedValue — trả về giá trị đã "gác lại" sau `delayMs`
 * (dùng cho ô tìm kiếm: chỉ fetch khi user ngừng gõ).
 */
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}