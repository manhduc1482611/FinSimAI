/**
 * Domain mapping — ánh xạ giá trị enum/ID từ backend sang nhãn tiếng Việt
 * và màu sắc hiển thị. Giá trị lấy từ schema/prompt thật của backend.
 */
import type { BadgeVariant } from "@/components/common/Badge";

/** Sentiment của tin tức / bài đăng xã hội. */
export const SENTIMENT_LABELS: Record<string, string> = {
  positive: "Tích cực",
  neutral: "Trung lập",
  negative: "Tiêu cực",
};

export function sentimentVariant(
  sentiment: string,
): BadgeVariant {
  if (sentiment === "positive") {
    return "success";
  }
  if (sentiment === "negative") {
    return "danger";
  }
  return "neutral";
}

export function sentimentLabel(sentiment: string): string {
  return SENTIMENT_LABELS[sentiment] ?? sentiment;
}

/** Danh mục tin tức (theo scenario_prompts.yaml). */
export const NEWS_CATEGORIES: Array<{ value: string; label: string }> = [
  { value: "macro_domestic", label: "Vĩ mô trong nước" },
  { value: "macro_international", label: "Vĩ mô quốc tế" },
  { value: "industry", label: "Ngành" },
  { value: "company", label: "Doanh nghiệp" },
  { value: "market_report", label: "Báo cáo thị trường" },
];

export function newsCategoryLabel(category: string): string {
  const found = NEWS_CATEGORIES.find((entry) => entry.value === category);
  return found?.label ?? category;
}

/** Persona trên mạng xã hội (theo social_prompts.yaml). */
export const SOCIAL_PERSONAS: Array<{ value: string; label: string }> = [
  { value: "kol_ta_fa", label: "KOL TA/FA" },
  { value: "bragging_profit", label: "Khoe lãi" },
  { value: "loss_pump", label: "Khoe lỗ & Lùa gà" },
  { value: "rumor_birds", label: "Chim lợn tin đồn" },
  { value: "experience_sharer", label: "Chia sẻ kinh nghiệm" },
  { value: "f0_qa", label: "Hỏi đáp F0" },
  { value: "macro_view", label: "Góc nhìn vĩ mô" },
  { value: "insider_tips", label: "Tip nội bộ" },
  { value: "meme_entertain", label: "Meme giải trí" },
  { value: "scam_warning", label: "Cảnh báo lừa đảo" },
];

export function personaLabel(persona: string): string {
  const found = SOCIAL_PERSONAS.find((entry) => entry.value === persona);
  return found?.label ?? persona;
}

/** Ngành của doanh nghiệp (theo seeds/companies.yaml). */
export const COMPANY_SECTORS: Array<{ value: string; label: string }> = [
  { value: "Technology", label: "Công nghệ" },
  { value: "Financial", label: "Tài chính" },
  { value: "Healthcare", label: "Y tế" },
  { value: "Consumer Goods", label: "Hàng tiêu dùng" },
  { value: "Energy", label: "Năng lượng" },
  { value: "Industrial", label: "Công nghiệp" },
  { value: "Communications", label: "Truyền thông" },
];

export function sectorLabel(sector: string): string {
  const found = COMPANY_SECTORS.find((entry) => entry.value === sector);
  return found?.label ?? sector;
}

/** Màu nền cho điểm rủi ro (0-100). */
export function riskTone(score: number): BadgeVariant {
  if (score < 30) {
    return "success";
  }
  if (score < 60) {
    return "warning";
  }
  return "danger";
}

/** Màu cho virality score. */
export function viralityTone(score: number): BadgeVariant {
  if (score >= 80) {
    return "danger";
  }
  if (score >= 50) {
    return "warning";
  }
  if (score >= 20) {
    return "info";
  }
  return "neutral";
}
