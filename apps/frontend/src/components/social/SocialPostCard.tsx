/**
 * SocialPostCard — bài đăng mạng xã hội tương tác được:
 * - Like/unlike (optimistic ở parent, revert khi lỗi).
 * - Mở thread bình luận, đăng bình luận mới.
 * Khi chưa đăng nhập, thao tác like/comment sẽ chuyển sang trang đăng nhập.
 */
"use client";

import { useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/common/Badge";
import { IconChat, IconHeart } from "@/components/common/Icon";
import { Spinner } from "@/components/common/Spinner";
import { toRequestError } from "@/services/api";
import { createSocialComment, listSocialComments } from "@/services/social";
import { useAuthStore } from "@/store/useAuthStore";
import { personaLabel, sentimentLabel, sentimentVariant, viralityTone } from "@/utils/domain";
import { formatRelativeTime } from "@/utils/format";
import { cn } from "@/utils/cn";
import type {
  SocialCommentResponse,
  SocialPostResponse,
} from "@finsim/shared-types/generated/api-types";

interface SocialPostCardProps {
  post: SocialPostResponse;
  onToggleLike: (post: SocialPostResponse) => void;
  onCommentAdded: (postId: string) => void;
}

export function SocialPostCard({ post, onToggleLike, onCommentAdded }: SocialPostCardProps) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [comments, setComments] = useState<SocialCommentResponse[]>([]);
  const [commentsTotal, setCommentsTotal] = useState(post.comments_count);
  const [commentsStatus, setCommentsStatus] = useState<"idle" | "loading" | "error">("idle");
  const [commentText, setCommentText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedRef = useRef(false);

  const initial = post.author_name.trim().charAt(0).toUpperCase();

  const requireAuth = () => {
    if (!user) {
      router.push("/login");
      return false;
    }
    return true;
  };

  const loadComments = async () => {
    if (loadedRef.current) {
      setCommentsOpen((open) => !open);
      return;
    }
    setCommentsStatus("loading");
    try {
      const response = await listSocialComments(post.id);
      setComments(response.items);
      setCommentsTotal(response.total);
      loadedRef.current = true;
      setCommentsStatus("idle");
    } catch (err) {
      setCommentsStatus("error");
      setError(toRequestError(err).detail);
    }
    setCommentsOpen((open) => !open);
  };

  const handleComment = async () => {
    const text = commentText.trim();
    if (!text || submitting || !requireAuth()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await createSocialComment(post.id, { content: text });
      setComments((prev) => [...prev, created]);
      setCommentsTotal((prev) => prev + 1);
      setCommentText("");
      loadedRef.current = true;
      onCommentAdded(post.id);
    } catch (err) {
      setError(toRequestError(err).detail);
    } finally {
      setSubmitting(false);
    }
  };

  const handleLike = () => {
    if (!requireAuth()) {
      return;
    }
    onToggleLike(post);
  };

  return (
    <article className="rounded-xl border border-ink-200 bg-white transition-shadow hover:shadow-sm dark:border-ink-700 dark:bg-ink-900">
      <div className="flex items-center gap-3 p-4 pb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
          {post.author_avatar ?? initial}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink-900 dark:text-ink-100">
            {post.author_name}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-ink-500 dark:text-ink-400">
            <Badge variant="neutral">{personaLabel(post.persona_type)}</Badge>
            <span>·</span>
            <span>{formatRelativeTime(post.simulated_at)}</span>
          </div>
        </div>
        <Badge variant={viralityTone(post.virality_score)}>
          Viral {post.virality_score}%
        </Badge>
      </div>

      <p className="px-4 pb-3 whitespace-pre-line text-sm leading-relaxed text-ink-800 dark:text-ink-200">
        {post.content}
      </p>

      <div className="border-t border-ink-100 px-2 py-1 dark:border-ink-800">
        <div className="flex items-center">
          <button
            type="button"
            onClick={handleLike}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              post.liked_by_me
                ? "text-red-600 dark:text-red-400"
                : "text-ink-500 hover:bg-ink-50 hover:text-ink-800 dark:text-ink-400 dark:hover:bg-ink-800",
            )}
            aria-pressed={post.liked_by_me}
          >
            <IconHeart
              className={cn("h-4 w-4", post.liked_by_me && "fill-current")}
            />
            {post.likes_count > 0 ? `${post.likes_count} thích` : "Thích"}
          </button>
          <button
            type="button"
            onClick={() => void loadComments()}
            className="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-ink-500 transition-colors hover:bg-ink-50 hover:text-ink-800 dark:text-ink-400 dark:hover:bg-ink-800"
            aria-expanded={commentsOpen}
          >
            <IconChat className="h-4 w-4" />
            {commentsTotal > 0 ? `${commentsTotal} bình luận` : "Bình luận"}
          </button>
          <span className="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-ink-500 dark:text-ink-400">
            <IconShare className="h-4 w-4" />
            {post.shares_count > 0 ? `${post.shares_count} chia sẻ` : "Chia sẻ"}
          </span>
        </div>
      </div>

      {commentsOpen && (
        <div className="border-t border-ink-100 px-4 py-3 dark:border-ink-800">
          {commentsStatus === "loading" ? (
            <div className="flex justify-center py-4">
              <Spinner size="sm" />
            </div>
          ) : commentsStatus === "error" ? (
            <p className="py-2 text-center text-xs text-red-600 dark:text-red-400">{error}</p>
          ) : (
            <div className="space-y-3">
              {comments.map((comment) => (
                <CommentRow key={comment.id} comment={comment} />
              ))}
              {comments.length === 0 && (
                <p className="text-center text-xs text-ink-400">Chưa có bình luận nào.</p>
              )}

              <div className="flex items-start gap-2">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
                  {(user?.display_name ?? user?.username ?? "?").trim().charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <input
                      value={commentText}
                      onChange={(event) => setCommentText(event.target.value)}
                      placeholder={user ? "Viết bình luận…" : "Đăng nhập để bình luận…"}
                      disabled={!user}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          void handleComment();
                        }
                      }}
                      className="input w-full py-1.5 text-sm"
                      maxLength={1000}
                    />
                    <button
                      type="button"
                      onClick={() => void handleComment()}
                      disabled={!user || commentText.trim().length === 0 || submitting}
                      className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-brand-500 dark:hover:bg-brand-600"
                    >
                      {submitting ? "Đang gửi…" : "Gửi"}
                    </button>
                  </div>
                  {error !== null && (
                    <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-ink-100 px-4 py-2.5 text-xs text-ink-500 dark:border-ink-800 dark:text-ink-400">
        <Badge variant={sentimentVariant(post.sentiment)}>
          {sentimentLabel(post.sentiment)}
        </Badge>
        {post.company_id !== null && (
          <span className="rounded-full bg-brand-50 px-2 py-0.5 font-medium text-brand-700 ring-1 ring-inset ring-brand-200 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/30">
            Nhắc tới doanh nghiệp
          </span>
        )}
        <span className="ml-auto">
          {post.persona_type === "user" ? "Bạn · Người dùng" : "Persona mô phỏng"}
        </span>
      </div>
    </article>
  );
}

function CommentRow({ comment }: { comment: SocialCommentResponse }) {
  const initial = comment.author_name.trim().charAt(0).toUpperCase();
  return (
    <div className="flex items-start gap-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink-100 text-xs font-bold text-ink-600 dark:bg-ink-700 dark:text-ink-300">
        {comment.author_avatar ?? initial}
      </div>
      <div className="min-w-0 rounded-lg bg-ink-50 px-3 py-2 dark:bg-ink-800">
        <p className="text-xs font-semibold text-ink-900 dark:text-ink-100">{comment.author_name}</p>
        <p className="mt-0.5 whitespace-pre-line text-sm text-ink-700 dark:text-ink-300">
          {comment.content}
        </p>
        <p className="mt-1 text-[10px] text-ink-400">{formatRelativeTime(comment.created_at)}</p>
      </div>
    </div>
  );
}

function IconShare(props: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={props.className}
    >
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <path d="m16 6-4-4-4 4" />
      <path d="M12 2v13" />
    </svg>
  );
}
