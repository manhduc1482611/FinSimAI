/**
 * MentorChat — giao diện chat Socratic với Mentor (streaming qua WebSocket).
 */
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { useAuthStore } from "@/store/useAuthStore";
import { useMentorStore } from "@/store/useMentorStore";
import { useSocraticMentor } from "@/hooks/useSocraticMentor";
import { cn } from "@/utils/cn";

const SUGGESTIONS = [
  "Giải thích khái niệm \"giá trị thời gian của tiền\"?",
  "Một cổ phiếu PE cao có nghĩa là gì?",
  "Tôi nên đa dạng hóa danh mục như thế nào?",
  "Vì sao cần tách biệt cảm xúc khi giao dịch?",
];

export function MentorChat() {
  const token = useAuthStore((state) => state.token);
  const mentor = useSocraticMentor();
  const sessionId = useMentorStore((state) => state.sessionId);
  const startSession = useMentorStore((state) => state.startSession);

  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (sessionId === null) {
      startSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mentor.messages.length > 0) {
      listRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [mentor.messages, mentor.isStreaming]);

  if (token === null) {
    return (
      <div className="rounded-xl border border-dashed border-ink-300 bg-white px-6 py-16 text-center">
        <h3 className="text-sm font-semibold text-ink-900">Cần đăng nhập</h3>
        <p className="mt-1 text-sm text-ink-500">
          Đăng nhập để bắt đầu phiên hỏi đáp Socratic với Mentor.
        </p>
        <div className="mt-4">
          <Link href="/login">
            <Button>Đăng nhập</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <Card className="flex h-[calc(100vh-16rem)] min-h-[28rem] flex-col">
      <div className="border-b border-ink-200 px-5 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-ink-900">Mentor tài chính</h2>
            <p className="text-xs text-ink-500">
              Hướng dẫn theo phương pháp Socratic — Mentor hỏi ngược để bạn tự tư duy.
            </p>
          </div>
          {mentor.isConnected && mentor.isReady ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Sẵn sàng
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-600 ring-1 ring-inset ring-ink-200">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400" />
              Đang kết nối
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {mentor.lastError !== null && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {mentor.lastError}
          </div>
        )}

        {!mentor.isConnected && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Chưa kết nối được tới Mentor. Đảm bảo backend WebSocket đang chạy, sau đó tải lại trang.
          </div>
        )}

        {mentor.messages.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-sm text-ink-500">
              Bắt đầu phiên tư vấn bằng một câu hỏi — hoặc chọn một gợi ý bên dưới.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="rounded-full border border-ink-200 bg-white px-3 py-1 text-xs text-ink-600 transition-colors hover:border-brand-400 hover:text-brand-700"
                  onClick={() => {
                    setDraft(suggestion);
                    inputRef.current?.focus();
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {mentor.messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex",
                  message.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    message.role === "user"
                      ? "rounded-br-md bg-brand-600 text-white"
                      : "rounded-bl-md border border-ink-100 bg-ink-50 text-ink-800",
                  )}
                >
                  {message.content}
                  {message.role === "mentor" && mentor.isStreaming && (
                    <span className="ml-1 inline-block h-3.5 w-1 animate-pulse bg-ink-400 align-text-bottom" />
                  )}
                </div>
              </div>
            ))}
            <div ref={listRef} />
          </div>
        )}
      </div>

      <div className="border-t border-ink-200 px-5 py-3">
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!draft.trim() || mentor.isStreaming) {
              return;
            }
            mentor.sendAsk(draft);
            setDraft("");
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Hỏi Mentor bất cứ điều gì về tài chính..."
            disabled={mentor.isStreaming}
            className="input flex-1"
          />
          {mentor.isStreaming ? (
            <Button type="button" variant="secondary" onClick={mentor.sendCancel}>
              Dừng
            </Button>
          ) : (
            <Button type="submit" disabled={!draft.trim()}>
              Gửi
            </Button>
          )}
        </form>
      </div>
    </Card>
  );
}
