/**
 * PriceChart — biểu đồ nến real-time bằng TradingView Lightweight Charts.
 *
 * Dữ liệu từ `usePriceStream` (WS `/ws/prices`): không có OHLC lịch sử nên nến
 * được dựng từ chuỗi tick qua `buildCandles` (gom theo cửa sổ thời gian thực).
 *
 * Hỗ trợ Dark/Light Mode: cập nhật lại màu chart khi theme đổi (useTheme).
 */
"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { useTheme } from "@/components/common/ThemeProvider";
import type { PriceTick } from "@/types/websocket";
import type { TimedPriceTick } from "@/utils/candles";
import { buildCandles } from "@/utils/candles";
import { formatNumber } from "@/utils/format";
import { cn } from "@/utils/cn";

export interface PriceChartProps {
  symbol: string;
  companyName: string;
  snapshot: PriceTick | null;
  ticks: TimedPriceTick[];
  /** Cửa sổ thời gian (giây thực) gom một cây nến. */
  bucketSeconds?: number;
  className?: string;
}

function priceTone(value: number): string {
  if (value > 0) {
    return "text-emerald-600 dark:text-emerald-400";
  }
  if (value < 0) {
    return "text-red-600 dark:text-red-400";
  }
  return "text-ink-600 dark:text-ink-300";
}

export function PriceChart({
  symbol,
  companyName,
  snapshot,
  ticks,
  bucketSeconds = 10,
  className,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const fittedRef = useRef(false);
  const { theme } = useTheme();

  const candles = useMemo(
    () => buildCandles(ticks, bucketSeconds),
    [ticks, bucketSeconds],
  );

  const change = snapshot !== null ? snapshot.change : null;
  const changePct = snapshot !== null ? snapshot.change_pct : null;
  const positive = (change ?? 0) >= 0;

  useEffect(() => {
    const container = containerRef.current;
    if (container === null) {
      return;
    }
    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme === "dark" ? "#94a3b8" : "#64748b",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.12)" },
        horzLines: { color: "rgba(148, 163, 184, 0.12)" },
      },
      rightPriceScale: { borderColor: "rgba(148, 163, 184, 0.2)" },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.2)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "rgba(148, 163, 184, 0.4)", labelBackgroundColor: "#334155" },
        horzLine: { color: "rgba(148, 163, 184, 0.4)", labelBackgroundColor: "#334155" },
      },
      localization: {
        locale: "vi-VN",
        priceFormatter: (price: number) => formatNumber(price, 2),
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;
    fittedRef.current = false;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // Chỉ tạo chart một lần; theme được cập nhật riêng ở effect dưới.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (chart === null) {
      return;
    }
    chart.applyOptions({
      layout: {
        textColor: theme === "dark" ? "#94a3b8" : "#64748b",
      },
    });
  }, [theme]);

  useEffect(() => {
    const series = seriesRef.current;
    if (series === null) {
      return;
    }
    const data: CandlestickData<UTCTimestamp>[] = candles.map((candle) => ({
      time: candle.time as UTCTimestamp,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));
    series.setData(data);
    const chart = chartRef.current;
    if (chart !== null && !fittedRef.current && data.length > 0) {
      chart.timeScale().fitContent();
      fittedRef.current = true;
    }
  }, [candles]);

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <div className="flex items-start justify-between gap-4 border-b border-ink-200 px-4 py-3 dark:border-ink-700">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-ink-900 dark:text-ink-100">{symbol}</h3>
            {snapshot !== null && (
              <Badge variant={positive ? "success" : "danger"}>
                {positive ? "+" : ""}
                {formatNumber(change ?? 0, 2)} ({positive ? "+" : ""}
                {formatNumber(changePct ?? 0, 2)}%)
              </Badge>
            )}
          </div>
          <p className="mt-0.5 truncate text-xs text-ink-500 dark:text-ink-400">{companyName}</p>
        </div>
        <div className="shrink-0 text-right">
          <p
            className={cn(
              "text-xl font-bold tabular-nums",
              snapshot !== null ? priceTone(change ?? 0) : "text-ink-400",
            )}
          >
            {snapshot !== null ? formatNumber(snapshot.price, 2) : "—"}
          </p>
          <p className="text-[10px] uppercase tracking-wide text-ink-400 dark:text-ink-500">
            {snapshot !== null ? `Ngày mô phỏng ${snapshot.sim_day}` : "Đang kết nối"}
          </p>
        </div>
      </div>

      <div className="relative min-h-[20rem] flex-1 p-2">
        <div ref={containerRef} className="h-[20rem] w-full lg:h-[24rem]" />
        {snapshot === null && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <p className="rounded-lg bg-ink-50/80 px-4 py-2 text-sm text-ink-500 dark:bg-ink-900/80 dark:text-ink-400">
              Chờ dữ liệu giá real-time…
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
