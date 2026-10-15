/**
 * usePriceStream — theo dõi giá một symbol bằng DỮ LIỆU THẬT từ backend.
 *
 * - Chế độ thường (WS có sẵn): lấy single-use ticket qua REST rồi mở socket
 *   `/ws/prices`; nhận `price_snapshot` (ngay sau subscribe) + `price_tick`
 *   (mỗi khi giá đổi). KHÔNG tự sinh giá — khi chưa có tick thật thì
 *   ``snapshot = null`` và UI hiển thị trạng thái chờ/mất kết nối.
 * - Demo mode (NEXT_PUBLIC_DEMO_MODE=1): Apps Script không có WebSocket → poll
 *   REST ``/companies`` lấy ``current_price`` thật của backend (backend demo tự
 *   mô phỏng giá ở phía máy chủ). Giá vẫn là dữ liệu backend, frontend không
 *   bịa bất kỳ tick/lịch sử giá nào. ``source = "poll"`` để UI phân biệt.
 *
 * Không còn mã sinh giá ngẫu nhiên phía client (priceSimulator bị xoá: nó từng
 * bịa tick khi WS im lặng và bịa 90 ngày OHLC lịch sử — review P0 #8).
 */
import { useEffect, useRef, useState } from "react";

import { useWebSocket, type WsConnectionStatus } from "@/hooks/useWebSocket";
import { getWsBaseUrl, isDemoMode } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { listCompanies } from "@/services/companies";
import { useAuthStore } from "@/store/useAuthStore";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import type { PriceTick, WsClientMessage } from "@/types/websocket";
import type { TimedPriceTick } from "@/utils/candles";

const MAX_TICKS = 400;
// Demo mode: Apps Script không có WebSocket → poll REST lấy giá thật. Giữ chu kỳ
// vừa phải để không hụt quota request/ngày của Apps Script.
const DEMO_POLL_MS = 5000;

/** Nguồn dữ liệu giá đang hiển thị. */
export type PriceSource = "live" | "poll" | "none";

export interface UsePriceStreamResult {
  /** Tick giá mới nhất (null khi chưa có dữ liệu thật / chưa đăng nhập). */
  snapshot: PriceTick | null;
  /** Lịch sử tick đã nhận (bounded), đã đánh dấu thời gian nhận. */
  ticks: TimedPriceTick[];
  status: WsConnectionStatus;
  lastError: string | null;
  /** live = tick WebSocket; poll = giá thật backend demo qua REST; none = chưa có. */
  source: PriceSource;
}

/** Dựng snapshot từ giá thật của backend demo (Apps Script không trả OHLC/change). */
function buildPollSnapshot(symbol: string, company: CompanyResponse): PriceTick {
  const price = parseFloat(company.current_price);
  const safePrice = Number.isFinite(price) && price > 0 ? price : 0;
  return {
    symbol,
    company_id: company.id,
    name: company.name,
    sector: company.sector,
    price: safePrice,
    open: safePrice,
    high: safePrice,
    low: safePrice,
    prev_close: safePrice,
    change: 0,
    change_pct: 0,
    market_cap:
      company.market_cap !== null && company.market_cap !== undefined
        ? parseFloat(company.market_cap)
        : null,
    sim_day: 1,
    simulated_at: new Date().toISOString(),
  };
}

export function usePriceStream(symbol: string): UsePriceStreamResult {
  const user = useAuthStore((state) => state.user);
  const isDemo = isDemoMode();
  const [ticketUrl, setTicketUrl] = useState<string | null>(null);
  // snapshot gây re-render có chủ đích: giá hiển thị cần cập nhật UI.
  const [snapshot, setSnapshot] = useState<PriceTick | null>(null);
  // ticks lưu bằng state để PriceChart cũng nhận đúng vòng đời React.
  // Components chỉ cần snapshot (TradePanel, giá header) nên dùng selector riêng.
  const [ticks, setTicks] = useState<TimedPriceTick[]>([]);

  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;
  const sendRef = useRef<((message: WsClientMessage) => void) | null>(null);

  // Đổi symbol → xoá dữ liệu cũ, không để nến/giá của mã trước loé lên.
  useEffect(() => {
    setSnapshot(null);
    setTicks([]);
  }, [symbol]);

  // Xia ticket (chỉ chế độ thường — demo mode không có WebSocket).
  useEffect(() => {
    if (isDemoMode() || !user) {
      setTicketUrl(null);
      return;
    }
    let cancelled = false;
    setTicketUrl(null);
    fetchWsTicket()
      .then((ticket) => {
        if (cancelled) {
          return;
        }
        const url = `${getWsBaseUrl()}/ws/prices?ticket=${encodeURIComponent(
          ticket.ticket,
        )}&symbol=${encodeURIComponent(symbol)}`;
        setTicketUrl(url);
      })
      .catch(() => {
        // Không lấy được ticket → giữ trạng thái idle, terminal hiển thị gợi ý đăng nhập.
      });
    return () => {
      cancelled = true;
    };
  }, [isDemo, user, symbol]);

  // Demo mode: poll REST giá THẬT của backend (không sinh tick phía client).
  useEffect(() => {
    if (!isDemo) {
      return;
    }
    let cancelled = false;
    const pollNow = async (): Promise<void> => {
      if (cancelled) {
        return;
      }
      try {
        const res = await listCompanies({ limit: 100 });
        const company = res.items.find((item) => item.symbol === symbolRef.current);
        if (company !== undefined && !cancelled) {
          setSnapshot(buildPollSnapshot(company.symbol, company));
        }
      } catch {
        // Giữ giá gần nhất — lỗi mạng/hết quota không làm vỡ terminal.
      }
    };
    void pollNow();
    const timer = window.setInterval(() => void pollNow(), DEMO_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isDemo, symbol]);

  const { status, lastError, sendMessage } = useWebSocket({
    url: ticketUrl,
    enabled: ticketUrl !== null,
    onOpen: () => {
      sendRef.current?.(
        { action: "subscribe", channels: [`prices:${symbolRef.current}`] } satisfies WsClientMessage,
      );
    },
    onMessage: (message) => {
      if (message.type !== "price_tick" && message.type !== "price_snapshot") {
        return;
      }
      if (message.data.symbol !== symbolRef.current) {
        return;
      }
      // snapshot update: trigger re-render để component hiển thị giá mới nhất.
      setSnapshot(message.data);
      // ticks update: chỉ PriceChart cần, sẽ re-render PriceChart riêng.
      // Các component chỉ đọc snapshot sẽ KHÔNG re-render thêm vì ticks
      // ở trạng thái riêng của hook — chỉ component mount hook mới nhận ticks.
      setTicks((prev) => {
        const next = prev.length >= MAX_TICKS ? prev.slice(prev.length - MAX_TICKS + 1) : prev;
        return [...next, { tick: message.data, receivedAt: Date.now() }];
      });
    },
  });

  sendRef.current = sendMessage;

  const source: PriceSource = snapshot === null ? "none" : isDemo ? "poll" : "live";

  return { snapshot, ticks, status, lastError, source };
}