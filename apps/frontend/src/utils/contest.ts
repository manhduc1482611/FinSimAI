/**
 * Nhãn tiếng Việt cho các lựa chọn khuôn/độ khó/trạng thái contest.
 */
export const TEMPLATE_LABELS: Record<string, string> = {
  classic: "Cổ điển",
  tech_news: "Công nghệ & Tin tức",
  fast_paced: "Biến động mạnh",
  micro: "Thu nhỏ",
};

export const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "Dễ",
  normal: "Thường",
  hard: "Khó",
};

export const STATUS_LABELS: Record<string, string> = {
  draft: "Nháp",
  active: "Đang chạy",
  ended: "Đã kết thúc",
};

export function templateLabel(template: string | undefined | null): string {
  return (template && TEMPLATE_LABELS[template]) || "Cổ điển";
}

export function difficultyLabel(difficulty: string | undefined | null): string {
  return (difficulty && DIFFICULTY_LABELS[difficulty]) || "Thường";
}

export function statusLabel(status: string | undefined | null): string {
  return (status && STATUS_LABELS[status]) || "—";
}

// ────────────────────────────────────────────────────────────────────────────
// Khuôn (template) — bản sao frontend của TEMPLATES trong schemas/contest.py.
// Giữ nguyên mặc định để form hiển thị đúng; backend vẫn là nguồn chân lý.
// ────────────────────────────────────────────────────────────────────────────
export type TemplateId = "classic" | "tech_news" | "fast_paced" | "micro";
export type Difficulty = "easy" | "normal" | "hard";

export interface TemplateOption {
  id: TemplateId;
  label: string;
  description: string;
  defaultCompanyCount: number;
  defaultIndustry: string;
  defaultStartCash: number;
  defaultCooldownSeconds: number;
  defaultVolatilityMultiplier: number;
  allowShort: boolean;
  newsEmphasis: boolean;
}

export const TEMPLATE_OPTIONS: TemplateOption[] = [
  {
    id: "classic",
    label: "Cổ điển",
    description: "Mặc định, giống thị trường chính.",
    defaultCompanyCount: 8,
    defaultIndustry: "tổng hợp",
    defaultStartCash: 100_000_000,
    defaultCooldownSeconds: 30,
    defaultVolatilityMultiplier: 1.0,
    allowShort: false,
    newsEmphasis: false,
  },
  {
    id: "tech_news",
    label: "Công nghệ & Tin tức",
    description: "Trọng tâm tin tức và bài viết về lĩnh vực đã chọn.",
    defaultCompanyCount: 6,
    defaultIndustry: "công nghệ",
    defaultStartCash: 200_000_000,
    defaultCooldownSeconds: 15,
    defaultVolatilityMultiplier: 1.2,
    allowShort: false,
    newsEmphasis: true,
  },
  {
    id: "fast_paced",
    label: "Biến động mạnh",
    description: "Giá biến động mạnh, cooldown ngắn — dành cho nhà giao dịch nhanh.",
    defaultCompanyCount: 10,
    defaultIndustry: "tổng hợp",
    defaultStartCash: 500_000_000,
    defaultCooldownSeconds: 5,
    defaultVolatilityMultiplier: 1.6,
    allowShort: true,
    newsEmphasis: false,
  },
  {
    id: "micro",
    label: "Thu nhỏ",
    description: "Cuộc thi nhỏ gọn, ít công ty, diễn ra nhanh.",
    defaultCompanyCount: 4,
    defaultIndustry: "tổng hợp",
    defaultStartCash: 50_000_000,
    defaultCooldownSeconds: 5,
    defaultVolatilityMultiplier: 1.0,
    allowShort: false,
    newsEmphasis: false,
  },
];

const DIFFICULTY_MODS: Record<Difficulty, { volatility: number; startCash: number; cooldown: number }> = {
  easy: { volatility: 0.7, startCash: 1.5, cooldown: 2 },
  normal: { volatility: 1.0, startCash: 1.0, cooldown: 1 },
  hard: { volatility: 1.4, startCash: 0.5, cooldown: 0.5 },
};

/** Resolve quy tắc hiển thị từ template + độ khó (mirror `resolve_rules`). */
export function resolveRulesPreview(
  template: TemplateOption,
  difficulty: Difficulty,
): { startCash: number; cooldownSeconds: number; volatilityMultiplier: number } {
  const mod = DIFFICULTY_MODS[difficulty];
  return {
    startCash: Math.round(template.defaultStartCash * mod.startCash),
    cooldownSeconds: Math.max(1, Math.round(template.defaultCooldownSeconds * mod.cooldown)),
    volatilityMultiplier: Math.round(template.defaultVolatilityMultiplier * mod.volatility * 100) / 100,
  };
}
