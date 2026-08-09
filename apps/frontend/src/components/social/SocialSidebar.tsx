/**
 * SocialSidebar — cột phụ của trang Xã hội:
 * - Bài đăng thịnh hành (top virality).
 * - Phân bố tâm lý của feed hiện tại.
 */
"use client";

import { Badge } from "@/components/common/Badge";
import { sentimentLabel, sentimentVariant } from "@/utils/domain";
import { formatRelativeTime } from "@/utils/format";
import type { SocialPostResponse } from "@finsim/shared-types/generated/api-types";

const SENTIMENT_ORDER = ["positive", "neutral", "negative"] as const;

export function SocialSidebar({ posts }: { posts: SocialPostResponse[] }) {
  const trending = [...posts]
    .sort((a, b) => b.virality_score - a.virality_score)
    .slice(0, 5);

  const sentimentCounts = new Map<string, number>();
  for (const post of posts) {
    sentimentCounts.set(post.sentiment, (sentimentCounts.get(post.sentiment) ?? 0) + 1);
  }
  const sentimentRows = SENTIMENT_ORDER.filter((key) => sentimentCounts.has(key))
    .map((key) => ({ key, count: sentimentCounts.get(key) ?? 0 }));

  return (
    <div className="space-y-5 lg:sticky lg:top-24">
      <section className="rounded-xl border border-line bg-[#FFFDF8] p-4 dark:border-granite-700 dark:bg-granite-900">
        <h2 className="mb-3 text-sm font-bold text-ink-900 dark:text-slip">Đang thịnh hành</h2>
        <ol className="space-y-3">
          {trending.map((post, index) => (
            <li key={post.id} className="flex gap-3">
              <span className="board-num w-5 shrink-0 text-right text-lg font-bold text-ink-300 dark:text-granite-300">
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="line-clamp-2 text-sm text-ink-800 dark:text-slip">{post.content}</p>
                <div className="mt-1 flex items-center gap-1.5 text-xs text-ink-400">
                  <span className="font-medium text-ink-500 dark:text-granite-300">{post.author_name}</span>
                  <span>·</span>
                  <span>{formatRelativeTime(post.simulated_at)}</span>
                  <span>·</span>
                  <Badge variant={sentimentVariant(post.sentiment)}>
                    {sentimentLabel(post.sentiment)}
                  </Badge>
                </div>
              </div>
            </li>
          ))}
          {trending.length === 0 && (
            <li className="text-sm text-ink-400">Chưa có bài đăng nào.</li>
          )}
        </ol>
      </section>

      <section className="rounded-xl border border-line bg-[#FFFDF8] p-4 dark:border-granite-700 dark:bg-granite-900">
        <h2 className="mb-3 text-sm font-bold text-ink-900 dark:text-slip">Tâm lý thị trường</h2>
        {sentimentRows.length === 0 ? (
          <p className="text-sm text-ink-400">Chưa có dữ liệu.</p>
        ) : (
          <ul className="space-y-2.5">
            {sentimentRows.map(({ key, count }) => {
              const percent =
                posts.length === 0
                  ? 0
                  : Math.round((count / posts.length) * 100);
              return (
                <li key={key}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <Badge variant={sentimentVariant(key)}>{sentimentLabel(key)}</Badge>
                    <span className="board-num text-ink-500 dark:text-granite-400">
                      {count} bài · {percent}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-3 text-[11px] leading-relaxed text-ink-400">
          Phân bố cảm xúc trong feed hiện tại — giúp bạn nhận diện khi thị trường
          đang quá lạc quan (nguy cơ điều chỉnh) hay quá bi quan (cơ hội).
        </p>
      </section>
    </div>
  );
}
