/**
 * useTrade — gom các hành động của `useTradeStore` + làm mới real-time qua
 * WebSocket `/ws/trades` (trade_fill / order_update → refresh portfolio & orders).
 */
import { useEffect, useState } from "react";

import { useWebSocket } from "@/hooks/useWebSocket";
import { getWsBaseUrl } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { useAuthStore } from "@/store/useAuthStore";
import { useTradeStore } from "@/store/useTradeStore";

export function useTrade() {
  const portfolio = useTradeStore((state) => state.portfolio);
  const orders = useTradeStore((state) => state.orders);
  const status = useTradeStore((state) => state.status);
  const orderStatus = useTradeStore((state) => state.orderStatus);
  const cancelStatus = useTradeStore((state) => state.cancelStatus);
  const error = useTradeStore((state) => state.error);
  const lastOrder = useTradeStore((state) => state.lastOrder);
  const fetchPortfolio = useTradeStore((state) => state.fetchPortfolio);
  const listOrders = useTradeStore((state) => state.listOrders);
  const submitOrder = useTradeStore((state) => state.submitOrder);
  const cancelOrder = useTradeStore((state) => state.cancelOrder);

  const user = useAuthStore((state) => state.user);
  const [ticketUrl, setTicketUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setTicketUrl(null);
      return;
    }
    let cancelled = false;
    fetchWsTicket()
      .then((ticket) => {
        if (cancelled) {
          return;
        }
        setTicketUrl(`${getWsBaseUrl()}/ws/trades?ticket=${encodeURIComponent(ticket.ticket)}`);
      })
      .catch(() => {
        // Không có WS realtime → vẫn làm việc bằng REST refresh.
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useWebSocket({
    url: ticketUrl,
    enabled: ticketUrl !== null,
    onMessage: (message) => {
      if (message.type === "trade_fill" || message.type === "order_update") {
        void useTradeStore.getState().fetchPortfolio();
        void useTradeStore.getState().listOrders();
      }
    },
  });

   useEffect(() => {
     if (!user) return;
     void fetchPortfolio();
     void listOrders();
   }, [user, fetchPortfolio, listOrders]);

  return {
    portfolio,
    orders,
    status,
    orderStatus,
    cancelStatus,
    error,
    lastOrder,
    refresh: () => {
      void fetchPortfolio();
      void listOrders();
    },
    submitOrder,
    cancelOrder,
  };
}
