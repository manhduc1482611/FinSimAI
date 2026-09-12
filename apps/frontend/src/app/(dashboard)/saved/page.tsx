/** Đã lưu — tổng hợp tất cả tin tức & bài xã hội user đã bookmark. */
"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/common/PageHeader";
import { Skeleton } from "@/components/common/Skeleton";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { NewsCard } from "@/components/news/NewsCard";
import { SocialPostCard } from "@/components/social/SocialPostCard";
import { listCompanies } from "@/services/companies";
import { useSavedStore } from "@/store/useSavedStore";
import type {
  CompanyResponse,
  SocialPostResponse,
} from "@finsim/shared-types/generated/api-types";

export default function SavedPage() {
  const savedNews = useSavedStore((state) => state.news);
  const savedPosts = useSavedStore((state) => state.social);
  const status = useSavedStore((state) => state.status);
  const error = useSavedStore((state) => state.error);
  const loadNews = useSavedStore((state) => state.loadNews);
  const loadSocial = useSavedStore((state) => state.loadSocial);
  const applyToggle = useSavedStore((state) => state.applyToggle);
  const [companies, setCompanies] = useState<CompanyResponse[]>([]);

  useEffect(() => {
    void loadNews();
    void loadSocial();
    listCompanies()
      .then((response) => setCompanies(response.items))
      .catch(() => setCompanies([]));
  }, [loadNews, loadSocial]);

  if (status === "loading" && savedNews.length === 0 && savedPosts.length === 0) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-10 w-40" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-44 w-full" />
        </div>
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (status === "error" && savedNews.length === 0 && savedPosts.length === 0) {
    return <ErrorPanel error={error} onRetry={() => void (loadNews(), loadSocial())} />;
  }

  const posts: SocialPostResponse[] = savedPosts
    .map((item) => item.social)
    .filter((post): post is SocialPostResponse => post !== null);

  return (
    <div>
      <PageHeader
        title="Đã lưu"
        description="Tin tức và bài đăng bạn đã bookmark — đọc lại bất cứ lúc nào."
      />

      {savedNews.length === 0 && posts.length === 0 ? (
        <p className="py-12 text-center text-sm text-ink-500 dark:text-granite-400">
          Bạn chưa lưu nội dung nào. Nhấn biểu tượng bookmark trên tin tức hoặc bài đăng để lưu.
        </p>
      ) : (
        <div className="space-y-8">
          <section>
            <h2 className="mb-3 border-b border-line pb-2 text-sm font-bold uppercase tracking-wide text-ink-900 dark:border-granite-800 dark:text-slip">
              Tin tức đã lưu
            </h2>
            {savedNews.length === 0 ? (
              <p className="py-4 text-sm text-ink-400">Chưa có tin tức nào.</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {savedNews.map((item) =>
                  item.news ? (
                    <NewsCard
                      key={item.content_id}
                      news={item.news}
                      onRemove={(id) => applyToggle("news", id, false)}
                    />
                  ) : null,
                )}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 border-b border-line pb-2 text-sm font-bold uppercase tracking-wide text-ink-900 dark:border-granite-800 dark:text-slip">
              Bài đăng đã lưu
            </h2>
            {posts.length === 0 ? (
              <p className="py-4 text-sm text-ink-400">Chưa có bài đăng nào.</p>
            ) : (
              <div className="space-y-4">
                {posts.map((post) => (
                  <SocialPostCard
                    key={post.id}
                    post={post}
                    companies={companies}
                    onToggleLike={() => undefined}
                    onCommentAdded={() => undefined}
                    onRemove={(id) => applyToggle("social", id, false)}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}