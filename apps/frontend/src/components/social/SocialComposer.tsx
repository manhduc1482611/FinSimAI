/**
 * SocialComposer — ô đăng bài kiểu mạng xã hội: avatar + nội dung + symbol.
 * Ẩn khả năng đăng nhập không có; khi chưa đăng nhập hiển thị hướng dẫn.
 */
"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";

import { Badge } from "@/components/common/Badge";
import { Avatar } from "@/components/common/Avatar";
import { Button } from "@/components/common/Button";
import { IconUser } from "@/components/common/Icon";
import { listCompanies } from "@/services/companies";
import { createSocialPost } from "@/services/social";
import { useAuthStore } from "@/store/useAuthStore";
import { toRequestError } from "@/services/api";
import type { CompanyResponse, SocialPostResponse } from "@finsim/shared-types/generated/api-types";

interface SocialComposerProps {
  onPosted: (post: SocialPostResponse) => void;
}

export function SocialComposer({ onPosted }: SocialComposerProps) {
  const user = useAuthStore((state) => state.user);
  const [content, setContent] = useState("");
  const [symbol, setSymbol] = useState("");
  const [companies, setCompanies] = useState<CompanyResponse[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState(1);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    void listCompanies({ limit: 60 })
      .then((response) => {
        if (!cancelled) {
          setCompanies(response.items);
        }
      })
      .catch(() => {
        // Composer vẫn dùng được mà không có gợi ý symbol.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const initial = (user?.display_name ?? user?.username ?? "?").trim().charAt(0).toUpperCase();

  const handleSubmit = async () => {
    const text = content.trim();
    if (!text || submitting || !user) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const post = await createSocialPost({
        content: text,
        company_symbol: symbol || null,
      });
      setContent("");
      setSymbol("");
      setRows(1);
      onPosted(post);
    } catch (err) {
      setError(toRequestError(err).detail);
    } finally {
      setSubmitting(false);
    }
  };

  if (!user) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-line bg-[#FFFDF8] px-5 py-4 dark:border-granite-700 dark:bg-granite-900">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line bg-ink-50 text-ink-400 dark:border-granite-700 dark:bg-granite-800 dark:text-granite-400">
          <IconUser className="h-5 w-5" />
        </div>
        <p className="text-sm text-ink-600 dark:text-granite-300">
          Đăng nhập để chia sẻ góc nhìn của bạn và tương tác like/bình luận.{" "}
          <Link href="/login" className="font-semibold text-brand-700 hover:underline dark:text-brand-300">
            Đăng nhập →
          </Link>
        </p>
      </div>
    );
  }

  const canPost = content.trim().length > 0 && !submitting;

  return (
    <div className="rounded-xl border border-line bg-[#FFFDF8] p-4 dark:border-granite-700 dark:bg-granite-900">
      <div className="flex gap-3">
        <Avatar
          src={user.avatar_url}
          alt={user.display_name ?? user.username}
          fallback={initial}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500/15 text-sm font-bold text-brand-700 dark:bg-brand-500/20 dark:text-brand-300"
        />
        <div className="min-w-0 flex-1">
          <textarea
            ref={textareaRef}
            rows={rows}
            value={content}
            placeholder="Chia sẻ góc nhìn thị trường hôm nay…"
            className="input w-full resize-none"
            maxLength={2000}
            onFocus={() => setRows(3)}
            onChange={(event) => setContent(event.target.value)}
          />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <select
                value={symbol}
                onChange={(event) => setSymbol(event.target.value)}
                className="input max-w-[220px] py-1.5 text-xs"
                aria-label="Chọn cổ phiếu nhắc tới"
              >
                <option value="">Không gắn cổ phiếu</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.symbol}>
                    {company.symbol} · {company.name}
                  </option>
                ))}
              </select>
              {symbol !== "" && (
                <Badge variant="info">{symbol}</Badge>
              )}
            </div>
            <Button size="sm" onClick={() => void handleSubmit()} loading={submitting} disabled={!canPost}>
              Đăng bài
            </Button>
          </div>
          {error !== null && <p className="mt-2 text-xs text-mkt-down dark:text-mkt-down-400">{error}</p>}
        </div>
      </div>
    </div>
  );
}
