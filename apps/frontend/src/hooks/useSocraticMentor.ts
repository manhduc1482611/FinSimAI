/**
 * useSocraticMentor — kết nối WS tới `/ws/mentor` (qua ticket single-use) và
 * điều phối luồng chat: câu hỏi → stream chunk → kết thúc (3 chế độ v2.0).
 *
 * Trạng thái tin nhắn nằm trong `useMentorStore`; hook chỉ quản lý socket và
 * truyền `trade_context` (mode + selected_symbol) — không gửi bất kỳ số liệu
 * tài chính nào từ client (backend tự lấy từ DB qua user_id).
 */
import { useEffect, useState } from "react";

import { getWsBaseUrl, isDemoMode } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { reportTaskEvent } from "@/services/tasks";
import { useAuthStore } from "@/store/useAuthStore";
import { useMentorStore } from "@/store/useMentorStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { MentorMode, TradeContext } from "@/types/websocket";
import {
  lookupConceptLocal,
  matchKnowledgeLocal,
} from "@/utils/knowledge_matcher";
import type { MentorMessage } from "@/store/useMentorStore";

export interface SocraticMentor {
  messages: ReturnType<typeof useMentorStore.getState>["messages"];
  isStreaming: boolean;
  isReady: boolean;
  isConnected: boolean;
  lastError: string | null;
  sendAsk: (text: string, tradeContext?: Partial<TradeContext>) => void;
  sendCancel: () => void;
  reset: () => void;
}

export function useSocraticMentor(): SocraticMentor {
  const user = useAuthStore((state) => state.user);
  const messages = useMentorStore((state) => state.messages);
  const isStreaming = useMentorStore((state) => state.isStreaming);
  const isReady = useMentorStore((state) => state.isReady);
  const lastError = useMentorStore((state) => state.lastError);

  const [ticketUrl, setTicketUrl] = useState<string | null>(null);

  useEffect(() => {
    if (isDemoMode() || !user) {
      setTicketUrl(null);
      useMentorStore.getState().setReady(isDemoMode());
      return;
    }
    let cancelled = false;
    fetchWsTicket()
      .then((ticket) => {
        if (cancelled) {
          return;
        }
        setTicketUrl(`${getWsBaseUrl()}/ws/mentor?ticket=${encodeURIComponent(ticket.ticket)}`);
      })
      .catch(() => {
        if (!cancelled) {
          useMentorStore
            .getState()
            .setError("Không lấy được ticket WebSocket — kiểm tra phiên đăng nhập.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const { status: wsStatus, sendMessage } = useWebSocket({
    url: ticketUrl,
    enabled: ticketUrl !== null,
    onMessage: (message) => {
      useMentorStore.getState().onServerMessage(message);
    },
    onClose: () => {
      useMentorStore.getState().setReady(false);
    },
  });

  const sendAsk = (text: string, tradeContext?: Partial<TradeContext>): void => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    const store = useMentorStore.getState();

    // Mode mặc định từ store; nếu gọi với tradeContext khác thì dùng cái đó.
    const mode = tradeContext?.mode ?? store.tradeContext.mode;
    const selectedSymbol =
      tradeContext?.selected_symbol ??
      store.tradeContext.selected_symbol;

    // Demo mode: không có WebSocket → trả lời bằng glossary local.
    if (isDemoMode()) {
store.setTradeContext({ mode, selected_symbol: selectedSymbol });
      store.pushUserMessage(trimmed);
      void reportTaskEvent("mentor_chat").catch(() => {
        // bỏ qua lỗi tracking
      });
      // Simulate nhỏ để có cảm giác stream.
      setTimeout(() => {
        const reply = buildDemoMentorReply(trimmed, mode, selectedSymbol);
        useMentorStore.setState({ isStreaming: false });
        useMentorStore.getState().pushMentorMessage(reply);
      }, 600);
      return;
    }

    if (wsStatus !== "open") {
      store.setError("Chưa kết nối được tới Mentor — vui lòng thử lại sau giây lát.");
      return;
    }
    store.setTradeContext({ mode, selected_symbol: selectedSymbol });
    store.pushUserMessage(trimmed);
    void reportTaskEvent("mentor_chat").catch(() => {
      // Báo sự kiện thưởng lỗi không ảnh hưởng luồng chat.
    });
    const sessionId = useMentorStore.getState().sessionId;
    if (sessionId) {
      sendMessage({
        action: "ask",
        message: trimmed,
        session_id: sessionId,
        trade_context: { mode, selected_symbol: selectedSymbol },
      });
    }
  };

  const sendCancel = (): void => {
    const store = useMentorStore.getState();
    const sessionId = store.sessionId;
    if (sessionId && wsStatus === "open") {
      sendMessage({ action: "cancel", session_id: sessionId });
    }
    store.setReady(false);
  };

  const reset = (): void => {
    useMentorStore.getState().resetSession();
  };

  return {
    messages,
    isStreaming,
    isReady: isDemoMode() ? true : isReady,
    isConnected: isDemoMode() ? true : wsStatus === "open",
    lastError,
    sendAsk,
    sendCancel,
    reset,
  };
}

/** Dựng phản hồi demo cho Mentor theo mode (dùng glossary local & template chiến lược). */
function buildDemoMentorReply(
  text: string,
  mode: MentorMode,
  selectedSymbol: string | undefined,
): Omit<MentorMessage, "id" | "ts"> {
  const intro = "Mentor:";

  if (mode === "concept") {
    const match = lookupConceptLocal(text);
    if (match !== null) {
      return {
        role: "mentor",
        content: match.interpretation,
        kind: "concept",
        concept: {
          id: match.id,
          name: match.concept,
          definition: match.definition,
          explanation: match.explanation,
          example: match.example,
          formula: match.formula,
          interpretation: match.interpretation,
          related: match.related,
          followup_question:
            "Bạn hiểu cách áp dụng khái niệm này vào một tình huống cụ thể của mình không? Hãy thử mô tả quyết định bạn đang cân nhắc.",
        },
      };
    }

    const lower = text.toLowerCase();
    if (
      lower.includes("lua ga") ||
      lower.includes("fomo") ||
      lower.includes("kiem chung") ||
      lower.includes("mxh") ||
      lower.includes("bai viet") ||
      lower.includes("bai dang")
    ) {
      const fomoConcept = lookupConceptLocal("fomo");
      return {
        role: "mentor",
        content: `Khi đọc các bài viết khuyến nghị trên mạng xã hội, bạn nên giữ tư duy phản biện độc lập:\n\n1. Phát hiện tâm lý bầy đàn & FOMO: Các bài viết dùng từ ngữ giật gân thường nhằm kích hoạt lòng tham để xả hàng.\n2. Đối chiếu số liệu: Luôn kiểm tra báo cáo tài chính (doanh thu, lợi nhuận ròng, P/E, ROE) trên trang Doanh nghiệp thay vì tin vào tin đồn.\n3. Kỷ luật giao dịch: Không bao giờ mua theo cảm xúc nếu chưa có kế hoạch dừng lỗ rõ ràng.`,
        kind: fomoConcept ? "concept" : undefined,
        concept: fomoConcept
          ? {
              id: fomoConcept.id,
              name: fomoConcept.concept,
              definition: fomoConcept.definition,
              explanation: fomoConcept.explanation,
              example: fomoConcept.example,
              formula: fomoConcept.formula,
              interpretation: fomoConcept.interpretation,
              related: fomoConcept.related,
              followup_question:
                "Bạn thấy bài viết này có điểm nào đáng ngờ so với dữ liệu kinh doanh thực tế không?",
            }
          : undefined,
      };
    }

    if (
      lower.includes("bai bao") ||
      lower.includes("tin tuc") ||
      lower.includes("phan tich")
    ) {
      return {
        role: "mentor",
        content: `Để phân tích một tin tức tài chính theo phương pháp Socratic, hãy tự đặt ra 3 câu hỏi:\n\n1. Nguồn tin & Độ tin cậy: Tin tức này đến từ cơ quan quản lý chính thống hay là tin đồn thổi?\n2. Tác động chu kỳ ngành: Tin tức này có làm thay đổi doanh thu hoặc chi phí của các doanh nghiệp trong ngành không?\n3. Thị trường đã phản ánh chưa: Liệu đây có phải là hiện tượng "mua vì tin đồn, bán khi tin ra"?`,
      };
    }

    return {
      role: "mentor",
      content: `${intro} Glossary chưa có khái niệm này. Hãy thử hỏi về một thuật ngữ như P/E, ROE, net margin, cắt lỗ, lãi kép, FOMO, hỗ trợ/kháng cự...`,
    };
  }

  if (mode === "trade_now") {
    const sym = selectedSymbol ?? "mã này";
    return {
      role: "mentor",
      content: `Dưới đây là các góc nhìn phản biện theo phương pháp Socrates để bạn tự rà soát quyết định vào lệnh với ${sym}:`,
      kind: "challenge",
      challenge: {
        focus: sym,
        risk_flags: [
          "Tỷ trọng phân bổ danh mục",
          "Kế hoạch dừng lỗ (Stop-Loss)",
          "Bẫy tâm lý FOMO / Bắt đáy",
        ],
        questions: [
          `Lệnh giao dịch này chiếm bao nhiêu % tổng vốn của bạn? Bạn có đang dồn vốn quá 20% vào một mã duy nhất?`,
          `Nếu thị trường đảo chiều giảm 5% - 7%, điểm cắt lỗ cụ thể của bạn nằm ở mức giá nào?`,
          `Lý do bạn vào lệnh là gì: dựa trên báo cáo tài chính/chỉ số hay chỉ vì thấy giá hoặc tin tức gần đây biến động mạnh?`,
          `Bạn dự định nắm giữ vị thế này trong bao lâu (lướt sóng ngắn hạn hay đầu tư trung hạn)?`,
        ],
        coaching_tip:
          "Hãy trả lời trung thực các câu hỏi trên trước khi nhấn xác nhận. Kỷ luật cắt lỗ quan trọng hơn việc tìm kiếm lợi nhuận.",
      },
    };
  }

  if (mode === "plan") {
    const isIncome = /cổ tức|thu nhập|bảo toàn|an toàn/i.test(text);
    const isGrowth = /tăng trưởng|rủi ro cao|nhanh/i.test(text);

    if (isIncome) {
      return {
        role: "mentor",
        content:
          "Dưới đây là khung chiến lược đầu tư phòng thủ / cổ tức được đề xuất:",
        kind: "strategy",
        strategy: {
          framework_id: "dividend_investing",
          framework_name:
            "Chiến lược Thu nhập & Cổ tức Bền vững (Dividend Investing)",
          criteria: [
            "Doanh nghiệp có lịch sử trả cổ tức tiền mặt đều đặn ít nhất 3 năm liên tiếp.",
            "Tỷ suất cổ tức / thị giá (Dividend Yield) > lãi suất tiết kiệm ngân hàng.",
            "Mô hình kinh doanh thiết yếu, dòng tiền kinh doanh (CFO) dương và ổn định.",
          ],
          allocation_rule:
            "Phân bổ 70% vào 3-4 cổ phiếu chia cổ tức tiền mặt cao, 20% trái phiếu/tiết kiệm, 10% tiền mặt linh hoạt.",
          risk_rule:
            "Cắt giảm tỷ trọng nếu doanh nghiệp chuyển sang nợ vay tăng đột biến hoặc lợi nhuận kinh doanh cốt lõi sụt giảm.",
          how_to_trade: [
            "Mua tích lũy trong các đợt điều chỉnh giảm của thị trường chung.",
            "Tái đầu tư cổ tức tiền mặt nhận được vào danh mục để tận dụng lãi kép.",
          ],
          questions: [
            "Dòng tiền bạn dùng đầu tư là tiền nhàn rỗi trong bao lâu?",
            "Doanh nghiệp có duy trì được lợi thế cạnh tranh khi kinh tế vĩ mô biến động không?",
          ],
        },
      };
    }

    if (isGrowth) {
      return {
        role: "mentor",
        content: "Dưới đây là khung chiến lược tăng trưởng có kiểm soát:",
        kind: "strategy",
        strategy: {
          framework_id: "growth_investing",
          framework_name:
            "Chiến lược Tăng trưởng Có Chọn Lọc (Growth with Discipline)",
          criteria: [
            "Tốc độ tăng trưởng doanh thu và lợi nhuận ròng hàng năm > 20%.",
            "Biên lợi nhuận gộp và ROE duy trì trên 15%.",
            "Quy mô thị trường của ngành còn nhiều dư địa mở rộng.",
          ],
          allocation_rule:
            "Tối đa 15-20% vốn cho mỗi cổ phiếu tăng trưởng; luôn giữ 15% tiền mặt dự phòng.",
          risk_rule:
            "Đặt mức dừng lỗ nghiêm ngặt (7-8% từ điểm mua) để bảo toàn vốn.",
          how_to_trade: [
            "Giải ngân thăm dò 30% khi cổ phiếu tạo nền tích lũy vững chắc.",
            "Gia tăng vị thế khi xu hướng tăng được xác nhận kèm thanh khoản lớn.",
          ],
          questions: [
            "Kỳ vọng P/E hiện tại có đang phản ánh quá mức sự lạc quan tương lai?",
            "Nếu tăng trưởng quý tới chậm lại, bạn sẽ xử lý vị thế thế nào?",
          ],
        },
      };
    }

    return {
      role: "mentor",
      content:
        "Dưới đây là khung chiến lược tích sản trung - dài hạn (DCA) phổ quát:",
      kind: "strategy",
      strategy: {
        framework_id: "dca_investing",
        framework_name: "Khung Chiến lược Tích sản Trung - Dài hạn (DCA)",
        criteria: [
          "Doanh nghiệp đầu ngành có lợi thế cạnh tranh bền vững (Moat).",
          "Ban lãnh đạo minh bạch, nợ vay an toàn (D/E < 1.0).",
          "Định giá P/E, P/B ở vùng hợp lý so với lịch sử phát triển.",
        ],
        allocation_rule:
          "Chia đều vào 3-5 ngành kinh tế trọng điểm (Ngân hàng, Bán lẻ, Công nghệ).",
        risk_rule:
          "Mua định kỳ theo tháng/quý không phụ thuộc biến động ngắn hạn; tái cân bằng 6 tháng/lần.",
        how_to_trade: [
          "Xác định khoản tiền nhàn rỗi cố định hàng tháng.",
          "Mua đúng ngày quy định, giữ tỷ trọng kỷ luật.",
          "Chỉ bán khi luận điểm kinh doanh dài hạn của doanh nghiệp bị phá vỡ.",
        ],
        questions: [
          "Bạn có cam kết duy trì kế hoạch này trong ít nhất 1-3 năm tới không?",
          "Cảm xúc của bạn sẽ ra sao nếu thị trường chung giảm 20% trong ngắn hạn?",
        ],
      },
    };
  }

  const matches = matchKnowledgeLocal(text);
  if (matches.length === 0) {
    return {
      role: "mentor",
      content: `${intro} Mình đã ghi nhận câu hỏi "${text}". Hãy thử đặt câu hỏi phản biện: thông tin bạn dựa vào đến từ đâu, và độ tin cậy của nó được kiểm chứng thế nào?`,
    };
  }
  const parts = matches.map((m) => `• ${m.concept}: ${m.definition}`);
  return {
    role: "mentor",
    content: `${intro} Những khái niệm liên quan tới "${text}":\n${parts.join("\n")}`,
  };
}