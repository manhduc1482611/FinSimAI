/**
 * NewsList — layout trang báo chính thức:
 * - Cột chính: tin chính (hero) + lưới tin phụ.
 * - Cột phụ: tin đáng chú ý + điều hướng chuyên mục.
 */
"use client";

import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconEmpty } from "@/components/common/Icon";
import { Skeleton } from "@/components/common/Skeleton";
import { NewsCard } from "@/components/news/NewsCard";
import { NewsHero } from "@/components/news/NewsHero";
import { NewsSidebar } from "@/components/news/NewsSidebar";
import { useNewsStore } from "@/store/useNewsStore";

export function NewsList() {
  const items = useNewsStore((state) => state.items);
  const total = useNewsStore((state) => state.total);
  const status = useNewsStore((state) => state.status);
  const error = useNewsStore((state) => state.error);
  const fetchNews = useNewsStore((state) => state.fetchNews);

  if (status === "loading") {
    return (
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <Skeleton className="h-52 w-full" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
          </div>
        </div>
        <div className="space-y-5">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </div>
    );
  }

  if (status === "error") {
    return <ErrorPanel error={error} onRetry={() => void fetchNews()} />;
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-[#FFFDF8] px-6 py-16 text-center dark:border-granite-700 dark:bg-granite-900">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-line bg-ink-50 text-ink-400 dark:border-granite-700 dark:bg-granite-800 dark:text-granite-400">
          <IconEmpty className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-ink-900 dark:text-slip">Chưa có tin tức nào</h3>
        <p className="mt-1 text-sm text-ink-500 dark:text-granite-400">
          {status === "success"
            ? "Hãy thử đổi bộ lọc, hoặc chờ kịch bản mới được sinh ra."
            : "Dữ liệu sẽ xuất hiện khi bạn đăng nhập và backend đang chạy."}
        </p>
      </div>
    );
  }

  const [hero, ...rest] = items;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-5">
        <NewsHero news={hero} />
        <div className="grid gap-4 sm:grid-cols-2">
          {rest.map((news) => (
            <NewsCard key={news.id} news={news} />
          ))}
        </div>
        <p className="text-xs text-ink-400 dark:text-granite-400">
          Hiển thị {items.length} / {total} bài viết
        </p>
      </div>

      <aside className="hidden min-w-0 lg:block">
        <NewsSidebar items={items} />
      </aside>
    </div>
  );
}
