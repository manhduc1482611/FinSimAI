# Kế hoạch hoàn thiện FinSimAI

> Chi tiết từng nhiệm vụ theo thứ tự ưu tiên P0 → P1 → P2.
> Dựa trên đánh giá `CRITIQUE_2026-09-08.md`.

---

## Mục tiêu tổng thể

| Giai đoạn | Điểm dự kiến | Phạm vi |
|---|---|---|
| Hiện tại | ~6.8/10 | UI có, data lỗi |
| Sau P0 | ~7.8/10 | Data đúng, trade chạy được |
| Sau P1 | ~8.3/10 | UX đầy đủ, simulation sống |
| Sau P2 | 8.5–9/10 | Visual polish, responsive |

---

# PHASE 1 — 🔴 P0: DỮ LIỆU ĐÚNG + TRADE CHẠY ĐƯỢC

---

## P0-1: Tạo lớp format & data validation

**Mục đích:** Không render raw API data trực tiếp. Tất cả số hiển thị phải qua format.

### P0-1.1 — Tạo utility functions

```ts
// Tạo file: src/utils/format.ts

formatCurrency(value: number)    → "100.000.000 ₫"
formatCompactCurrency(value)     → "100M" | "1.2B"
formatPercent(value: number)     → "+2.67%" | "-0.54%"
formatImpact(value: number)      → "7.8/10"
formatDate(value: string)        → "08/09 14:30"
formatNumber(value: number)      → "177.654"
formatViral(value: number)       → "×2.4" | "82"
```

### P0-1.2 — Thay thế toàn bộ hardcoded display

- [ ] Tìm tất cả nơi render số tiền: grep `toFixed`, `toLocaleString`, `₫`
- [ ] Thay thế bằng `formatCurrency()`
- [ ] Tìm tất cả nơi render %: grep `%`, `percent`
- [ ] Thay bằng `formatPercent()`
- [ ] Tìm tất cả nơi render ngày: grep `createdAt`, `timestamp`, `Date`
- [ ] Thay bằng `formatDate()`

### P0-1.3 — Thêm validation layer

```ts
// Tạo file: src/utils/validate.ts

validatePrice(value)     → throw nếu NaN/undefined/negative
validatePercent(value)   → clamp [-100, 1000]
validateImpact(value)    → clamp [0, 10]
validateViral(value)     → clamp [0, 100]
validateSymbol(value)    → throw nếu chứa { hay }
```

---

## P0-2: Sửa lỗi News `{name}` `{symbol}`

### P0-2.1 — Xác định root cause

- [ ] Kiểm tra component News/NewsCard
- [ ] Kiểm tra mock data / API response
- [ ] Có thể là:
  - Template literal sai: `` `${name}` `` thay vì `${article.name}`
  - API trả về object lồng nhau: `data.name.company` thay vì `data.companyName`
  - Default value là string `"name"` thay vì undefined

### P0-2.2 — Sửa source

- [ ] Nếu dùng mock data → sửa template trong mock
- [ ] Nếu API → kiểm tra `response.data.name` có đúng field không
- [ ] Thêm fallback: `article.companyName || article.name || 'N/A'`
- [ ] Tương tự cho `symbol`: `article.symbol || 'N/A'`

### P0-2.3 — Kiểm tra toàn bộ trang News

- [ ] Tất cả headline hiển thị đúng tên công ty
- [ ] Tất cả tag hiển thị đúng mã CP
- [ ] Không còn `{` hay `}` trong UI

---

## P0-3: Sửa lỗi timestamp hiển thị sai

### P0-3.1 — Xác định timestamp leak

Vấn đề hiển thị:
```
Tác động 1777654800000.0/10
Capia News 1785517200000.0
```

- [ ] Kiểm tra field `impact` trong database/mock → có thể là `created_at` (Unix ms) hoặc `id`
- [ ] Kiểm tra API response → field `impact` trả về gì?
- [ ] Có thể là number lớn (1777654800000) — cần xác nhận

### P0-3.2 — Sửa mapping API → frontend

```ts
// Nếu API trả impact là timestamp:
const impact = article.impact_timestamp
  ? calculateImpactFromTimestamp(article.impact_timestamp)
  : article.impact ?? 0

// Nếu API trả impact sai field:
const impact = article.sentiment_impact ?? article.score ?? 0
```

### P0-3.3 — Sửa fallback

```ts
// Thêm fallback an toàn
const safeImpact = (val) => {
  if (!val || val > 1000) return 0
  return Math.min(Math.max(val, 0), 10)
}
```

---

## P0-4: Sửa lỗi Viral % trên Social

### P0-4.1 — Xác định root cause

Vấn đề: `Viral 176720040000%`

- [ ] Kiểm tra field `viral_score` trong mock/API
- [ ] Có thể là:
  - Timestamp thay vì viral count
  - Số nguyên lớn bị hiển thị như %
  - Sai field mapping

### P0-4.2 — Sửa format

```ts
// Tạo format function
const formatViral = (val) => {
  if (!val) return '—'
  if (val > 10000) {
    // Có thể là raw count → convert
    return `🔥 ${Math.round(val / 1000)}k`
  }
  return `×${(val / 100).toFixed(1)}`
}
```

### P0-4.3 — Áp dụng cho Social feed

- [ ] Tất cả post hiển thị viral đúng format
- [ ] Không có số > 1000% hiển thị

---

## P0-5: Trade page — Price chart có dữ liệu

### P0-5.1 — Tạo simulated price data

```ts
// Tạo file: src/services/priceSimulator.ts

interface PricePoint {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// Tạo 100 ngày dữ liệu giả lập
function generateHistoricalPrices(
  basePrice: number,
  volatility: number,
  days: number
): PricePoint[]

// Tạo tick realtime
function startRealtimeSimulation(
  currentPrice: number,
  callback: (newPrice: number) => void,
  intervalMs: number = 3000
): () => void  // return cleanup function
```

### P0-5.2 — Tích hợp với chart component

```ts
// Hook: usePriceChart.ts
function usePriceChart(symbol: string) {
  const [prices, setPrices] = useState<PricePoint[]>([])
  const [currentPrice, setCurrentPrice] = useState(0)

  useEffect(() => {
    // Load historical
    const hist = generateHistoricalPrices(154, 0.02, 100)
    setPrices(hist)
    setCurrentPrice(hist[hist.length - 1].close)

    // Start realtime
    const cleanup = startRealtimeSimulation(
      hist[hist.length - 1].close,
      (p) => setCurrentPrice(p),
      3000
    )
    return cleanup
  }, [symbol])

  return { prices, currentPrice }
}
```

### P0-5.3 — Hiển thị trên Trade page

- [ ] Thay "Chờ dữ liệu giá real-time..." bằng biểu đồ
- [ ] Hiển thị giá hiện tại: `154.20`
- [ ] Hiển thị change: `+1.37%`
- [ ] Chart render 100 ngày lịch sử + tick realtime mỗi 3 giây

---

## P0-6: Order book có dữ liệu

### P0-6.1 — Tạo order book giả lập

```ts
// Tạo file: src/services/orderBookSimulator.ts

interface OrderBookLevel {
  price: number
  quantity: number
  total: number
}

function generateOrderBook(
  currentPrice: number,
  spread: number,
  depth: number = 10
): { bids: OrderBookLevel[], asks: OrderBookLevel[] }
```

### P0-6.2 — Tích hợp OrderBook component

- [ ] Hiển thị bids (màu xanh) và asks (màu đỏ)
- [ ] Cập nhật mỗi 2–3 giây
- [ ] Spread hiển thị ở giữa

---

## P0-7: Đảm bảo Buy/Sell hoạt động đúng

### P0-7.1 — Validation trước khi đặt lệnh

```ts
// Mua
if (order.type === 'buy') {
  const totalCost = order.price * order.quantity
  if (totalCost > portfolio.cash) {
    throw new Error('Vốn không đủ')
  }
}

// Bán
if (order.type === 'sell') {
  const holding = portfolio.positions.find(p => p.symbol === order.symbol)
  if (!holding || holding.quantity < order.quantity) {
    throw new Error('Không đủ cổ phiếu')
  }
}
```

### P0-7.2 — Cập nhật portfolio sau giao dịch

- [ ] Sau khi buy thành công → trừ cash, thêm position
- [ ] Sau khi sell thành công → cộng cash, trừ position
- [ ] NAV cập nhật real-time

### P0-7.3 — Lưu vào database

- [ ] Lệnh được lưu vào bảng `orders` (status: pending/filled/cancelled)
- [ ] Nếu có matching → lưu vào bảng `trades`
- [ ] Portfolio cập nhật vào bảng `portfolio_positions`

---

## P0-8: Kiểm tra data persistence

### P0-8.1 — Refresh test

- [ ] Sau khi refresh, portfolio vẫn giữ nguyên
- [ ] Sau khi refresh, order history vẫn hiển thị
- [ ] Dữ liệu không chỉ ở frontend state

### P0-8.2 — Database schema check

```sql
-- Kiểm tra các bảng tồn tại:
-- users
-- orders
-- trades
-- portfolio_positions
-- news
-- social_posts
-- companies
-- price_history
```

---

# PHASE 2 — 🟠 P1: NÂNG UX

---

## P1-1: Dashboard redesign

### P1-1.1 — Bố cục mới

```
┌──────────────────────────────────────────────┐
│  NAV        CASH       P/L        RISK        │
└──────────────────────────────────────────────┘

┌────────────────────────┐ ┌────────────────────┐
│  HIỆU SUẤT DANH MỤC    │ │  NHIỆM VỤ 4/6      │
│                        │ │  ████████░░░       │
│  [line chart 7 ngày]   │ │  ✅ Điểm danh       │
│  NAV: 100.020.510      │ │  ✅ Mua 1 lệnh     │
│  Change: +0.02%        │ │  ⬜ Bán 1 lệnh     │
└────────────────────────┘ │  ⬜ Đọc 3 tin       │
                           │  ⬜ Chat mentor      │
                           │  ⬜ Kết bạn          │
                           └────────────────────┘

┌────────────────────────┐ ┌────────────────────┐
│  TIN TỨC THỊ TRƯỜNG     │ │  TOP CỔ PHIẾU      │
│                        │ │                    │
│  📈 TECHA +2.6%        │ │  TECHA  154  +2.6% │
│  TechVision vượt KQKD  │ │  FINA    46  +1.8% │
│  2 phút trước           │ │  VNM    82  -0.3% │
│                        │ │  FPT   120  +0.5% │
│  📉 VNM -0.3%          │ │                    │
│  Vinamilk quý yếu      │ │                    │
└────────────────────────┘ └────────────────────┘

┌──────────────────────────────────────────────┐
│  HOẠT ĐỘNG GẦN ĐÂY                           │
│  14:32  Mua 20 TECHA @ 154                   │
│  14:20  Điểm danh ngày                        │
│  13:45  Đọc tin "TechVision vượt KQKD"       │
└──────────────────────────────────────────────┘
```

### P1-1.2 — Triển khai

- [ ] Xóa các feature card hiện tại (6 card menu)
- [ ] Tạo component `PortfolioChart` (line chart nhỏ 7 ngày)
- [ ] Tạo component `TopStocks` (bảng top 5 CP)
- [ ] Tạo component `RecentActivity` (timeline hoạt động)
- [ ] Tạo component `MarketNews` (3 tin nổi bật)
- [ ] Bố cục 2-column grid, row cuối full width

---

## P1-2: Trade — Order confirmation

### P1-2.1 — Thêm modal confirmation

```tsx
<OrderConfirmModal
  visible={showConfirm}
  order={{
    symbol: 'TECHA',
    side: 'buy',
    type: 'limit',
    price: 154,
    quantity: 20,
    total: 3080,
    fee: 0,
  }}
  onConfirm={submitOrder}
  onCancel={() => setShowConfirm(false)}
/>
```

### P1-2.2 — Hiển thị trong modal

```
Xác nhận lệnh MUA

Mã:              TECHA
Loại lệnh:       Giới hạn
Giá đặt:         154.000 ₫
Khối lượng:      20
─────────────────────────
Giá trị lệnh:    3.080.000 ₫
Phí giao dịch:   0 ₫
Tổng thanh toán: 3.080.000 ₫

[Xác nhận]    [Hủy]
```

---

## P1-3: Trade — Order history

### P1-3.1 — Tạo tab/bảng Order History

```tsx
// Component: OrderHistory
// Tabs: Tất cả | Đang chờ | Đã khớp | Đã hủy

<Table
  columns={['Thời gian', 'Mã', 'Loại', 'KL', 'Giá', 'Tổng', 'Trạng thái']}
  data={orders}
/>
```

### P1-3.2 — Triển khai

- [ ] Component OrderHistory với tabs
- [ ] Fetch orders từ API/database
- [ ] Filter theo status
- [ ] Hiển thị "Không có lệnh nào" khi rỗng

---

## P1-4: News — Nâng cấp hiển thị

### P1-4.1 — Thêm metadata cho mỗi tin

```
┌──────────────────────────────────────┐
│ TechVision Corp công bố kết quả KQKD │
│ quý vượt kỳ vọng                     │
│                                      │
│ TECHA    Tích cực    +3.2%           │
│ Impact   8.4/10     2 phút trước     │
└──────────────────────────────────────┘
```

### P1-4.2 — Thêm sentiment badge

```tsx
<SentimentBadge sentiment="positive" />
// → hiển thị badge xanh "Tích cực"

<SentimentBadge sentiment="negative" />
// → hiển thị badge đỏ "Tiêu cực"

<SentimentBadge sentiment="neutral" />
// → hiển thị badge xám "Trung tính"
```

### P1-4.3 — Thêm price reaction

```
Tin tức liên quan: TECHA
Giá trước tin: 153.20
Giá sau tin:   154.50
Thay đổi:      +0.85%
```

---

## P1-5: Social — Liên kết với thị trường

### P1-5.1 — Upgrade Social post card

```
┌──────────────────────────────────────┐
│ 👤 F0 mới tập đầu tư                │
│ Psychological type: Conservative     │
│                                      │
│ Mình mới mua thêm TECHA hôm nay...   │
│                                      │
│ ┌────────────────────────────────┐   │
│ │ 📈 TECHA                       │   │
│ │ Mua: 20 CP @ 154 ₫            │   │
│ │ Tổng: 3.080.000 ₫             │   │
│ │ Quan điểm: Tích cực            │   │
│ └────────────────────────────────┘   │
│                                      │
│ ❤️ 12  💬 3  🔄 1   🔥 Viral ×2.4  │
└──────────────────────────────────────┘
```

### P1-5.2 — Triển khai

- [ ] Component `TradeLinkedPost`
- [ ] Hiển thị sentiment + price action liên quan
- [ ] Format viral: `×2.4` hoặc `🔥 82`
- [ ] Thêm sentiment badge trên post

---

## P1-6: Portfolio — Thêm tổng quan

### P1-6.1 — Component PortfolioSummary

```tsx
<PortfolioSummary
  totalAsset={100020510}
  cash={100000000}
  stockValue={20510}
  pl={510}
  plPercent={0.02}
/>
```

### P1-6.2 — Hiển thị

```
Tổng tài sản           100.020.510 ₫
─────────────────────────────────────
Tiền mặt               100.000.000 ₫
Giá trị cổ phiếu            20.510 ₫
Lãi/lỗ (today)                +510 ₫  (+0.02%)
```

---

## P1-7: Loading / Empty / Error states

### P1-7.1 — Component skeleton

```tsx
// Component: Skeleton
<Skeleton width="100%" height={20} count={5} />
```

### P1-7.2 — Empty state

```tsx
// Component: EmptyState
<EmptyState
  icon="📊"
  title="Chưa có lệnh nào"
  description="Bắt đầu đặt lệnh đầu tiên của bạn"
  action={<Button>Đặt lệnh</Button>}
/>
```

### P1-7.3 — Error state

```tsx
<ErrorState
  icon="⚠️"
  title="Không thể tải dữ liệu"
  description="Vui lòng thử lại"
  action={<Button onClick={retry}>Thử lại</Button>}
/>
```

### P1-7.4 — Áp dụng cho tất cả trang

- [ ] Dashboard: skeleton khi load
- [ ] Trade: skeleton chart + empty order book
- [ ] News: skeleton cards
- [ ] Social: skeleton posts
- [ ] Portfolio: skeleton table
- [ ] Mọi page: error state khi fetch fail

---

# PHASE 3 — 🟡 P2: VISUAL POLISH

---

## P2-1: Sidebar — Rút gọn subtitle

### P2-1.1 — Thay đổi

```tsx
// Trước
<MenuItem icon="🏠" title="Bảng điều khiển" subtitle="Tổng quan & cuộc thi" />

// Sau
<MenuItem icon="🏠" title="Bảng điều khiển" />
```

### P2-1.2 — Danh sách menu mới

```
🏠  Bảng điều khiển
🏆  Nhiệm vụ
📰  Tin tức
🏢  Doanh nghiệp
📈  Giao dịch
💬  Mentor
👥  Xã hội
📊  Cuộc thi
🔥  Heatmap
```

---

## P2-2: Header — Giảm độ nặng

### P2-2.1 — Format mới

```
NAV 100,02M  |  Cash 100M  |  Risk 50
```

### P2-2.2 — Tooltip khi hover

```tsx
<Tooltip content={
  <>
    NAV: 100.020.510 ₫<br/>
    Cash: 100.000.000 ₫<br/>
    Risk: 50/100 — Trung bình
  </>
}>
  <HeaderStats ... />
</Tooltip>
```

---

## P2-3: Typography hierarchy

### P2-3.1 — Định nghĩa

```css
/* Headline */
.font-headline { font-weight: 700; font-size: 1.25rem; }

/* Subheadline */
.font-subheadline { font-weight: 600; font-size: 1rem; }

/* Body */
.font-body { font-weight: 400; font-size: 0.875rem; }

/* Number */
.font-number { font-weight: 600; font-variant-numeric: tabular-nums; }

/* Metadata */
.font-meta { font-weight: 400; font-size: 0.75rem; opacity: 0.6; }
```

### P2-3.2 — Áp dụng

- [ ] Headlines: bold 700
- [ ] News titles: bold 700
- [ ] News summaries: regular 400
- [ ] Metadata (time, author): regular 400, smaller
- [ ] Numbers (giá, %): 600 + tabular-nums
- [ ] Không bold tất cả

---

## P2-4: Semantic Color System

### P2-4.1 — Định nghĩa trong theme

```ts
const semanticColors = {
  // Profit/Loss
  profit:    '#22c55e',  // xanh lá
  loss:      '#ef4444',  // đỏ

  // Sentiment
  positive:  '#22c55e',
  negative:  '#ef4444',
  neutral:   '#94a3b8',  // xám

  // Actions
  buy:       '#22c55e',
  sell:      '#ef4444',

  // System
  info:      '#3b82f6',  // xanh dương
  warning:   '#f59e0b',  // vàng
  success:   '#22c55e',
  danger:    '#ef4444',

  // UI
  active:    '#3b82f6',  // menu active → xanh dương
  link:      '#3b82f6',  // links → xanh dương
  badge:     '#3b82f6',  // badges → xanh dương
}
```

### P2-4.2 — Thay đổi

- [ ] Menu active: xanh dương (thay vì xanh lá)
- [ ] Links: xanh dương
- [ ] Badge/status: xanh dương
- [ ] Profit/loss: xanh lá/đỏ
- [ ] Warning/risk: vàng

---

## P2-5: Risk score redesign

### P2-5.1 — Component RiskIndicator

```tsx
<RiskIndicator score={50} />
// Hiển thị:
// RỦI RO    50/100    Trung bình
// có progress bar màu vàng
```

### P2-5.2 — Risk levels

```
  0-20:  Thấp        (xanh lá)
 21-50:  Trung bình  (vàng)
 51-80:  Cao         (cam)
 81-100: Rất cao     (đỏ)
```

---

## P2-6: Giảm border/card

### P2-6.1 — Thay đổi CSS

```css
/* Trước */
.card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-card);
}

/* Sau — chỉ cho những component thực sự cần card */
.card-featured {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-card);
}

/* Phần còn lại dùng background + spacing */
.section {
  padding: 16px;
  background: var(--bg-section);
  border-radius: 8px;
}
```

### P2-6.2 — Áp dụng

- [ ] Giữ card: Portfolio chart, Order book, Task progress
- [ ] Bỏ card: KPI values, Filter, Navigation, Footer text
- [ ] Dùng spacing thay border cho phần phụ

---

## P2-7: Responsive testing

### P2-7.1 — Breakpoints

```css
/* Desktop */
@media (min-width: 1920px) { /* extended */ }
@media (min-width: 1366px) { /* standard desktop */ }

/* Tablet */
@media (min-width: 1024px) and (max-width: 1365px) { /* sidebar collapse */ }
@media (min-width: 768px) and (max-width: 1023px) { /* tablet */ }

/* Mobile */
@media (max-width: 767px) { /* mobile stack */ }
```

### P2-7.2 — Checklist test

- [ ] 1920×1080 — desktop lớn
- [ ] 1536×864 — laptop
- [ ] 1366×768 — laptop phổ biến ← **bắt buộc ổn**
- [ ] 1280×720 — laptop nhỏ
- [ ] 1024×768 — tablet landscape
- [ ] 768×1024 — tablet portrait
- [ ] 390×844 — iPhone 14

### P2-7.3 — Xử lý sidebar

```
≥ 1366px: Sidebar full
1024-1365px: Sidebar collapse (icon only)
< 1024px: Sidebar overlay / hamburger
```

---

## P2-8: Task page — Giảm stamp

### P2-8.1 — Thay đổi

```tsx
// Trước
<Stamp text="ĐÃ ĐIỂM DANH" color="green" />

// Sau
<Badge variant="success" icon="✓">Đã điểm danh</Badge>

// Chỉ giữ stamp cho milestone đặc biệt
<Stamp text="🏆 HOÀN THÀNH" />
```

---

# PHASE 4 — 🧪 TESTING & QA

---

## QA-1: Smoke test toàn bộ flow

### QA-1.1 — Flow chính

- [ ] Login → Dashboard hiển thị đúng
- [ ] Dashboard → vào Trade → chart có dữ liệu
- [ ] Trade → đặt lệnh buy → confirmation hiện → lệnh được lưu
- [ ] Trade → đặt lệnh sell → confirmation hiện → lệnh được lưu
- [ ] Sau buy → Portfolio cập nhật, cash trừ đúng
- [ ] Sau sell → Portfolio cập nhật, cash cộng đúng
- [ ] Dashboard → NAV cập nhật đúng
- [ ] Refresh → dữ liệu vẫn giữ nguyên

### QA-1.2 — Flow phụ

- [ ] News → tất cả tin hiển thị đúng tên công ty, mã CP
- [ ] News → impact hiển thị đúng format
- [ ] Social → viral hiển thị đúng format
- [ ] Social → post có link đến mã CP
- [ ] Tasks → streak hiển thị đúng
- [ ] Tasks → progress bar cập nhật sau khi hoàn thành
- [ ] Mentor → response hiển thị đúng

---

## QA-2: Edge cases

- [ ] Mua với số tiền = 0
- [ ] Mua vượt cash
- [ ] Bán vượt số lượng sở hữu
- [ ] Bán CP không tồn tại trong portfolio
- [ ] Đặt lệnh với giá âm
- [ ] Đặt lệnh với số lượng âm
- [ ] Network error → hiển thị error state
- [ ] Empty portfolio → hiển thị empty state
- [ ] Chưa có tin tức → hiển thị empty state

---

## QA-3: Data consistency

- [ ] NAV trên header = NAV trên dashboard = NAV trên portfolio
- [ ] Cash trên header = Cash trên portfolio
- [ ] Giá trên Trade = Giá trên portfolio holdings
- [ ] Risk score hiển thị đúng trên header + portfolio
- [ ] Số lệnh đang chờ hiển thị đúng trên order book

---

# PHASE 5 — 📝 THUYẾT TRÌNH

---

## Presentation-1: Câu định vị

> **Capia** — môi trường mô phỏng đầu tư giúp người dùng học cách ra quyết định thông qua thị trường giả lập, nhiệm vụ, cộng đồng và AI Mentor.

---

## Presentation-2: 10 câu hỏi cần trả lời được

| # | Câu hỏi | Nguồn trả lời |
|---|---|---|
| 1 | Giá CP được sinh thế nào? | `priceSimulator.ts` — mô hình random walk với volatility |
| 2 | Dữ liệu realtime từ đâu? | WebSocket + simulated tick mỗi 3 giây |
| 3 | Refresh có mất portfolio không? | Lưu vào PostgreSQL, không chỉ frontend state |
| 4 | Lệnh lưu ở đâu? | Bảng `orders` trong PostgreSQL |
| 5 | Mua vượt tiền? | Validation trước khi submit — throw error |
| 6 | Bán vượt CP? | Validation — kiểm tra portfolio position |
| 7 | Limit order hoạt động? | Matching engine so sánh price với order book |
| 8 | Sentiment tính bằng gì? | Keyword matching + scoring algorithm |
| 9 | Risk score 50 tính bằng? | Volatility + portfolio concentration + drawdown |
| 10 | AI Mentor dùng AI? | Gemini API / multi-mode: static → rules → AI |

---

## Presentation-3: Demo script (5 phút)

```
1. [30s]  Giới thiệu: "Capia là môi trường mô phỏng đầu tư..."
2. [1m]   Dashboard: overview → NAV, tasks, top stocks
3. [1m]   Trade: xem chart → đặt lệnh → confirmation → order thành công
4. [30s]  Portfolio: kiểm tra vị thế → profit/loss cập nhật
5. [30s]  News: đọc tin → sentiment → impact → price reaction
6. [30s]  Social: xem post → linked trade → viral
7. [30s]  Mentor: chat → AI response
8. [30s]  Tasks: điểm danh → streak → reward
```

---

# TỔNG HỢP TASK LIST

## 🔴 P0 — Ưu tiên cao nhất (làm trước)

| # | Task | File liên quan | Trạng thái |
|---|---|---|---|
| P0-1.1 | Tạo `formatCurrency`, `formatPercent`... | `src/utils/format.ts` | ⬜ |
| P0-1.2 | Thay thế toàn bộ hardcoded display | Nhiều component | ⬜ |
| P0-2.1 | Tìm root cause `{name}` `{symbol}` | News component / mock | ⬜ |
| P0-2.2 | Sửa template/mapping | News component | ⬜ |
| P0-3.1 | Xác định timestamp leak | News/API | ⬜ |
| P0-3.2 | Sửa mapping impact | News component | ⬜ |
| P0-4.1 | Xác định viral % leak | Social/API | ⬜ |
| P0-4.2 | Sửa format viral | Social component | ⬜ |
| P0-5.1 | Tạo price simulator | `src/services/priceSimulator.ts` | ⬜ |
| P0-5.2 | Tích hợp chart component | Trade page | ⬜ |
| P0-6.1 | Tạo order book simulator | `src/services/orderBookSimulator.ts` | ⬜ |
| P0-6.2 | Hiển thị order book | Trade page | ⬜ |
| P0-7.1 | Validation buy/sell | Trade service | ⬜ |
| P0-7.2 | Cập nhật portfolio sau trade | Portfolio service | ⬜ |
| P0-8.1 | Test refresh persistence | Database | ⬜ |

## 🟠 P1 — Nâng UX (sau P0)

| # | Task | File liên quan | Trạng thái |
|---|---|---|---|
| P1-1.1 | Dashboard redesign layout | Dashboard page | ⬜ |
| P1-1.2 | Component PortfolioChart | `src/components/PortfolioChart.tsx` | ⬜ |
| P1-1.3 | Component TopStocks | `src/components/TopStocks.tsx` | ⬜ |
| P1-1.4 | Component RecentActivity | `src/components/RecentActivity.tsx` | ⬜ |
| P1-2.1 | Order confirmation modal | `src/components/OrderConfirmModal.tsx` | ⬜ |
| P1-3.1 | Order history component | `src/components/OrderHistory.tsx` | ⬜ |
| P1-4.1 | News metadata display | News component | ⬜ |
| P1-4.2 | Sentiment badge | `src/components/SentimentBadge.tsx` | ⬜ |
| P1-5.1 | Social post linked trade | Social component | ⬜ |
| P1-6.1 | Portfolio summary header | Portfolio component | ⬜ |
| P1-7.1 | Skeleton components | `src/components/Skeleton.tsx` | ⬜ |
| P1-7.2 | Empty state components | `src/components/EmptyState.tsx` | ⬜ |
| P1-7.3 | Error state components | `src/components/ErrorState.tsx` | ⬜ |

## 🟡 P2 — Visual polish (sau P1)

| # | Task | File liên quan | Trạng thái |
|---|---|---|---|
| P2-1.1 | Sidebar subtitle removal | Sidebar component | ⬜ |
| P2-2.1 | Header stats compact | Header component | ⬜ |
| P2-3.1 | Typography tokens | `src/styles/typography.css` | ⬜ |
| P2-3.2 | Áp dụng typography | Tất cả component | ⬜ |
| P2-4.1 | Semantic color tokens | `src/styles/colors.ts` | ⬜ |
| P2-4.2 | Thay đổi active/link/badge colors | Theme | ⬜ |
| P2-5.1 | Risk indicator redesign | `src/components/RiskIndicator.tsx` | ⬜ |
| P2-6.1 | Giảm border/card | CSS / component | ⬜ |
| P2-7.1 | Responsive breakpoints | `src/styles/responsive.css` | ⬜ |
| P2-7.2 | Test 1366×768 | Browser | ⬜ |
| P2-7.3 | Test mobile | Browser | ⬜ |
| P2-8.1 | Task page stamp → badge | Tasks component | ⬜ |

## 🧪 QA — Testing

| # | Task | Trạng thái |
|---|---|---|
| QA-1.1 | Smoke test flow chính | ⬜ |
| QA-1.2 | Smoke test flow phụ | ⬜ |
| QA-2.1 | Edge case: mua/bán invalid | ⬜ |
| QA-2.2 | Edge case: network error | ⬜ |
| QA-2.3 | Edge case: empty states | ⬜ |
| QA-3.1 | Data consistency cross-page | ⬜ |

---

## Timeline ước tính

| Phase | Thời gian | Deliverable |
|---|---|---|
| P0 | 2–3 ngày | Data đúng, trade chạy, chart có dữ liệu |
| P1 | 2–3 ngày | Dashboard mới, confirmation, order history |
| P2 | 1–2 ngày | Typography, colors, responsive |
| QA | 1 ngày | Smoke test, edge cases |
| **Tổng** | **6–9 ngày** | **Sản phẩm demo thuyết phục** |
