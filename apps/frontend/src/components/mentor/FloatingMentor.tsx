/**
 * FloatingMentor — widget chat nổi ở góc dưới bên phải.
 *
 * Nút FAB dạng tròn chứa trợ lý 3D capybara (idle animations); bấm mở panel
 * chat Mentor. Tự động mở khi có `focusRequest` (nút "Hỏi Mentor" trên trade
 * page). Đóng panel giúp giải phóng WebSocket — chỉ mount MentorChat khi mở.
 */
"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { IconLock, IconMentor } from "@/components/common/Icon";
import { MentorChat } from "@/components/mentor/MentorChat";
import { useAuthStore } from "@/store/useAuthStore";
import { useMentorStore } from "@/store/useMentorStore";
import { cn } from "@/utils/cn";

const Capybara3D = dynamic(
  () => import("@/components/mentor/Capybara3D").then((m) => m.Capybara3D),
  {
    ssr: false,
    loading: () => <CapybaraFallback />,
  },
);

export function FloatingMentor() {
  const token = useAuthStore((state) => state.token);
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
            {!token ? (
              <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-accent-500/30 bg-accent-500/10 text-accent-600 dark:text-accent-400">
                  <IconMentor className="h-7 w-7" />
                </div>
                <h3 className="mt-3 text-base font-black text-ink-900 dark:text-slip">
                  Chào bạn, tôi là AI Mentor!
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-ink-500 dark:text-granite-300">
                  Tôi là trợ lý Socratic của Capia, giúp bạn rèn luyện tư duy đầu tư qua các câu hỏi phản biện. Để trò chuyện cùng tôi, vui lòng đăng nhập tài khoản nhé!
                </p>
                <div className="mt-5 flex w-full flex-col gap-2">
                  <Link
                    href="/login"
                    className="btn-primary w-full py-2 text-center text-xs font-bold"
                    onClick={() => setOpen(false)}
                  >
                    Đăng nhập ngay
                  </Link>
                  <Link
                    href="/register"
                    className="btn-secondary w-full py-2 text-center text-xs font-semibold"
                    onClick={() => setOpen(false)}
                  >
                    Tạo tài khoản miễn phí
                  </Link>
                </div>
              </div>
            ) : (
              <MentorChat fixedSymbol={selectedSymbol} compact />
            )}
          </div>
        </div>
      )}

      <div className="group relative">
        {/* Bong bóng gợi ý xinh xắn khi hover hoặc khi AI đang suy nghĩ */}
        <div
          className={cn(
            "pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded-full border border-line bg-paper/95 px-3 py-1 text-xs font-semibold text-ink-800 shadow-md backdrop-blur-sm transition-all duration-300 dark:border-granite-700 dark:bg-granite-900/95 dark:text-slip",
            isStreaming
              ? "opacity-100 scale-100 translate-y-0 text-accent-600 dark:text-accent-400"
              : "opacity-0 scale-95 translate-y-1 group-hover:opacity-100 group-hover:scale-100 group-hover:translate-y-0",
          )}
        >
          {!token ? (
            <span className="flex items-center gap-1.5 text-amber-700 dark:text-amber-300">
              <IconLock className="h-3 w-3" />
              AI Mentor (Cần đăng nhập)
            </span>
          ) : isStreaming ? (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 animate-ping rounded-full bg-accent-500" />
              Đang trả lời...
            </span>
          ) : open ? (
            "Thu nhỏ Mentor"
          ) : (
            "Hỏi Capia ✨"
          )}
        </div>

        <button
          type="button"
          onClick={toggle}
          aria-label={
            open ? "Đóng chat với Mentor tài chính" : "Mở chat với Mentor tài chính"
          }
          className="relative flex shrink-0 cursor-pointer items-center justify-center transition-transform duration-200 hover:scale-105 active:scale-95"
          style={{ background: "transparent", width: 116, height: 116 }}
        >
          <Capybara3D excited={isStreaming} />
        </button>
      </div>
    </div>
  );
}

/** SVG Capybara Chibi đứng 2 chân — fallback siêu cute nhẹ nhàng trong lúc 3D tải */
function CapybaraFallback() {
  return (
    <svg viewBox="0 0 120 130" className="h-4/5 w-4/5 drop-shadow-sm" aria-hidden="true">
      {/* Bóng tiếp đất */}
      <ellipse cx="60" cy="122" rx="30" ry="5" fill="#3D2614" opacity="0.18" />

      {/* Hai bàn chân đứng thẳng */}
      <rect x="36" y="112" width="16" height="10" rx="5" fill="#8A5428" />
      <rect x="68" y="112" width="16" height="10" rx="5" fill="#8A5428" />

      {/* Thân béo tròn */}
      <ellipse cx="60" cy="88" rx="27" ry="25" fill="#C88746" />
      {/* Bụng sữa kem */}
      <ellipse cx="60" cy="90" rx="18" ry="17" fill="#FDF1DC" />

      {/* Đồng tiền vàng FinSimAI */}
      <circle cx="60" cy="88" r="9" fill="#FFC107" stroke="#FFA000" strokeWidth="1.2" />
      <circle cx="60" cy="88" r="6.2" fill="#FFE082" />
      <circle cx="60" cy="88" r="2" fill="#FFFFFF" />

      {/* Hai tay ngắn ôm đồng xu */}
      <circle cx="48" cy="88" r="5.5" fill="#8A5428" />
      <circle cx="72" cy="88" r="5.5" fill="#8A5428" />

      {/* Hai tai tròn */}
      <ellipse cx="36" cy="38" rx="7" ry="8" fill="#8A5428" />
      <ellipse cx="36" cy="38" rx="4" ry="5" fill="#F2A79D" />
      <ellipse cx="84" cy="38" rx="7" ry="8" fill="#8A5428" />
      <ellipse cx="84" cy="38" rx="4" ry="5" fill="#F2A79D" />

      {/* Đầu sọ vuông tròn */}
      <rect x="34" y="32" width="52" height="42" rx="18" fill="#C88746" />
      {/* Má phúng phính */}
      <circle cx="36" cy="56" r="10" fill="#C88746" />
      <circle cx="84" cy="56" r="10" fill="#C88746" />
      {/* Má hồng đào */}
      <circle cx="38" cy="58" r="4.5" fill="#FFAAA6" opacity="0.9" />
      <circle cx="82" cy="58" r="4.5" fill="#FFAAA6" opacity="0.9" />

      {/* Mõm kem */}
      <rect x="42" y="48" width="36" height="24" rx="10" fill="#FDF1DC" />
      {/* Mũi hạt nút */}
      <rect x="53" y="49" width="14" height="8" rx="3.5" fill="#352014" />
      {/* Miệng cười chúm chím */}
      <path d="M57 63 Q60 66 63 63" stroke="#352014" strokeWidth="1.5" strokeLinecap="round" fill="none" />

      {/* Đôi mắt kawaii đen láy long lanh */}
      <ellipse cx="46" cy="46" rx="4.5" ry="5" fill="#1C140E" />
      <circle cx="44.5" cy="44.5" r="1.8" fill="#FFFFFF" />
      <circle cx="47" cy="47.5" r="0.8" fill="#FFFFFF" />

      <ellipse cx="74" cy="46" rx="4.5" ry="5" fill="#1C140E" />
      <circle cx="72.5" cy="44.5" r="1.8" fill="#FFFFFF" />
      <circle cx="75" cy="47.5" r="0.8" fill="#FFFFFF" />

      {/* Quả cam yuzu trên đầu */}
      <ellipse cx="60" cy="22" rx="11" ry="9.5" fill="#FF9500" />
      <line x1="60" y1="13" x2="60" y2="9" stroke="#5D4037" strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="65" cy="11" rx="4.5" ry="2" fill="#4CAF50" transform="rotate(20 65 11)" />
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