/** Xã hội — mạng xã hội mô phỏng: đọc dòng tin, like, bình luận, lưu bài. */
"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/common/Badge";
import { IconEmpty, IconSearch } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField, TextField } from "@/components/common/Field";
import { Skeleton } from "@/components/common/Skeleton";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { SocialPostCard } from "@/components/social/SocialPostCard";
import { SocialSidebar } from "@/components/social/SocialSidebar";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { listSocialPosts, toggleSocialLike } from "@/services/social";
import { listCompanies } from "@/services/companies";
import { useSavedStore } from "@/store/useSavedStore";
import { SOCIAL_PERSONAS, sentimentLabel, sentimentVariant } from "@/utils/domain";
import { cn } from "@/utils/cn";
import type {
  CompanyResponse,
  SocialPostResponse,
} from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";

const SENTIMENT_OPTIONS = [
  { value: "positive", label: "Tích cực" },
  { value: "neutral", label: "Trung lập" },
  { value: "negative", label: "Tiêu cực" },
];

type Tab = "all" | "saved";

export default function SocialPage() {
  const savedPosts = useSavedStore((state) => state.social);
  const savedPostsTotal = useSavedStore((state) => state.socialTotal);
  const loadSavedPosts = useSavedStore((state) => state.loadSocial);
  const applyToggle = useSavedStore((state) => state.applyToggle);
  const [tab, setTab] = useState<Tab>("all");

  const [posts, setPosts] = useState<SocialPostResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const debouncedQ = useDebouncedValue(searchInput);
  const [personaType, setPersonaType] = useState<string>("");
  const [sentiment, setSentiment] = useState<string>("");
  const [companies, setCompanies] = useState<CompanyResponse[]>([]);

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const response = await listSocialPosts({
        persona_type: personaType || null,
        sentiment: sentiment || null,
        q: debouncedQ || null,
        limit: 50,
      });
      setPosts(response.items);
      setTotal(response.total);
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Không tải được bài đăng.");
    }
  }, [personaType, sentiment, debouncedQ]);

  useEffect(() => {
    if (tab === "all") {
      void load();
    } else {
      void loadSavedPosts();
    }
  }, [tab, load, loadSavedPosts]);

  useEffect(() => {
    listCompanies()
      .then((response) => setCompanies(response.items))
      .catch(() => setCompanies([]));
  }, []);

  const applyPostUpdate = (postId: string, patch: Partial<SocialPostResponse>) => {
    setPosts((prev) =>
      prev.map((post) => (post.id === postId ? { ...post, ...patch } : post)),
    );
  };

  const handleToggleLike = async (post: SocialPostResponse) => {
    const previous = post;
    const optimistic: SocialPostResponse = {
      ...post,
      liked_by_me: !post.liked_by_me,
      likes_count: Math.max(0, post.likes_count + (post.liked_by_me ? -1 : 1)),
    };
    applyPostUpdate(post.id, optimistic);
    try {
      const result = await toggleSocialLike(post.id);
      applyPostUpdate(post.id, {
        liked_by_me: result.liked,
        likes_count: result.likes_count,
      });
    } catch {
      // Lỗi mạng / hết token → hoàn tác trạng thái tối ưu.
      applyPostUpdate(previous.id, previous);
    }
  };

  const handleCommentAdded = (postId: string) => {
    setPosts((prev) =>
      prev.map((post) =>
        post.id === postId ? { ...post, comments_count: post.comments_count + 1 } : post,
      ),
    );
  };

  const loadMore = async () => {
    try {
      const response = await listSocialPosts({
        persona_type: personaType || null,
        sentiment: sentiment || null,
        q: debouncedQ || null,
        skip: posts.length,
        limit: 50,
      });
      setPosts((prev) => [...prev, ...response.items]);
      setTotal(response.total);
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Không tải được bài đăng.");
    }
  };

  return (
    <div>
      <PageHeader
        title="Xã hội"
        description="Mạng xã hội mô phỏng của nhà đầu tư — đọc góc nhìn, like, bình luận, lưu bài và học cách nhận diện tin đồn, khoe lãi, cảnh báo lừa đảo."
      />

      <div className="mb-5 flex items-center gap-1 rounded-lg border border-line bg-paper p-1 dark:border-granite-700 dark:bg-granite-900">
        <TabButton active={tab === "all"} onClick={() => setTab("all")}>
          Tất cả
        </TabButton>
        <TabButton active={tab === "saved"} onClick={() => setTab("saved")}>
          Đã lưu
          {savedPostsTotal > 0 && (
            <Badge variant="neutral" className="ml-1.5">{savedPostsTotal}</Badge>
          )}
        </TabButton>
      </div>

      {tab === "saved" ? (
        <SavedPosts
          posts={savedPosts.map((item) => item.social).filter((post): post is SocialPostResponse => post !== null)}
          companies={companies}
          onToggleLike={handleToggleLike}
          onCommentAdded={handleCommentAdded}
          onRemove={(id) => applyToggle("social", id, false)}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0 space-y-4">
            <div className="flex flex-col gap-3 rounded-xl border border-line bg-paper p-3 sm:flex-row sm:items-end dark:border-granite-700 dark:bg-granite-900">
              <TextField
                label="Tìm bài đăng"
                placeholder="Nội dung, tác giả…"
                icon={<IconSearch className="h-4 w-4" />}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                size="sm"
                className="sm:max-w-xs"
              />
              <SelectField
                label="Nhóm persona"
                value={personaType}
                onChange={(event) => setPersonaType(event.target.value)}
              >
                <option value="">Tất cả</option>
                {SOCIAL_PERSONAS.map((persona) => (
                  <option key={persona.value} value={persona.value}>
                    {persona.label}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Tâm lý"
                value={sentiment}
                onChange={(event) => setSentiment(event.target.value)}
              >
                <option value="">Tất cả</option>
                {SENTIMENT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </SelectField>
              <div className="text-sm text-ink-500 sm:ml-auto sm:pb-2 dark:text-granite-400">
                {total} bài đăng
              </div>
            </div>

            {status === "loading" && posts.length === 0 ? (
              <div className="space-y-4">
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            ) : status === "error" && posts.length === 0 ? (
              <ErrorPanel error={error} onRetry={() => void load()} />
            ) : posts.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line bg-paper px-6 py-16 text-center dark:border-granite-600 dark:bg-granite-900">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-line bg-ink-50 text-ink-400 dark:border-granite-700 dark:bg-granite-800 dark:text-granite-400">
                  <IconEmpty className="h-6 w-6" />
                </div>
                <h3 className="text-sm font-black text-ink-900 dark:text-slip">
                  Không có bài đăng phù hợp
                </h3>
                <p className="mt-1 text-sm text-ink-500 dark:text-granite-400">
                  Hãy đổi từ khoá tìm kiếm hoặc thay đổi bộ lọc persona & tâm lý.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {posts.map((post) => (
                  <SocialPostCard
                    key={post.id}
                    post={post}
                    companies={companies}
                    onToggleLike={handleToggleLike}
                    onCommentAdded={handleCommentAdded}
                  />
                ))}
                {posts.length < total && (
                  <div className="flex justify-center pt-1">
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
              </div>
            )}
          </div>

          <aside className="hidden min-w-0 lg:block">
            <SocialSidebar posts={posts} />
          </aside>
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-2 text-xs text-ink-500 dark:text-granite-400">
        <span>Tâm lý:</span>
        {SENTIMENT_OPTIONS.map((option) => (
          <Badge key={option.value} variant={sentimentVariant(option.value)}>
            {sentimentLabel(option.value)}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function SavedPosts({
  posts,
  companies,
  onToggleLike,
  onCommentAdded,
  onRemove,
}: {
  posts: SocialPostResponse[];
  companies: CompanyResponse[];
  onToggleLike: (post: SocialPostResponse) => void;
  onCommentAdded: (postId: string) => void;
  onRemove: (postId: string) => void;
}) {
  const status = useSavedStore((state) => state.status);
  const error = useSavedStore((state) => state.error);

  if (status === "loading") {
    return <p className="py-8 text-center text-sm text-ink-500 dark:text-granite-400">Đang tải…</p>;
  }

  if (status === "error") {
    return <p className="py-8 text-center text-sm text-mkt-down dark:text-mkt-down-400">{error}</p>;
  }

  if (posts.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-ink-500 dark:text-granite-400">
        Bạn chưa lưu bài đăng nào. Nhấn biểu tượng bookmark trên bài để lưu.
      </p>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-4">
        {posts.map((post) => (
          <SocialPostCard
            key={post.id}
            post={post}
            companies={companies}
            onToggleLike={onToggleLike}
            onCommentAdded={onCommentAdded}
            onRemove={onRemove}
          />
        ))}
      </div>
      <aside className="hidden min-w-0 lg:block">
        <SocialSidebar posts={posts} />
      </aside>
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