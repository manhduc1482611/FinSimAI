/**
 * MentorChat — giao diện chat với Mentor (3 chế độ v2.0).
 *
 * 3 chip chế độ ở header:
 * - Hỏi đáp (concept): giải thích khái niệm → card khái niệm + chips liên quan.
 * - Đề xuất (plan): khung chiến lược → card strategy.
 * - Phản biện (trade_now): phản biện lúc giao dịch → card challenge kèm symbol context.
 * Mặc định chế độ Socratic khi nhập câu hỏi/đoạn mô tả.
 */
"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { IconLock, IconRisk, IconTrendUp } from "@/components/common/Icon";
import { useAuthStore } from "@/store/useAuthStore";
import {
  useMentorStore,
  type MentorMessage,
} from "@/store/useMentorStore";
import { useSocraticMentor } from "@/hooks/useSocraticMentor";
import { fetchMentorHistory } from "@/services/mentor";
import { cn } from "@/utils/cn";
import type { ConceptReply, MentorMode, StrategyReply } from "@/types/websocket";

export interface MentorModeOption {
  id: MentorMode;
  label: string;
  hint: string;
}

export const MENTOR_MODE_OPTIONS: MentorModeOption[] = [
  { id: "concept", label: "Hỏi đáp", hint: "Giải thích khái niệm" },
  { id: "plan", label: "Đề xuất", hint: "Khung chiến lược" },
  { id: "trade_now", label: "Phản biện", hint: "Giao dịch đang cân nhắc" },
];

const SUGGESTIONS_BY_MODE: Record<MentorMode, string[]> = {
  concept: [
    "Giải thích khái niệm \"giá trị thời gian của tiền\"?",
    "Một cổ phiếu PE cao có nghĩa là gì?",
    "Biên lợi nhuận ròng (net margin) là gì?",
  ],
  plan: [
    "Tôi muốn đầu tư dài hạn, rủi ro thấp, mục tiêu ổn định — nên theo khung nào?",
    "Tôi chấp nhận rủi ro cao để tăng trưởng nhanh, thời gian 3-5 năm — hướng đi nào?",
  ],
  trade_now: [
    "Mình đang định mua cổ phiếu này — nên cân nhắc điều gì?",
    "Phản biện quyết định mua của mình với mã đang chọn.",
  ],
  socratic: [
    "Tôi nên đa dạng hóa danh mục như thế nào?",
    "Vì sao cần tách biệt cảm xúc khi giao dịch?",
  ],
};

interface MentorChatProps {
  /** fixedSymbol: gắn một mã cụ thể (trade page truyền selected symbol). */
  fixedSymbol?: string;
  /** initialMode: chế độ mặc định khi mở lần đầu. */
  initialMode?: MentorMode;
  /** compact: dùng trong panel chat nổi — card chiếm hết chiều cao chứa của nó. */
  compact?: boolean;
}

export function MentorChat({ fixedSymbol, initialMode, compact }: MentorChatProps) {
  const token = useAuthStore((state) => state.token);
  const mentor = useSocraticMentor();
  const sessionId = useMentorStore((state) => state.sessionId);
  const startSession = useMentorStore((state) => state.startSession);
  const historyLoaded = useMentorStore((state) => state.historyLoaded);
  const seedHistory = useMentorStore((state) => state.seedHistory);
  const tradeContext = useMentorStore((state) => state.tradeContext);
  const focusRequest = useMentorStore((state) => state.focusRequest);
  const pendingPrompt = useMentorStore((state) => state.pendingPrompt);
  const autoSendPending = useMentorStore((state) => state.autoSendPending);
  const clearPendingPrompt = useMentorStore((state) => state.clearPendingPrompt);

  const [mode, setMode] = useState<MentorMode>(initialMode ?? "concept");
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sessionId === null) {
      startSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Phục hồi hội thoại từ DB sau reload (A3.2) — chỉ chạy 1 lần mỗi phiên đăng nhập.
  useEffect(() => {
    if (token === null || historyLoaded) {
      return;
    }
    let cancelled = false;
    fetchMentorHistory(50)
      .then((response) => {
        if (cancelled) return;
        seedHistory(
          response.items.map((item) => ({
            id: item.id,
            role: item.role,
            content: item.content,
            ts: item.created_at,
          })),
        );
      })
      .catch(() => {
        // Lịch sử là tiện ích — lỗi không chặn chat; đánh dấu để không retry loop.
        if (!cancelled) seedHistory([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token, historyLoaded, seedHistory]);

  useEffect(() => {
    if (mentor.messages.length > 0) {
      listRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [mentor.messages, mentor.isStreaming]);

  // Đồng bộ mode khi store thay đổi từ các nút gọi ngoài (Trade, News, Social,...)
  useEffect(() => {
    if (tradeContext.mode && tradeContext.mode !== "socratic") {
      setMode(tradeContext.mode);
    }
  }, [tradeContext.mode]);

  // Yêu cầu focus từ bên ngoài (nút "Hỏi Mentor" trên trade page) — scroll + focus + nạp pendingPrompt.
  useEffect(() => {
    if (focusRequest <= 0) {
      return;
    }
    rootRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    inputRef.current?.focus();

    if (pendingPrompt) {
      const promptText = pendingPrompt;
      clearPendingPrompt();
      if (autoSendPending) {
        mentor.sendAsk(promptText, {
          mode: tradeContext.mode || mode,
          selected_symbol: fixedSymbol ?? tradeContext.selected_symbol,
        });
      } else {
        setDraft(promptText);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusRequest]);

  if (token === null) {
    return (
      <div className="rounded-xl border border-line bg-paper px-6 py-12 text-center shadow-card dark:border-granite-700 dark:bg-granite-900">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-accent-500/30 bg-accent-500/10 text-accent-600 dark:text-accent-400">
          <IconLock className="h-6 w-6" />
        </div>
        <h3 className="mt-3 text-base font-black text-ink-900 dark:text-slip">
          AI Mentor yêu cầu đăng nhập
        </h3>
        <p className="mx-auto mt-2 max-w-sm text-xs leading-relaxed text-ink-500 dark:text-granite-400">
          Bạn cần đăng nhập tài khoản để đặt câu hỏi, nhận phản biện Socratic và lưu lịch sử hội thoại.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Link href="/login" className="btn-primary px-4 py-2 text-xs">
            Đăng nhập ngay
          </Link>
          <Link href="/register" className="btn-secondary px-4 py-2 text-xs">
            Tạo tài khoản
          </Link>
        </div>
      </div>
    );
  }

  const effectiveSymbol = fixedSymbol ?? tradeContext.selected_symbol;

  return (
    <div ref={rootRef} className={compact ? "h-full" : undefined}>
      <Card
        className={cn(
          "flex flex-col",
          compact
            ? "h-full min-h-0 rounded-none border-0"
            : "h-[calc(100vh-16rem)] min-h-[28rem]",
        )}
      >
      <div className="border-b border-line px-5 py-3 dark:border-granite-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CapybaraMiniAvatar className="h-10 w-10 shadow-sm" />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-black text-ink-900 dark:text-slip">
                  Capia — AI Mentor
                </h2>
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800 dark:bg-amber-950/80 dark:text-amber-300">
                  Capybara 🍊
                </span>
              </div>
              <p className="text-xs text-ink-500 dark:text-granite-400">
                Linh vật Socratic — đặt câu hỏi gợi mở để bạn tự ra quyết định đầu tư đúng đắn.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {mentor.isConnected && mentor.isReady ? (
              <span className="stamp stamp-success animate-flicker-on">
                <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-mkt-up" />
                Sẵn sàng
              </span>
            ) : (
              <span className="stamp">
                <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-600 dark:bg-brand-400" />
                Đang kết nối
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                mentor.reset();
                setDraft("");
                inputRef.current?.focus();
              }}
              className="rounded-md border border-line px-2 py-1 text-[11px] font-medium text-ink-500 transition-colors hover:border-ink-300 hover:text-ink-900 dark:border-granite-700 dark:text-granite-400 dark:hover:text-slip"
              title="Đặt lại phiên trò chuyện mới"
            >
              Làm mới
            </button>
          </div>
        </div>

        {/* Mode selector — 3 chế độ v2.0 */}
        <div className="mt-3 flex flex-wrap gap-2">
          {MENTOR_MODE_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => {
                setMode(option.id);
                useMentorStore.getState().setTradeContext({ mode: option.id });
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                mode === option.id
                  ? "border-accent-500 bg-accent-500 text-granite-950 shadow-board"
                  : "border-ink-200 bg-paper text-ink-600 hover:border-accent-500 hover:text-accent-700 dark:border-granite-600 dark:bg-granite-900 dark:text-granite-300 dark:hover:border-accent-400 dark:hover:text-accent-300",
              )}
              title={option.hint}
            >
              {option.label}
            </button>
          ))}
        </div>

        {effectiveSymbol !== undefined && (
          <button
            type="button"
            onClick={() => setMode("trade_now")}
            className="mt-2 flex items-center gap-1 rounded-lg border border-dashed border-mkt-down/50 bg-mkt-down/5 px-2.5 py-1 text-xs text-mkt-down transition-colors hover:border-mkt-down dark:text-mkt-down-400"
            title="Phản biện quyết định với mã đang chọn"
          >
            <IconRisk className="h-3.5 w-3.5" />
            Phản biện với cổ {effectiveSymbol}
          </button>
        )}

        <p
          role="note"
          aria-label="Miễn trừ trách nhiệm"
          className="mt-2 rounded-lg border border-dashed border-line bg-paper px-3 py-1.5 text-[11px] font-medium leading-snug text-ink-500 dark:border-granite-600 dark:bg-granite-900 dark:text-granite-400"
        >
          Mentor không khuyến nghị mua/bán — chỉ giúp bạn phản biện quyết định của mình.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {mentor.lastError !== null && (
          <div className="rounded-lg border border-mkt-down/40 bg-mkt-down/10 px-3 py-2 text-xs text-mkt-down dark:text-mkt-down-400">
            {mentor.lastError}
          </div>
        )}

        {!mentor.isConnected && (
          <div className="rounded-lg border border-brand-500/40 bg-brand-500/10 px-3 py-2 text-xs text-brand-700 dark:text-brand-300">
            Chưa kết nối được tới Mentor. Đảm bảo backend WebSocket đang chạy, sau đó tải lại trang.
          </div>
        )}

        {mentor.messages.length === 0 ? (
          <div className="py-8 text-center">
            <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-300/40 bg-gradient-to-b from-amber-100 to-amber-200/80 p-1.5 shadow-sm dark:border-amber-500/30 dark:from-amber-950/60 dark:to-amber-900/40">
              <CapybaraMiniAvatar className="h-11 w-11 border-0 bg-transparent shadow-none" />
            </div>
            <h3 className="text-sm font-bold text-ink-900 dark:text-slip">
              Chào bạn, mình là Capia 🍊
            </h3>
            <p className="mx-auto mt-1 max-w-sm text-xs text-ink-500 dark:text-granite-400">
              Chuột lang AI Mentor tài chính. Chọn một gợi ý bên dưới hoặc đặt câu hỏi bất kỳ để rèn luyện tư duy đầu tư nhé!
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS_BY_MODE[mode].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="rounded-full border border-line bg-paper px-3 py-1 text-xs text-ink-600 transition-colors hover:border-accent-400 hover:text-accent-700 dark:border-granite-600 dark:bg-granite-900 dark:text-granite-300 dark:hover:border-accent-400 dark:hover:text-accent-300"
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
                  "flex gap-2.5",
                  message.role === "user" ? "justify-end" : "items-start justify-start",
                )}
              >
                {message.role === "mentor" && (
                  <CapybaraMiniAvatar className="mt-0.5 h-7 w-7" />
                )}
                {message.role === "mentor" && message.kind !== undefined ? (
                  <MentorCard
                    message={message}
                    onChipAsk={(chip) => {
                      setDraft(chip);
                      inputRef.current?.focus();
                    }}
                    onSendChip={(chip) => {
                      mentor.sendAsk(`${chip} là gì?`, { mode: "concept" });
                    }}
                  />
                ) : (
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                      message.role === "user"
                        ? "rounded-br-md bg-brand-500 text-granite-950 shadow-card"
                        : "rounded-bl-md border border-line bg-paper text-ink-800 dark:border-granite-700 dark:bg-granite-900 dark:text-slip",
                    )}
                  >
                    {message.content}
                    {message.role === "mentor" && mentor.isStreaming && (
                      <span className="ml-1 inline-block h-3.5 w-1 animate-pulse bg-brand-600 align-text-bottom dark:bg-brand-400" />
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={listRef} />
          </div>
        )}
      </div>

      <div className="border-t border-line px-5 py-3 dark:border-granite-700">
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!draft.trim() || mentor.isStreaming) {
              return;
            }
            mentor.sendAsk(draft, {
              mode,
              selected_symbol: effectiveSymbol,
            });
            setDraft("");
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              effectiveSymbol !== undefined
                ? `Hỏi Mentor về ${effectiveSymbol}...`
                : "Hỏi Mentor bất cứ điều gì về tài chính..."
            }
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
    </div>
  );
}

/** Render 1 card structured (concept/strategy/challenge) cho tin nhắn mentor. */
function MentorCard({
  message,
  onChipAsk,
  onSendChip,
}: {
  message: MentorMessage;
  onChipAsk: (chip: string) => void;
  onSendChip: (chip: string) => void;
}) {
  if (message.kind === "concept" && message.concept !== undefined) {
    return (
      <ConceptCard
        concept={message.concept}
        followup={message.content}
        onChipAsk={onChipAsk}
        onSendChip={onSendChip}
      />
    );
  }
  if (message.kind === "strategy" && message.strategy !== undefined) {
    return <StrategyCard strategy={message.strategy} />;
  }
  if (message.kind === "challenge" && message.challenge !== undefined) {
    return <ChallengeCard challenge={message.challenge} />;
  }
  // Fallback an toàn: giống bubble text.
  return (
    <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-line bg-paper px-4 py-2.5 text-sm leading-relaxed text-ink-800 dark:border-granite-700 dark:bg-granite-900 dark:text-slip">
      {message.content}
    </div>
  );
}

function ConceptCard({
  concept,
  followup,
  onChipAsk,
  onSendChip,
}: {
  concept: ConceptReply;
  followup: string;
  onChipAsk: (chip: string) => void;
  onSendChip: (chip: string) => void;
}) {
  return (
    <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-accent-500/30 bg-paper p-4 text-sm leading-relaxed shadow-card dark:border-accent-400/30 dark:bg-granite-900">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-black text-accent-700 dark:text-accent-300">
          {concept.name}
        </h4>
        {concept.category !== undefined && (
          <span className="stamp">{concept.category}</span>
        )}
      </div>
      <p className="mt-2 text-ink-800 dark:text-slip">{concept.definition}</p>
      {concept.formula !== undefined && concept.formula !== "" && (
        <p className="mt-2 rounded-lg border border-dashed border-line bg-paper px-3 py-1.5 font-mono text-xs text-accent-700 dark:border-granite-700 dark:text-accent-300">
          {concept.formula}
        </p>
      )}
      {concept.explanation !== undefined && concept.explanation !== "" && (
        <p className="mt-2 text-xs text-ink-500 dark:text-granite-400">
          {concept.explanation}
        </p>
      )}
      {concept.example !== undefined && concept.example !== "" && (
        <p className="mt-2 text-xs text-ink-600 dark:text-granite-300">
          <span className="font-semibold">Ví dụ: </span>
          {concept.example}
        </p>
      )}
      {concept.interpretation !== undefined && concept.interpretation !== "" && (
        <p className="mt-2 text-xs italic text-ink-500 dark:text-granite-400">
          {concept.interpretation}
        </p>
      )}
      {concept.related.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-ink-400 dark:text-granite-500">Liên quan:</span>
          {concept.related.map((term) => (
            <button
              key={term}
              type="button"
              onClick={() => onChipAsk(term)}
              onDoubleClick={() => onSendChip(term)}
              className="rounded-full border border-line bg-paper px-2 py-0.5 text-xs text-ink-600 transition-colors hover:border-accent-500 hover:text-accent-700 dark:border-granite-600 dark:bg-granite-900 dark:text-granite-300 dark:hover:border-accent-400 dark:hover:text-accent-300"
              title={`Nhấn 1 lần để điền, 2 lần để hỏi "${term} là gì?"`}
            >
              {term}
            </button>
          ))}
        </div>
      )}
      {followup.trim() !== "" && (
        <p className="mt-3 border-t border-line pt-2 text-xs font-medium text-ink-600 dark:border-granite-700 dark:text-granite-300">
          {followup}
        </p>
      )}
    </div>
  );
}

function StrategyCard({ strategy }: { strategy: StrategyReply }) {
  return (
    <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-mkt-up/30 bg-paper p-4 text-sm leading-relaxed shadow-card dark:border-mkt-up/30 dark:bg-granite-900">
      <h4 className="flex items-center gap-1.5 text-sm font-black text-mkt-up-dark dark:text-mkt-up-400">
        <IconTrendUp className="h-4 w-4" />
        {strategy.framework_name}
      </h4>
      <div className="mt-3 space-y-2 text-xs">
        <Row label="Tiêu chí">
          <ul className="list-disc space-y-1 pl-4">
            {strategy.criteria.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Row>
        <Row label="Phân bổ vốn">{strategy.allocation_rule}</Row>
        <Row label="Quản trị rủi ro">{strategy.risk_rule}</Row>
        {strategy.how_to_trade.length > 0 && (
          <Row label="Cách triển khai">
            <ul className="list-disc space-y-1 pl-4">
              {strategy.how_to_trade.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Row>
        )}
        {strategy.questions.length > 0 && (
          <Row label="Câu hỏi phản biện">
            <ul className="list-disc space-y-1 pl-4">
              {strategy.questions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Row>
        )}
      </div>
    </div>
  );
}

function ChallengeCard({
  challenge,
}: {
  challenge: import("@/types/websocket").MentorChallenge;
}) {
  return (
    <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-mkt-down/30 bg-paper p-4 text-sm leading-relaxed shadow-card dark:border-mkt-down/30 dark:bg-granite-900">
      <div className="flex items-center justify-between gap-2">
        <h4 className="flex items-center gap-1.5 text-sm font-black text-mkt-down dark:text-mkt-down-400">
          <IconRisk className="h-4 w-4" />
          Phản biện quyết định giao dịch
        </h4>
        {challenge.risk_flags.length > 0 && (
          <span className="stamp stamp-danger">
            {challenge.risk_flags.length} rủi ro
          </span>
        )}
      </div>
      {challenge.risk_flags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {challenge.risk_flags.map((flag) => (
            <span
              key={flag}
              className="rounded-full border border-mkt-down/40 bg-mkt-down/5 px-2 py-0.5 text-[11px] text-mkt-down dark:text-mkt-down-400"
            >
              {flag}
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 space-y-2 text-xs">
        <ul className="list-disc space-y-1 pl-4">
          {challenge.questions.map((item) => (
            <li key={item} className="text-ink-700 dark:text-granite-200">
              {item}
            </li>
          ))}
        </ul>
        {challenge.coaching_tip.trim() !== "" && (
          <p className="rounded-lg border border-dashed border-line px-3 py-1.5 text-ink-500 dark:border-granite-700 dark:text-granite-400">
            <span className="font-semibold">Bài tập: </span>
            {challenge.coaching_tip}
          </p>
        )}
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line px-3 py-2 text-ink-700 dark:border-granite-700 dark:text-granite-200">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-400 dark:text-granite-500">
        {label}
      </span>
      {children}
    </div>
  );
}

/** Avatar Capybara mini siêu cute đồng bộ linh vật 3D */
export function CapybaraMiniAvatar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full border border-amber-300/50 bg-gradient-to-b from-amber-100 to-amber-200/90 p-0.5 shadow-sm dark:border-amber-500/40 dark:from-amber-950/70 dark:to-amber-900/50",
        className,
      )}
      title="Capia — AI Mentor"
    >
      <svg viewBox="0 0 120 120" className="h-full w-full drop-shadow-sm" aria-hidden="true">
        {/* Tai */}
        <ellipse cx="36" cy="38" rx="7" ry="8" fill="#8A5428" />
        <ellipse cx="36" cy="38" rx="4" ry="5" fill="#F2A79D" />
        <ellipse cx="84" cy="38" rx="7" ry="8" fill="#8A5428" />
        <ellipse cx="84" cy="38" rx="4" ry="5" fill="#F2A79D" />
        {/* Đầu */}
        <rect x="34" y="32" width="52" height="42" rx="18" fill="#C88746" />
        <circle cx="36" cy="56" r="10" fill="#C88746" />
        <circle cx="84" cy="56" r="10" fill="#C88746" />
        {/* Má hồng đào */}
        <circle cx="38" cy="58" r="4.5" fill="#FFAAA6" opacity="0.9" />
        <circle cx="82" cy="58" r="4.5" fill="#FFAAA6" opacity="0.9" />
        {/* Mõm & mũi */}
        <rect x="42" y="48" width="36" height="24" rx="10" fill="#FDF1DC" />
        <rect x="53" y="49" width="14" height="8" rx="3.5" fill="#352014" />
        <path d="M57 63 Q60 66 63 63" stroke="#352014" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        {/* Mắt to tròn có đốm sáng */}
        <ellipse cx="46" cy="46" rx="4.5" ry="5" fill="#1C140E" />
        <circle cx="44.5" cy="44.5" r="1.8" fill="#FFFFFF" />
        <ellipse cx="74" cy="46" rx="4.5" ry="5" fill="#1C140E" />
        <circle cx="72.5" cy="44.5" r="1.8" fill="#FFFFFF" />
        {/* Quả cam yuzu trên đầu */}
        <ellipse cx="60" cy="22" rx="11" ry="9.5" fill="#FF9500" />
        <line x1="60" y1="13" x2="60" y2="9" stroke="#5D4037" strokeWidth="2" strokeLinecap="round" />
        <ellipse cx="65" cy="11" rx="4.5" ry="2" fill="#4CAF50" transform="rotate(20 65 11)" />
      </svg>
    </div>
  );
}