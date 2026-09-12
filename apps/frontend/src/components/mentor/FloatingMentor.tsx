/**
 * FloatingMentor — widget chat nổi ở góc dưới bên phải.
 *
 * Nút FAB dạng tròn chứa trợ lý 3D capybara (idle animations); bấm mở panel
 * chat Mentor. Tự động mở khi có `focusRequest` (nút "Hỏi Mentor" trên trade
 * page). Đóng panel giúp giải phóng WebSocket — chỉ mount MentorChat khi mở.
 */
"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { MentorChat } from "@/components/mentor/MentorChat";
import { useMentorStore } from "@/store/useMentorStore";

const Capybara3D = dynamic(
  () => import("@/components/mentor/Capybara3D").then((m) => m.Capybara3D),
  {
    ssr: false,
    loading: () => <CapybaraFallback />,
  },
);

export function FloatingMentor() {
  const pathname = usePathname();
  const focusRequest = useMentorStore((state) => state.focusRequest);
  const isStreaming = useMentorStore((state) => state.isStreaming);
  const selectedSymbol = useMentorStore(
    (state) => state.tradeContext.selected_symbol,
  );

  const [open, setOpen] = useState(false);

  // Nút "Hỏi Mentor" ở trade page → tự mở panel.
  useEffect(() => {
    if (focusRequest > 0) {
      setOpen(true);
    }
  }, [focusRequest]);

  // Escape đóng panel.
  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Trang /trade/mentor đã là chat toàn màn hình — ẩn widget tránh 2 WebSocket.
  if (pathname?.startsWith("/trade/mentor")) {
    return null;
  }

  const toggle = () => {
    setOpen(!open);
  };

  return (
    <div className="fixed bottom-5 right-5 z-[60]">
      {open && (
        <div className="absolute bottom-0 right-full mr-3 flex h-[min(34rem,calc(100dvh-10rem))] w-[min(24rem,calc(100vw-11rem))] flex-col animate-pop-in overflow-hidden rounded-2xl border border-line bg-slip p-0 shadow-card dark:border-granite-700 dark:bg-granite-900">
<button
            type="button"
            onClick={toggle}
            aria-label="Đóng chat với Mentor"
            className="absolute -right-2.5 -top-2.5 z-10 flex h-8 w-8 items-center justify-center rounded-full border border-line bg-paper text-ink-600 shadow-card transition-colors hover:bg-ink-100 hover:text-ink-900 dark:border-granite-600 dark:bg-granite-800 dark:text-granite-300 dark:hover:text-slip"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
          <div className="min-h-0 flex-1">
            <MentorChat fixedSymbol={selectedSymbol} compact />
          </div>
        </div>
      )}

      <div className="group relative">
        <button
          type="button"
          onClick={toggle}
          aria-label={
            open ? "Đóng chat với Mentor tài chính" : "Mở chat với Mentor tài chính"
          }
          className="relative flex shrink-0 cursor-pointer items-center justify-center transition-transform duration-200 hover:scale-105 active:scale-95"
          style={{ background: "transparent", width: 112, height: 112 }}
        >
          <Capybara3D excited={isStreaming} />
        </button>
      </div>
    </div>
  );
}

/** SVG capybara dạng mặt — fallback nhẹ trong lúc 3D đang tải. */
function CapybaraFallback() {
  return (
    <svg viewBox="0 0 120 120" className="h-3/5 w-3/5" aria-hidden="true">
      <circle cx="28" cy="30" r="13" fill="#7C5126" />
      <circle cx="92" cy="30" r="13" fill="#7C5126" />
      <ellipse cx="35" cy="24" rx="7" ry="8" fill="#5C3A1C" />
      <ellipse cx="85" cy="24" rx="7" ry="8" fill="#5C3A1C" />
      <circle cx="60" cy="62" r="44" fill="#9A6B3F" />
      <ellipse cx="60" cy="76" rx="24" ry="15" fill="#CBA57E" />
      <ellipse cx="48" cy="58" rx="5.5" ry="7" fill="#2E1F12" />
      <ellipse cx="72" cy="58" rx="5.5" ry="7" fill="#2E1F12" />
      <circle cx="49.5" cy="55.5" r="2" fill="#FFFFFF" />
      <circle cx="73.5" cy="55.5" r="2" fill="#FFFFFF" />
      <ellipse cx="60" cy="38" rx="10" ry="4" fill="#7C5126" />
      <path d="M48 84 Q60 92 72 84" stroke="#5C3A1C" strokeWidth="3" strokeLinecap="round" fill="none" />
    </svg>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}