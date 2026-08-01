/**
 * CompanyMap — bản đồ bong bóng doanh nghiệp:
 * - Trục X: ngành (7 nhóm), Trục Y: điểm sức khỏe tài chính (0–100).
 * - Kích thước bong bóng = vốn hóa, màu = sức khỏe (xanh/ vàng/ đỏ).
 * - Hover xem chi tiết, click vào doanh nghiệp.
 */
"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/common/Badge";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";

import { formatCompactVND, formatNumber, parseDecimal } from "@/utils/format";
import { COMPANY_SECTORS, sectorLabel } from "@/utils/domain";

const WIDTH = 900;
const HEIGHT = 460;
const MARGIN = { top: 24, right: 16, bottom: 44, left: 48 };
const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = HEIGHT - MARGIN.top - MARGIN.bottom;

function healthColor(score: number): string {
  if (score >= 80) {
    return "#059669";
  }
  if (score >= 60) {
    return "#d97706";
  }
  return "#dc2626";
}

function healthBadgeTone(score: number): "success" | "warning" | "danger" {
  if (score >= 80) {
    return "success";
  }
  if (score >= 60) {
    return "warning";
  }
  return "danger";
}

export function CompanyMap({ companies }: { companies: CompanyResponse[] }) {
  const router = useRouter();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const maxCap = Math.max(
    1,
    ...companies.map((company) => Math.sqrt(parseDecimal(company.market_cap))),
  );

  const groups = new Map<string, CompanyResponse[]>();
  for (const company of companies) {
    const bucket = groups.get(company.sector) ?? [];
    bucket.push(company);
    groups.set(company.sector, bucket);
  }

  interface Bubble {
    company: CompanyResponse;
    cx: number;
    cy: number;
    r: number;
  }

  const bubbles: Bubble[] = [];
  for (let sectorIndex = 0; sectorIndex < COMPANY_SECTORS.length; sectorIndex += 1) {
    const sector = COMPANY_SECTORS[sectorIndex];
    const bucket = groups.get(sector.value) ?? [];
    bucket.forEach((company, index) => {
      const baseX = MARGIN.left + PLOT_WIDTH * ((sectorIndex + 0.5) / COMPANY_SECTORS.length);
      const health = company.health_score;
      const y = MARGIN.top + PLOT_HEIGHT - (health / 100) * PLOT_HEIGHT;
      const sqrtCap = Math.sqrt(parseDecimal(company.market_cap));
      const radius = 6 + (sqrtCap / maxCap) * 26;
      const jitter = (index - (bucket.length - 1) / 2) * 10;
      bubbles.push({ company, cx: baseX + jitter, cy: y, r: radius });
    });
  }

  const hovered = bubbles.find((bubble) => bubble.company.id === hoveredId);
  const hoveredCompany = hovered?.company ?? null;

  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-ink-500 dark:text-ink-400">
          {companies.length} doanh nghiệp · Trục X = ngành · Trục Y = sức khỏe tài chính
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500 dark:text-ink-400">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#059669" }} /> Tốt ≥80
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#d97706" }} /> Khá 60–79
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#dc2626" }} /> Yếu &lt;60
          </span>
          <span className="text-ink-400">· Bong bóng to = vốn hóa lớn</span>
        </div>
      </div>

      {hoveredCompany !== null && (
        <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5 dark:border-brand-500/30 dark:bg-brand-500/10">
          <span className="text-sm font-bold text-ink-900 dark:text-ink-100">
            {hoveredCompany.symbol}
            <span className="ml-2 font-medium text-ink-500 dark:text-ink-400">{hoveredCompany.name}</span>
          </span>
          <Badge variant={healthBadgeTone(hoveredCompany.health_score)}>
            Sức khỏe {hoveredCompany.health_score}
          </Badge>
          <span className="text-sm text-ink-600 dark:text-ink-300">
            {sectorLabel(hoveredCompany.sector)}
          </span>
          <span className="text-sm text-ink-600 dark:text-ink-300">
            Vốn hóa{" "}
            {parseDecimal(hoveredCompany.market_cap) > 0
              ? formatCompactVND(parseDecimal(hoveredCompany.market_cap))
              : "—"}
          </span>
          <span className="text-sm text-ink-600 dark:text-ink-300">
            P/E{" "}
            {hoveredCompany.pe_ratio !== null
              ? formatNumber(parseDecimal(hoveredCompany.pe_ratio))
              : "—"}
          </span>
          <span className="text-sm text-ink-600 dark:text-ink-300">
            ROE{" "}
            {hoveredCompany.roe !== null
              ? `${formatNumber(parseDecimal(hoveredCompany.roe))}%`
              : "—"}
          </span>
        </div>
      )}

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label="Bản đồ doanh nghiệp theo ngành và sức khỏe tài chính"
      >
        {[20, 40, 60, 80, 100].map((tick) => {
          const y = MARGIN.top + PLOT_HEIGHT - (tick / 100) * PLOT_HEIGHT;
          return (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                y1={y}
                x2={WIDTH - MARGIN.right}
                y2={y}
                className="stroke-ink-100 dark:stroke-ink-700"
                strokeDasharray="4 4"
              />
              <text
                x={MARGIN.left - 8}
                y={y + 4}
                textAnchor="end"
                className="fill-ink-400 text-[11px]"
              >
                {tick}
              </text>
            </g>
          );
        })}
        <text
          x={12}
          y={MARGIN.top + PLOT_HEIGHT / 2}
          textAnchor="middle"
          transform={`rotate(-90 12 ${MARGIN.top + PLOT_HEIGHT / 2})`}
          className="fill-ink-400 text-[11px] font-medium"
        >
          Sức khỏe tài chính
        </text>

        {COMPANY_SECTORS.map((sector, index) => {
          const x = MARGIN.left + PLOT_WIDTH * ((index + 0.5) / COMPANY_SECTORS.length);
          return (
            <text
              key={sector.value}
              x={x}
              y={HEIGHT - MARGIN.bottom + 18}
              textAnchor="middle"
              className="fill-ink-500 text-[11px] font-medium dark:fill-ink-400"
            >
              {sectorLabel(sector.value)}
            </text>
          );
        })}

        {bubbles.map((bubble) => (
          <circle
            key={bubble.company.id}
            cx={bubble.cx}
            cy={bubble.cy}
            r={bubble.r}
            fill={healthColor(bubble.company.health_score)}
            fillOpacity={0.35}
            stroke={healthColor(bubble.company.health_score)}
            strokeWidth={1.5}
            className="cursor-pointer transition-opacity"
            onMouseEnter={() => setHoveredId(bubble.company.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => router.push(`/companies/${bubble.company.id}`)}
          >
            <title>{`${bubble.company.symbol} · ${bubble.company.name} · Sức khỏe ${bubble.company.health_score}`}</title>
          </circle>
        ))}
      </svg>

      <p className="mt-2 text-xs text-ink-400 dark:text-ink-500">
        Di chuột để xem chi tiết · bấm vào bong bóng để mở hồ sơ doanh nghiệp.
      </p>
    </div>
  );
}
