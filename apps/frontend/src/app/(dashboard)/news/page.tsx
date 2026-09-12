/** Tin tức — bước 1 của hành trình: đọc tin & cảm nhận thị trường. */
"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/common/Badge";
import { PageHeader } from "@/components/common/PageHeader";
import { NewsCard } from "@/components/news/NewsCard";
import { NewsFilter } from "@/components/news/NewsFilter";
import { NewsList } from "@/components/news/NewsList";
import { useNewsStore } from "@/store/useNewsStore";
import { useSavedStore } from "@/store/useSavedStore";
import type { SavedContentItem } from "@finsim/shared-types/generated/api-types";
import { cn } from "@/utils/cn";

type Tab = "all" | "saved";

export default function NewsPage() {
  const fetchNews = useNewsStore((state) => state.fetchNews);
  const savedNews = useSavedStore((state) => state.news);
  const savedNewsTotal = useSavedStore((state) => state.newsTotal);
  const loadSavedNews = useSavedStore((state) => state.loadNews);
  const applyToggle = useSavedStore((state) => state.applyToggle);
  const [tab, setTab] = useState<Tab>("all");

  useEffect(() => {
    if (tab === "all") {
      void fetchNews();
    } else {
      void loadSavedNews();
    }
  }, [tab, fetchNews, loadSavedNews]);

  return (
    <div>
      <PageHeader
        title="Bản tin thị trường"
        description="Đọc tin & cảm nhận thị trường — các sự kiện vĩ mô, ngành và doanh nghiệp kèm mức tác động tới giá."
      />

      <div className="mb-5 flex items-center gap-1 rounded-lg border border-line bg-paper p-1 dark:border-granite-700 dark:bg-granite-900">
        <TabButton active={tab === "all"} onClick={() => setTab("all")}>
          Tất cả
        </TabButton>
        <TabButton active={tab === "saved"} onClick={() => setTab("saved")}>
          Đã lưu
          {savedNewsTotal > 0 && (
            <Badge variant="neutral" className="ml-1.5">{savedNewsTotal}</Badge>
          )}
        </TabButton>
      </div>

      {tab === "all" ? (
        <>
          <NewsFilter />
          <NewsList />
        </>
      ) : (
        <NewsListSaved items={savedNews} onRemove={(id) => applyToggle("news", id, false)} />
      )}
    </div>
  );
}

function NewsListSaved({
  items,
  onRemove,
}: {
  items: SavedContentItem[];
  onRemove: (id: string) => void;
}) {
  const status = useSavedStore((state) => state.status);
  const error = useSavedStore((state) => state.error);

  if (status === "loading") {
    return <p className="py-8 text-center text-sm text-ink-500 dark:text-granite-400">Đang tải…</p>;
  }

  if (status === "error") {
    return <p className="py-8 text-center text-sm text-mkt-down dark:text-mkt-down-400">{error}</p>;
  }

  if (items.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-ink-500 dark:text-granite-400">
        Bạn chưa lưu tin nào. Nhấn biểu tượng bookmark trên tin để lưu.
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) =>
        item.news ? (
          <NewsCard key={item.content_id} news={item.news} onRemove={onRemove} />
        ) : null,
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-brand-500 text-granite-950 shadow-board"
          : "text-ink-600 hover:bg-ink-100 dark:text-granite-200 dark:hover:bg-granite-800",
      )}
    >
      {children}
    </button>
  );
}