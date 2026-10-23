/**
 * Mentor — hỏi đáp tài chính qua Mentor (3 chế độ v2.0).
 */
"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { IconLock } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { MentorChat } from "@/components/mentor/MentorChat";
import { useAuthStore } from "@/store/useAuthStore";
import { cn } from "@/utils/cn";
import type { MentorMode } from "@/types/websocket";

const MODES: { id: MentorMode; label: string; description: string }[] = [
  {
    id: "concept",
    label: "Hỏi đáp khái niệm",
    description: "Giải thích thuật ngữ tài chính có cấu trúc kèm ví dụ.",
  },
  {
    id: "plan",
    label: "Đề xuất hướng đầu tư",
    description: "Gợi ý khung chiến lược theo mục tiêu và mức rủi ro.",
  },
  {
    id: "trade_now",
    label: "Phản biện khi giao dịch",
    description: "Phản biện quyết định mua/bán dựa trên danh mục thực tế.",
  },
];

function MentorPageContent() {
  const token = useAuthStore((state) => state.token);
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const rawMode = searchParams.get("mode");
  const [mode, setMode] = useState<MentorMode>(
    rawMode === "concept" || rawMode === "plan" || rawMode === "trade_now"
      ? rawMode
      : "concept",
  );

  return (
    <div>
      <PageHeader
        title="Capia — AI Mentor tài chính"
        description="Đồng hành cùng linh vật Capybara phản biện Socratic — rèn luyện bản lĩnh và tư duy đầu tư kỷ luật."
      />
      <div className="mb-4 flex flex-wrap gap-2">
        {MODES.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setMode(item.id);
              // Giữ query param mode để reload vẫn giữ đúng chế độ đang chọn.
              const params = new URLSearchParams(searchParams.toString());
              params.set("mode", item.id);
              window.history.replaceState(null, "", `${pathname}?${params.toString()}`);
            }}
            className={cn(
              "group rounded-xl border px-4 py-3 text-left transition-all",
              mode === item.id
                ? "border-accent-500 bg-accent-500/10 shadow-sm ring-1 ring-accent-500/30"
                : "border-line bg-paper hover:border-ink-300 dark:border-granite-700 dark:bg-granite-900 dark:hover:border-granite-600",
            )}
            aria-pressed={mode === item.id}
          >
            <span className="block text-sm font-semibold text-ink-800 dark:text-slip">
              {item.label}
            </span>
            <span className="mt-0.5 block text-xs text-ink-500 dark:text-granite-400">
              {item.description}
            </span>
          </button>
        ))}
      </div>
      {!token ? (
        <div className="rounded-2xl border border-line bg-paper p-8 text-center shadow-card dark:border-granite-700 dark:bg-granite-900">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-accent-500/30 bg-accent-500/10 text-accent-600 dark:text-accent-400">
            <IconLock className="h-7 w-7" />
          </div>

          <h3 className="mt-4 text-lg font-black text-ink-900 dark:text-slip">
            AI Mentor Socratic yêu cầu đăng nhập
          </h3>

          <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-ink-500 dark:text-granite-400">
            Trợ lý AI Mentor Socratic cần kết nối tài khoản để phân tích danh mục, lưu trữ lịch sử hội thoại và phản biện các quyết định đầu tư của bạn theo thời gian thực. Hãy đăng nhập để bắt đầu trò chuyện cùng linh vật Capybara!
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/login" className="btn-primary px-6 py-2.5 text-sm">
              Đăng nhập ngay
            </Link>
            <Link href="/register" className="btn-secondary px-6 py-2.5 text-sm">
              Tạo tài khoản miễn phí
            </Link>
          </div>
        </div>
      ) : (
        <MentorChat initialMode={mode} key={mode} />
      )}
    </div>
  );
}

export default function MentorPage() {
  return (
    <Suspense fallback={null}>
      <MentorPageContent />
    </Suspense>
  );
}