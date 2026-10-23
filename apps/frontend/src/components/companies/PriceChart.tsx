/**
 * PriceChart — biểu đồ nến real-time bằng TradingView Lightweight Charts
 * kèm các đường chỉ báo kỹ thuật (MA10, MA20) giống các ứng dụng chứng khoán chuyên nghiệp.
 *
 * Dữ liệu kết hợp:
 * - Chuỗi nến lịch sử được dựng mượt mà quanh giá tham chiếu
 * - Luồng giá real-time WebSocket cập nhật nối tiếp theo từng tick
 * - Đường MA10 (cam vàng) và MA20 (tím xanh) uốn lượn tính toán theo thời gian thực
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  LineSeries,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type UTCTimestamp,
} from "lightweight-charts";

import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { IconLock } from "@/components/common/Icon";
import { useTheme } from "@/components/common/ThemeProvider";
import { useAuthStore } from "@/store/useAuthStore";
import type { PriceTick } from "@/types/websocket";
import type { Candle, TimedPriceTick } from "@/utils/candles";
import { buildCandles, calculateMA, generateInitialCandles } from "@/utils/candles";
import { formatNumber } from "@/utils/format";
import { cn } from "@/utils/cn";

export interface PriceChartProps {
  symbol: string;
  companyName: string;
  snapshot: PriceTick | null;
  ticks: TimedPriceTick[];
  /** Cửa sổ thời gian (giây thực) gom một cây nến. */
  bucketSeconds?: number;
  noCandlesNotice?: string;
  className?: string;
}

function priceTone(value: number): string {
  if (value > 0) {
    return "text-mkt-up dark:text-mkt-up-400";
  }
  if (value < 0) {
    return "text-mkt-down dark:text-mkt-down-400";
  }
  return "text-ink-600 dark:text-granite-300";
}

export function PriceChart({
  symbol,
  companyName,
  snapshot,
  ticks,
  bucketSeconds = 10,
  noCandlesNotice,
  className,
}: PriceChartProps) {
  const token = useAuthStore((state) => state.token);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ma10SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const fittedRef = useRef(false);
  const { theme } = useTheme();

  // Khởi tạo nến quá khứ cho mã đang chọn khi có giá snapshot
  const [initialCandles, setInitialCandles] = useState<Candle[]>([]);
  const lastSymbolRef = useRef<string>(symbol);

  useEffect(() => {
    if (symbol !== lastSymbolRef.current) {
      lastSymbolRef.current = symbol;
      setInitialCandles([]);
      fittedRef.current = false;
    }
  }, [symbol]);

  useEffect(() => {
    if (snapshot !== null && snapshot.price > 0 && initialCandles.length === 0) {
      const generated = generateInitialCandles(snapshot.price, 40, bucketSeconds);
      setInitialCandles(generated);
    }
  }, [snapshot, bucketSeconds, initialCandles.length]);

  // Ghép nến lịch sử với nến gom từ tick real-time
  const candles = useMemo(() => {
    const realCandles = buildCandles(ticks, bucketSeconds);
    if (initialCandles.length === 0) return realCandles;
    if (realCandles.length === 0) return initialCandles;

    const firstRealTime = realCandles[0].time;
    const prior = initialCandles.filter((c) => c.time < firstRealTime);
    return [...prior, ...realCandles];
  }, [initialCandles, ticks, bucketSeconds]);

  // Tính các đường chỉ báo kỹ thuật Moving Average
  const ma10Data = useMemo(() => calculateMA(candles, 10), [candles]);
  const ma20Data = useMemo(() => calculateMA(candles, 20), [candles]);

  const latestMA10 = ma10Data.length > 0 ? ma10Data[ma10Data.length - 1].value : null;
  const latestMA20 = ma20Data.length > 0 ? ma20Data[ma20Data.length - 1].value : null;

  const change = snapshot !== null ? snapshot.change : null;
  const changePct = snapshot !== null ? snapshot.change_pct : null;
  const positive = (change ?? 0) >= 0;

  // Khởi tạo biểu đồ Lightweight Charts
  useEffect(() => {
    if (!token) {
      return;
    }
    const container = containerRef.current;
    if (container === null) {
      return;
    }
    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme === "dark" ? "#A7B1BE" : "#66727F",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(102, 114, 127, 0.14)" },
        horzLines: { color: "rgba(102, 114, 127, 0.14)" },
      },
      rightPriceScale: { borderColor: "rgba(102, 114, 127, 0.24)" },
      timeScale: {
        borderColor: "rgba(102, 114, 127, 0.24)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "rgba(0, 230, 217, 0.55)", labelBackgroundColor: "#1E2430" },
        horzLine: { color: "rgba(0, 230, 217, 0.55)", labelBackgroundColor: "#1E2430" },
      },
      localization: {
        locale: "vi-VN",
        priceFormatter: (price: number) => formatNumber(price, 2),
      },
    });

    // 1. Series nến giá chính
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#1CAE56",
      downColor: "#E23636",
      borderVisible: false,
      wickUpColor: "#1CAE56",
      wickDownColor: "#E23636",
    });

    // 2. Đường kỹ thuật MA10 (Màu vàng cam)
    const ma10Series = chart.addSeries(LineSeries, {
      color: "#F59E0B",
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    // 3. Đường kỹ thuật MA20 (Màu tím xanh)
    const ma20Series = chart.addSeries(LineSeries, {
      color: "#8B5CF6",
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    ma10SeriesRef.current = ma10Series;
    ma20SeriesRef.current = ma20Series;
    fittedRef.current = false;

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      ma10SeriesRef.current = null;
      ma20SeriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cập nhật theme Dark/Light
  useEffect(() => {
    const chart = chartRef.current;
    if (chart === null) return;
    chart.applyOptions({
      layout: {
        textColor: theme === "dark" ? "#A7B1BE" : "#66727F",
      },
    });
  }, [theme]);

  // Cập nhật dữ liệu nến và các đường MA
  useEffect(() => {
    const candleSeries = candleSeriesRef.current;
    const ma10Series = ma10SeriesRef.current;
    const ma20Series = ma20SeriesRef.current;

    if (candleSeries === null) return;

    const data: CandlestickData<UTCTimestamp>[] = candles.map((candle) => ({
      time: candle.time as UTCTimestamp,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));
    candleSeries.setData(data);

    if (ma10Series !== null) {
      const ma10LineData: LineData<UTCTimestamp>[] = ma10Data.map((pt) => ({
        time: pt.time as UTCTimestamp,
        value: pt.value,
      }));
      ma10Series.setData(ma10LineData);
    }

    if (ma20Series !== null) {
      const ma20LineData: LineData<UTCTimestamp>[] = ma20Data.map((pt) => ({
        time: pt.time as UTCTimestamp,
        value: pt.value,
      }));
      ma20Series.setData(ma20LineData);
    }

    const chart = chartRef.current;
    if (chart !== null && !fittedRef.current && data.length > 0) {
      chart.timeScale().fitContent();
      fittedRef.current = true;
    }
  }, [candles, ma10Data, ma20Data]);

  if (!token) {
    return (
      <Card className={cn("overflow-hidden", className)}>
        {/* Header of chart showing stock info but locked */}
        <div className="flex flex-wrap items-center justify-between border-b border-line px-4 py-3 dark:border-granite-800">
          <div className="flex items-center gap-2">
            <span className="board-num text-base font-black text-ink-900 dark:text-slip">
              {symbol}
            </span>
            <span className="truncate text-xs text-ink-500 dark:text-granite-400">
              {companyName}
            </span>
          </div>
          <Badge variant="warning">Yêu cầu đăng nhập</Badge>
        </div>

        {/* Locked chart body */}
        <div className="relative flex h-[380px] w-full flex-col items-center justify-center overflow-hidden bg-slip/50 px-6 text-center dark:bg-granite-950/60">
          {/* Simulated blurred candlestick silhouettes in background */}
          <div
            className="pointer-events-none absolute inset-0 flex select-none items-end justify-between px-8 pb-10 opacity-15 blur-[2px]"
            aria-hidden="true"
          >
            <div className="h-28 w-4 rounded-sm bg-mkt-up" />
            <div className="h-44 w-4 rounded-sm bg-mkt-up" />
            <div className="h-36 w-4 rounded-sm bg-mkt-down" />
            <div className="h-56 w-4 rounded-sm bg-mkt-up" />
            <div className="h-40 w-4 rounded-sm bg-mkt-down" />
            <div className="h-64 w-4 rounded-sm bg-mkt-up" />
            <div className="h-52 w-4 rounded-sm bg-mkt-down" />
            <div className="h-72 w-4 rounded-sm bg-mkt-up" />
          </div>

          <div className="relative z-10 max-w-md rounded-2xl border border-line bg-paper/95 p-6 shadow-card backdrop-blur dark:border-granite-700 dark:bg-granite-900/95">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <IconLock className="h-6 w-6" />
            </div>

            <h3 className="mt-4 text-base font-black text-ink-900 dark:text-slip">
              Biểu đồ chứng khoán yêu cầu đăng nhập
            </h3>

            <p className="mt-2 text-xs leading-relaxed text-ink-500 dark:text-granite-400">
              Biểu đồ nến real-time với các chỉ báo kỹ thuật MA10/MA20 và luồng tick giá trực tiếp chỉ khả dụng cho thành viên. Đăng nhập hoặc tạo tài khoản miễn phí để mở khóa toàn bộ dữ liệu.
            </p>

            <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-center">
              <Link href="/login" className="btn-primary px-5 py-2 text-xs">
                Đăng nhập để xem biểu đồ
              </Link>
              <Link href="/register" className="btn-secondary px-5 py-2 text-xs">
                Tạo tài khoản miễn phí
              </Link>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-4 py-3 dark:border-granite-700">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="board-num text-base font-black text-ink-900 dark:text-slip">{symbol}</h3>
            {snapshot !== null && (
              <Badge variant={positive ? "success" : "danger"}>
                {positive ? "+" : ""}
                {formatNumber(change ?? 0, 2)} ({positive ? "+" : ""}
                {formatNumber(changePct ?? 0, 2)}%)
              </Badge>
            )}
            {/* Hiển thị thông số các đường kỹ thuật MA */}
            <div className="ml-2 flex items-center gap-3 text-xs font-semibold">
              <span className="flex items-center gap-1.5 text-amber-500 dark:text-amber-400">
                <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
                MA10: {latestMA10 !== null ? formatNumber(latestMA10, 2) : "—"}
              </span>
              <span className="flex items-center gap-1.5 text-purple-500 dark:text-purple-400">
                <span className="inline-block h-2 w-2 rounded-full bg-purple-500" />
                MA20: {latestMA20 !== null ? formatNumber(latestMA20, 2) : "—"}
              </span>
            </div>
          </div>
          <p className="mt-0.5 truncate text-xs text-ink-500 dark:text-granite-300">{companyName}</p>
        </div>
        <div className="shrink-0 text-right">
          <p
            className={cn(
              "board-num text-2xl font-black",
              snapshot !== null ? priceTone(change ?? 0) : "text-ink-400",
            )}
          >
            {snapshot !== null ? formatNumber(snapshot.price, 2) : "—"}
          </p>
          <p className="board-label mt-0.5">
            {snapshot !== null ? `Ngày mô phỏng ${snapshot.sim_day}` : "Đang kết nối"}
          </p>
        </div>
      </div>

      <div className="relative min-h-[20rem] flex-1 p-2">
        <div ref={containerRef} className="h-[20rem] w-full lg:h-[24rem]" />
        {snapshot === null && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <p className="rounded-lg bg-ink-50/80 px-4 py-2 text-sm text-ink-500 dark:bg-granite-900/80 dark:text-granite-300">
              Chờ dữ liệu giá real-time…
            </p>
          </div>
        )}
        {snapshot !== null && candles.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <p className="rounded-lg bg-ink-50/80 px-4 py-2 text-sm text-ink-500 dark:bg-granite-900/80 dark:text-granite-300">
              {noCandlesNotice ?? "Đang chờ tick giá để vẽ nến…"}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
