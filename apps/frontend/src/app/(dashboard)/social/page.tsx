/** Xã hội — mạng xã hội mô phỏng: đăng bài, like, bình luận, theo dõi tâm lý. */
"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/common/Badge";
import { IconEmpty } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField } from "@/components/common/Field";
import { Skeleton } from "@/components/common/Skeleton";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { SocialComposer } from "@/components/social/SocialComposer";
import { SocialPostCard } from "@/components/social/SocialPostCard";
import { SocialSidebar } from "@/components/social/SocialSidebar";
import { listSocialPosts, toggleSocialLike } from "@/services/social";
import { SOCIAL_PERSONAS, sentimentLabel, sentimentVariant } from "@/utils/domain";
import type { SocialPostResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";

const SENTIMENT_OPTIONS = [
  { value: "positive", label: "Tích cực" },
  { value: "neutral", label: "Trung lập" },
  { value: "negative", label: "Tiêu cực" },
];

export default function SocialPage() {
  const [posts, setPosts] = useState<SocialPostResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [personaType, setPersonaType] = useState<string>("");
  const [sentiment, setSentiment] = useState<string>("");

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const response = await listSocialPosts({
        persona_type: personaType || null,
        sentiment: sentiment || null,
        limit: 50,
      });
      setPosts(response.items);
      setTotal(response.total);
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Không tải được bài đăng.");
    }
  }, [personaType, sentiment]);

  useEffect(() => {
    void load();
  }, [load]);

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

  const handlePosted = (post: SocialPostResponse) => {
    setPosts((prev) => [post, ...prev]);
    setTotal((prev) => prev + 1);
  };

  return (
    <div>
      <PageHeader
        title="Xã hội"
        description="Mạng xã hội mô phỏng của nhà đầu tư — chia sẻ góc nhìn, like, bình luận và học cách nhận diện tin đồn, khoe lãi, cảnh báo lừa đảo."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-4">
          <SocialComposer onPosted={handlePosted} />

          <div className="flex flex-col gap-3 rounded-xl border border-line bg-[#FFFDF8] p-3 sm:flex-row sm:items-end dark:border-granite-700 dark:bg-granite-900">
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

          {status === "loading" ? (
            <div className="space-y-4">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : status === "error" ? (
            <ErrorPanel error={error} onRetry={() => void load()} />
          ) : posts.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line bg-[#FFFDF8] px-6 py-16 text-center dark:border-granite-600 dark:bg-granite-900">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-line bg-ink-50 text-ink-400 dark:border-granite-700 dark:bg-granite-800 dark:text-granite-400">
                <IconEmpty className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-black text-ink-900 dark:text-slip">
                Không có bài đăng phù hợp
              </h3>
              <p className="mt-1 text-sm text-ink-500 dark:text-granite-400">
                Hãy thay đổi bộ lọc persona hoặc tâm lý.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {posts.map((post) => (
                <SocialPostCard
                  key={post.id}
                  post={post}
                  onToggleLike={handleToggleLike}
                  onCommentAdded={handleCommentAdded}
                />
              ))}
            </div>
          )}
        </div>

        <aside className="hidden min-w-0 lg:block">
          <SocialSidebar posts={posts} />
        </aside>
      </div>

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
