/**
 * usePriceStream — kết nối WebSocket `/ws/prices` và theo dõi một symbol.
 *
 * - Lấy single-use ticket qua REST (bắt buộc xác thực) rồi mở socket.
 * - Khi socket mở → gửi `subscribe` tới channel `prices:{SYMBOL}`.
 * - Nhận `price_snapshot` (ngay sau subscribe) + `price_tick` (mỗi khi giá đổi).
 * - Giữ `snapshot` mới nhất + `ticks` (lịch sử có đánh dấu thời gian nhận, bounded).
 *
 * Đổi symbol → hủy kết nối cũ, xin ticket mới, reset dữ liệu, kết nối lại.
 */
import { useEffect, useRef, useState } from "react";

import { useWebSocket, type WsConnectionStatus } from "@/hooks/useWebSocket";
import { getWsBaseUrl, isDemoMode } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { listCompanies } from "@/services/companies";
import { useAuthStore } from "@/store/useAuthStore";
import type { PriceTick } from "@/types/websocket";
import type { TimedPriceTick } from "@/utils/candles";

const MAX_TICKS = 400;
// Demo mode: không có WebSocket → tự mô phỏng giá bằng polling REST.
const DEMO_POLL_MS = 2000; // cũng là chu kỳ stable trong Apps Script

export interface UsePriceStreamResult {
  /** Tick giá mới nhất (null khi chưa có dữ liệu / chưa đăng nhập). */
  snapshot: PriceTick | null;
  /** Lịch sử tick đã nhận (bounded), đã đánh dấu thời gian nhận. */
  ticks: TimedPriceTick[];
  status: WsConnectionStatus;
  lastError: string | null;
}

export function usePriceStream(symbol: string): UsePriceStreamResult {
  const user = useAuthStore((state) => state.user);
  const isDemo = isDemoMode();
  const [ticketUrl, setTicketUrl] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<PriceTick | null>(null);
  const [ticks, setTicks] = useState<TimedPriceTick[]>([]);

  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;
  const sendRef = useRef<((message: { action: "subscribe"; channels: string[] }) => void) | null>(
    null,
  );

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

  useEffect(() => {
    setSnapshot(null);
    setTicks([]);
  }, [symbol]);

  // Demo mode: không backend WS → poll REST, dựng PriceTick từ company hiện tại.
  useEffect(() => {
    if (!isDemo) {
      return;
    }
    let cancelled = false;
    async function poll() {
      try {
        const res = await listCompanies({ tick: 1, limit: 500, search: symbol });
        const company = res.items.find((c) => c.symbol === symbol);
        if (!company) {
          return;
        }
        const price = parseFloat(company.current_price);
        const tick: PriceTick = {
          symbol: company.symbol,
          company_id: company.id,
          name: company.name,
          sector: company.sector,
          price,
          open: price,
          high: price,
          low: price,
          prev_close: price,
          change: 0,
          change_pct: 0,
          market_cap: company.market_cap ? parseFloat(company.market_cap) : null,
          sim_day: 1,
          simulated_at: new Date().toISOString(),
        };
        if (cancelled) {
          return;
        }
        setSnapshot(tick);
        setTicks((prev) => {
          const next =
            prev.length >= MAX_TICKS ? prev.slice(prev.length - MAX_TICKS + 1) : prev;
          return [...next, { tick, receivedAt: Date.now() }];
        });
      } catch {
        // bỏ qua lỗi tạm thời, đợi poll lần sau
      }
    }
    void poll();
    const timer = window.setInterval(poll, DEMO_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isDemo, symbol]);

  const { status, lastError, sendMessage } = useWebSocket({
    url: ticketUrl,
    enabled: ticketUrl !== null,
    onOpen: () => {
      sendRef.current?.({ action: "subscribe", channels: [`prices:${symbolRef.current}`] });
    },
    onMessage: (message) => {
      if (message.type !== "price_tick" && message.type !== "price_snapshot") {
        return;
      }
      if (message.data.symbol !== symbolRef.current) {
        return;
      }
      setSnapshot(message.data);
      setTicks((prev) => {
        const next = prev.length >= MAX_TICKS ? prev.slice(prev.length - MAX_TICKS + 1) : prev;
        return [...next, { tick: message.data, receivedAt: Date.now() }];
      });
    },
  });

  sendRef.current = sendMessage;

  return { snapshot, ticks, status, lastError };
}
