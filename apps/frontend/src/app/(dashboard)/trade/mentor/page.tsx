/**
 * Mentor — hỏi đáp tài chính qua Mentor (3 chế độ v2.0).
 */
"use client";

import { Suspense, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/common/PageHeader";
import { MentorChat } from "@/components/mentor/MentorChat";
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
        title="Mentor tài chính"
        description="Học cách tư duy như nhà đầu tư qua các câu hỏi gợi mở — không trao đáp án có sẵn."
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
            className="group rounded-xl border px-4 py-3 text-left transition-colors aria-checked:border-brand-500 aria-checked:bg-brand-500/10"
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
      <MentorChat initialMode={mode} key={mode} />
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