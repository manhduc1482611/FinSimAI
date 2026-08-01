/**
 * Keyword matching phía client — fallback khi backend `/knowledge/match` không
 * phản hồi. Map các thuật ngữ tài chính phổ biến sang khái niệm/định nghĩa ngắn
 * (đồng bộ cấu trúc với `KnowledgeResponse`).
 */
import type { KnowledgeResponse } from "@finsim/shared-types/generated/api-types";

interface LocalConcept {
  keyword: string;
  concept: string;
  definition: string;
  category: string;
  difficulty: number;
  related: string[];
}

const LOCAL_GLOSSARY: LocalConcept[] = [
  {
    keyword: "fomo",
    concept: "FOMO (Fear Of Missing Out)",
    definition:
      "Sợ bỏ lỡ cơ hội — mua/bán do tâm lý đám đông thay vì phân tích. Dấu hiệu: quyết định gấp, không có kế hoạch, giá đã tăng/giảm mạnh.",
    category: "Tâm lý",
    difficulty: 1,
    related: ["tâm lý", "bầy đàn", "cảm xúc"],
  },
  {
    keyword: "pe",
    concept: "P/E (Price to Earnings)",
    definition:
      "Chỉ số định giá = Giá / Lợi nhuận mỗi cổ phần. P/E thấp thường rẻ nhưng cần so sánh với trung bình ngành và tăng trưởng.",
    category: "Định giá",
    difficulty: 2,
    related: ["định giá", "p/e"],
  },
  {
    keyword: "roe",
    concept: "ROE (Return on Equity)",
    definition:
      "Tỷ suất lợi nhuận trên vốn chủ sở hữu. ROE cao và ổn định cho thấy doanh nghiệp dùng vốn hiệu quả.",
    category: "Hiệu quả",
    difficulty: 2,
    related: ["lợi nhuận", "vốn"],
  },
  {
    keyword: "net margin",
    concept: "Biên lợi nhuận ròng",
    definition:
      "Lợi nhuận sau thuế / Doanh thu. Biên ròng cao thể hiện sức mạnh định giá và kiểm soát chi phí.",
    category: "Hiệu quả",
    difficulty: 2,
    related: ["biên lợi nhuận", "lợi nhuận"],
  },
  {
    keyword: "cut loss",
    concept: "Cắt lỗ (Stop-Loss)",
    definition:
      "Đặt mức giá thoát để giới hạn thua lỗ. Cắt lỗ phải theo kế hoạch từ trước, không phải quyết định cảm xúc lúc thị trường biến động.",
    category: "Quản trị rủi ro",
    difficulty: 1,
    related: ["cắt lỗ", "rủi ro"],
  },
  {
    keyword: "risk",
    concept: "Quản trị rủi ro",
    definition:
      "Kiểm soát mức thua lỗ tối đa mỗi lệnh và tổng danh mục. Quy tắc phổ biến: rủi ro mỗi lệnh không quá 1-2% NAV.",
    category: "Quản trị rủi ro",
    difficulty: 1,
    related: ["rủi ro", "nav"],
  },
  {
    keyword: "volume",
    concept: "Khối lượng giao dịch",
    definition:
      "Số lượng cổ phiếu khớp trong kỳ. Giá tăng kèm khối lượng lớn thường đáng tin hơn giá tăng trên thanh khoản mỏng.",
    category: "Kỹ thuật",
    difficulty: 2,
    related: ["thanh khoản", "khối lượng"],
  },
  {
    keyword: "support resistance",
    concept: "Hỗ trợ & Kháng cự",
    definition:
      "Vùng giá mua (hỗ trợ) và vùng giá bán (kháng cự) hình thành từ lịch sử. Dùng để đặt điểm vào lệnh và stop-loss hợp lý.",
    category: "Kỹ thuật",
    difficulty: 2,
    related: ["hỗ trợ", "kháng cự", "kỹ thuật"],
  },
  {
    keyword: "market order",
    concept: "Lệnh thị trường (Market Order)",
    definition:
      "Khớp ngay ở giá hiện tại, đảm bảo thực hiện nhưng giá khớp có thể lệch so với kỳ vọng khi biến động mạnh.",
    category: "Lệnh giao dịch",
    difficulty: 1,
    related: ["market", "lệnh"],
  },
  {
    keyword: "limit order",
    concept: "Lệnh giới hạn (Limit Order)",
    definition:
      "Chỉ khớp ở mức giá bằng hoặc tốt hơn mức đặt. Kiểm soát giá nhưng có thể không khớp nếu thị trường không chạm giá.",
    category: "Lệnh giao dịch",
    difficulty: 1,
    related: ["limit", "lệnh"],
  },
];

function normalize(text: string): string {
  return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

const CONCEPT_CACHE: Map<string, KnowledgeResponse[]> = new Map();

/** Tìm kiếm khái niệm phù hợp nhất với đoạn text (không dấu, tiếng Việt ok). */
export function matchKnowledgeLocal(
  text: string,
  limit = 3,
): KnowledgeResponse[] {
  if (!text.trim()) {
    return [];
  }
  const key = `${text.trim().toLowerCase()}|${limit}`;
  const cached = CONCEPT_CACHE.get(key);
  if (cached) {
    return cached;
  }

  const haystack = normalize(text);
  const scored = LOCAL_GLOSSARY.map((entry) => {
    const terms = [entry.keyword, ...entry.related];
    let score = 0;
    for (const term of terms) {
      if (haystack.includes(normalize(term))) {
        score += 1;
      }
    }
    return { entry, score };
  })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(({ entry }) => ({
      id: `local-${entry.keyword}`,
      keyword: entry.keyword,
      concept: entry.concept,
      definition: entry.definition,
      category: entry.category,
      difficulty: entry.difficulty,
      related_keywords: entry.related,
      created_at: new Date(0).toISOString(),
    }));

  CONCEPT_CACHE.set(key, scored);
  return scored;
}
