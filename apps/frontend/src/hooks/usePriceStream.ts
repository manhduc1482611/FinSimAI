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
import { computeChange, nextSimulatedPrice } from "@/utils/priceSimulator";

const MAX_TICKS = 400;
// Demo mode: không có WebSocket → tự mô phỏng giá bằng polling REST.
const DEMO_POLL_MS = 2000; // cũng là chu kỳ stable trong Apps Script
// Fallback mô phỏng local khi chưa có realtime (chưa đăng nhập / backend không feed).
const SIM_FALLBACK_MS = 3000;
// Số tick sau đó fallback khôi phục nếu WS quay lại.
const FALLBACK_WARMUP_MS = 4000;

export interface UsePriceStreamResult {
  /** Tick giá mới nhất (null khi chưa có dữ liệu / chưa đăng nhập). */
  snapshot: PriceTick | null;
  /** Lịch sử tick đã nhận (bounded), đã đánh dấu thời gian nhận. */
  ticks: TimedPriceTick[];
  status: WsConnectionStatus;
  lastError: string | null;
}

export function usePriceStream(symbol: string, initialBase?: number): UsePriceStreamResult {
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
  // Bộ nhớ basePrice/step cho fallback mô phỏng local.
  const simBaseRef = useRef<number>(100);
  const baseReadyRef = useRef<boolean>(false);
  const simStepRef = useRef<number>(0);
  const lastLiveRef = useRef<number>(0);
  const lastSimulatedPriceRef = useRef<number>(0);

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

  // Cập nhật base ngay nếu có giá khởi tạo (ví dụ: giá đã tải trong danh sách công ty).
  useEffect(() => {
    setSnapshot(null);
    setTicks([]);
    lastLiveRef.current = 0;
    simStepRef.current = 0;
    lastSimulatedPriceRef.current = 0;
    const base = Number(initialBase);
    baseReadyRef.current = Number.isFinite(base) && base > 0;
    if (baseReadyRef.current) {
      simBaseRef.current = base;
      lastSimulatedPriceRef.current = base;
    }
  }, [symbol, initialBase]);

  // Cập nhật live timestamp mỗi khi nhận tick thật.
  const markLive = () => {
    lastLiveRef.current = Date.now();
  };

  // Profile thật của công ty (để fallback dựa trên giá gốc).
  useEffect(() => {
    let cancelled = false;
    async function loadCompany() {
      try {
        // Demo mode: Apps Script hiện không xử lý `tick` cùng `search`,
        // nên dùng query tối giản (trả đủ list, giá có thể đã mô phỏng sẵn).
        const query = isDemoMode() ? { limit: 100 } : { limit: 500, search: symbol };
        const res = await listCompanies(query);
        const company = res.items.find((c) => c.symbol === symbol);
        if (company && !cancelled) {
          const price = parseFloat(company.current_price);
          if (Number.isFinite(price) && price > 0) {
            simBaseRef.current = price;
            lastSimulatedPriceRef.current =
              lastSimulatedPriceRef.current > 0 ? lastSimulatedPriceRef.current : price;
            baseReadyRef.current = true;
          }
        }
      } catch {
        // bỏ qua — fallback sẽ dùng default.
      }
    }
    void loadCompany();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Demo mode: tự sinh tick cục bộ từ base (giá đã tải) — không cần poll nhiều,
  // tránh làm nghẽn Apps Script. Bắt đầu ngay khi đã có base khả dụng.
  useEffect(() => {
    if (!isDemo) {
      return;
    }
    let cancelled = false;
    let alive = false;
    let timer: number | undefined;

    const tickNow = () => {
      if (cancelled) {
        return;
      }
      const base = simBaseRef.current;
      const last = lastSimulatedPriceRef.current;
      const price =
        last > 0 ? nextSimulatedPrice(symbol, last, simStepRef.current++) : base;
      lastSimulatedPriceRef.current = price;
      const { change, changePct } = computeChange(price, base);
      const tick: PriceTick = {
        symbol,
        company_id: "",
        name: symbol,
        sector: null,
        price,
        open: base,
        high: Math.max(base, price),
        low: Math.min(base, price),
        prev_close: base,
        change,
        change_pct: changePct,
        market_cap: null,
        sim_day: 1,
        simulated_at: new Date().toISOString(),
      };
      setSnapshot(tick);
      setTicks((prev) => {
        const next =
          prev.length >= MAX_TICKS ? prev.slice(prev.length - MAX_TICKS + 1) : prev;
        return [...next, { tick, receivedAt: Date.now() }];
      });
    };

    const start = () => {
      if (cancelled || alive) {
        return;
      }
      if (baseReadyRef.current) {
        alive = true;
        tickNow();
        timer = window.setInterval(tickNow, DEMO_POLL_MS);
      } else {
        window.setTimeout(start, 250);
      }
    };

    start();
    return () => {
      cancelled = true;
      alive = false;
      if (timer !== undefined) {
        window.clearInterval(timer);
      }
    };
  }, [isDemo, symbol]);

  // Fallback mô phỏng local: nếu sau một khoảng im lặng vẫn không có tick thật,
  // tự sinh tick để thị trường luôn "sống". Khôi phục ngay khi có realtime trở lại.
  useEffect(() => {
    if (isDemo) {
      return;
    }
    let cancelled = false;
    const timer = window.setInterval(() => {
      if (cancelled) {
        return;
      }
      const hasFreshLive = Date.now() - lastLiveRef.current < FALLBACK_WARMUP_MS;
      // Chỉ fallback khi chưa có dữ liệu thật hoặc realtime đã ngừng lâu.
      if (hasFreshLive) {
        return;
      }
      const price =
        lastSimulatedPriceRef.current > 0
          ? nextSimulatedPrice(symbol, lastSimulatedPriceRef.current, simStepRef.current++)
          : simBaseRef.current;
      lastSimulatedPriceRef.current = price;
      const { change, changePct } = computeChange(price, simBaseRef.current);
      const tick: PriceTick = {
        symbol,
        company_id: "",
        name: symbol,
        sector: null,
        price,
        open: simBaseRef.current,
        high: Math.max(simBaseRef.current, price),
        low: Math.min(simBaseRef.current, price),
        prev_close: simBaseRef.current,
        change,
        change_pct: changePct,
        market_cap: null,
        sim_day: 1,
        simulated_at: new Date().toISOString(),
      };
      setSnapshot(tick);
      setTicks((prev) => {
        const next =
          prev.length >= MAX_TICKS ? prev.slice(prev.length - MAX_TICKS + 1) : prev;
        return [...next, { tick, receivedAt: Date.now() }];
      });
    }, SIM_FALLBACK_MS);
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
      markLive();
      // Cập nhật base theo tick thật để fallback khớp.
      if (Number.isFinite(message.data.price) && message.data.price > 0) {
        simBaseRef.current = message.data.prev_close || message.data.price;
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
