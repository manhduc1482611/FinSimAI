/**
 * NewsList — layout trang báo chính thức:
 * - Cột chính: tin chính (hero) + lưới tin phụ + nút Xem thêm.
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
import { cn } from "@/utils/cn";

export interface NewsListProps {
  /** Gọi khi bỏ lưu một tin — dùng cho danh sách "Đã lưu" để xoá item. */
  onRemove?: (newsId: string) => void;
}

export function NewsList({ onRemove }: NewsListProps) {
  const items = useNewsStore((state) => state.items);
  const total = useNewsStore((state) => state.total);
  const status = useNewsStore((state) => state.status);
  const error = useNewsStore((state) => state.error);
  const fetchNews = useNewsStore((state) => state.fetchNews);
  const hasMore = useNewsStore((state) => state.hasMore);
  const loadMore = useNewsStore((state) => state.loadMore);

  if (status === "loading" && items.length === 0) {
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

  if (status === "error" && items.length === 0) {
    return <ErrorPanel error={error} onRetry={() => void fetchNews()} />;
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-paper px-6 py-16 text-center dark:border-granite-700 dark:bg-granite-900">
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
            <NewsCard key={news.id} news={news} onRemove={onRemove} />
          ))}
        </div>
        {hasMore && (
          <div className="flex justify-center pt-2">
            <button
              type="button"
              onClick={() => void loadMore()}
              disabled={status === "loading"}
              className={cn(
                "btn-secondary px-6 py-2 text-xs",
                status === "loading" && "cursor-wait opacity-60",
              )}
            >
              {status === "loading" ? "Đang tải…" : "Xem thêm"}
            </button>
          </div>
        )}
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