---
name: FinSimAI
description: Mô phỏng đầu tư chứng khoán — quầy giao dịch thời gian nén với AI Mentor Socratic.
colors:
  brass: "#C9A227"
  brass-deep: "#A8861C"
  brass-ink: "#8A6E15"
  brass-bright: "#DDB84A"
  paper: "#FFFDF8"
  slip: "#F8F5EF"
  slip-line: "#E3DCCB"
  ink-900: "#171610"
  ink-700: "#35322B"
  ink-500: "#6B6456"
  ink-400: "#787166"
  granite-950: "#0D0C0B"
  granite-900: "#171615"
  granite-800: "#211F1C"
  granite-700: "#2D2B27"
  granite-400: "#8B867C"
  granite-300: "#9E9A91"
  mkt-up: "#16A34A"
  mkt-up-bright: "#2AC364"
  mkt-down: "#DC2626"
  mkt-down-bright: "#F04949"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Aptos, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(2.5rem, 6vw, 3.5rem)"
    fontWeight: 900
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Aptos, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace"
    fontSize: "10px"
    fontWeight: 700
    letterSpacing: "0.12em"
    textTransform: "uppercase"
  micro:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.12em"
    textTransform: "uppercase"
rounded:
  slip: "10px"
  md: "8px"
  lg: "12px"
  sm: "2px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.brass}"
    textColor: "{colors.granite-950}"
    rounded: "{rounded.slip}"
    padding: "12px 24px"
  button-primary-hover:
    backgroundColor: "{colors.brass-bright}"
    textColor: "{colors.granite-950}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-700}"
    rounded: "{rounded.slip}"
    padding: "12px 24px"
  chip:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.ink-500}"
    rounded: "{rounded.slip}"
    padding: "4px 12px"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-900}"
    rounded: "{rounded.slip}"
  board:
    backgroundColor: "{colors.granite-950}"
    textColor: "{colors.granite-300}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-900}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: FinSimAI

## Overview

**Creative North Star: "Quầy giao dịch — The Branch Counter"**

FinSimAI is a bank branch rendered as a product. The app is the branch floor: a warm granite counter that runs the length of the screen, brass fittings as the only metal, and paper slips carrying every piece of content the visitor reads and fills. The world refuses two category defaults at once — the generic light fintech panel (crisp white, blue accent, pill everything) and the neon crypto terminal (pure black, saturated green, glassmorphism). Its DNA is the physical branch you already trust: rate boards tick over in mono numerals, a queue ticket clocks today's discipline, a teller (the AI Mentor) questions you before a risky order, and a filled slip comes back stamped.

Dark mode is the default and the signature: the night branch, where the counter reads as deep warm granite and brass catches the light. Light mode is the day branch — the same counter under natural light on paper. The toggle is preserved; the world does not pick light or dark by category.

Every action is a *giao dịch*: it is filled, stamped, and counted. Content is never weightless; state is never silent.

**Key Characteristics:**
- One accent metal (brass gold) on warm granite and paper; never a second hue.
- Numerals and data live only on inset dark rate boards, in mono.
- Confirmation is a physical stamp, animated with a hard stamp-down; never a ringed pill.
- Warm paper surfaces in light mode, warm granite counter in dark mode; nothing is pure `#ffffff` or pure black.
- VN market convention: up is green, down is red — treated as the branch's indicator lights.

## Colors

The palette is a branch interior: paper and granite neutrals, one brass metal, two market lights.

### Primary
- **Đồng thau (Brass)** (#C9A227): the only brand accent. Fills primary actions and the active nav plate, always with dark text (`granite-950`). Deeper variant `brass-deep` (#A8861C) for hover; `brass-bright` (#DDB84A) for dark-mode states. `brass-ink` (#8A6E15) is the light-mode text tone for brass-on-paper labels and links (passes 4.5:1 on paper).

### Secondary
- **Ánh đèn xanh (Market up)** (#16A34A, bright #2AC364): price increases, profit, "Sẵn sàng"/"Live" stamps.
- **Ánh đèn đỏ (Market down)** (#DC2626, bright #F04949): price decreases, losses, errors, like-hearts on the social feed.

### Neutral
- **Giấy phiếu (Paper)** (#FFFDF8): the content surface, light mode.
- **Giấy nền (Slip)** (#F8F5EF): the page ground, light mode.
- **Gạch ngang phiếu (Slip line)** (#E3DCCB): hairline dividers and borders on paper.
- **Đá granit (Granite) 950/900/800/700** (#0D0C0B → #2D2B27): dark-mode ground and counter surfaces; 900 for cards, 950 for the page ground and boards, 800 for raised chips, 700 for hairline borders on granite.
- **Mực (Ink) 900/700/500/400** (#171610 → #787166): light-mode text ramp; 900 headings, 700 body, 500 secondary, 400 meta/timestamps (deepened to hold 4.5:1 on paper).

### Named Rules
**The One Metal Rule.** Brass is the only accent. Its coverage stays modest and its message stays functional — it fills the action, the active nav plate, and nothing decorative.

**The Counter Rule.** Dark surfaces use granite, never black; light surfaces use paper, never white. Pure black and pure white do not exist in this system.

**The Market Lights Rule.** Up is green, down is red, always, per VN convention. Profit never turns the brass; losses never turn blue.

## Typography

**Display Font:** System sans (Segoe UI / Aptos / Roboto fallback) at weight 900, tracking -0.02em.
**Body Font:** Same system sans at 400, 14px, line-height 1.5.
**Label/Mono Font:** System mono (SFMono / Consolas) at 700, 10–11px, uppercase, tracking 0.12em.

**Character:** The branch does not ornament its lettering. Headings are the blocky, confident weight of signage; every numeral and every data label drops into mono as the board would. This pairing is the machine inside the comfortable room: bold human sans carries the message, mono carries the numbers.

### Hierarchy
- **Display** (900, clamp(2.5rem→3.5rem), 1.1): the landing hero and page titles (`PageHeader`), black weight only.
- **Headline** (900, 16–20px, 1.2): card titles, section titles; dark mode renders on `slip`.
- **Title** (700, 14px, 1.3): item titles, nav labels.
- **Body** (400, 14px, 1.5): prose, controls; measure capped near 65ch.
- **Label** (mono 700, 10–11px, tracking 0.12em, uppercase): board captions (`.board-label`), stamps, form labels (`.label`). The `label` step is 10px; the `micro` step is 11px for the stamp body and dense data labels (map axes, rank numerals, category chips).

### Named Rules
**The Board Rule.** Mono is for code, data, and measurement only. Numerals that mean something (prices, quantities, NAV, scores) render `tabular-nums` on mono; prose never switches faces. Nobody "technicals" the language.

**The Signage Rule.** Emphasis is weight, never decoration. No gradient text, no italic headlines, no letter-spaced body copy. A heading stands on its own weight or it is not a heading.

## Layout

The dashboard is a single branch floor: a fixed brass rail on the left (nav groups with mono board-label headers), a sticky counter header above (NAV / Cash boards and a risk stamp, theme toggle, user plate), and paper content in a centered container (`max-w-7xl`). The rail is the persistent frame; the header is the counter display; the content is the queue.

Spacing rhythm is tight inside groups (4–8px), generous between groups (16–24px), and more air above a heading than below it. Cards sit on the slip ground with a soft lift, never flush and never stacked nested. Tables are paper slips with `slip-line` hairline rows; numeric columns align right in mono.

Responsive: the rail collapses to an off-canvas drawer under `lg`; the header compresses its boards to a compact row on mobile; grids stack at one column. The trade surface (`/trade`) stays a 2-up composition of chart + order panel on desktop and stacks on mobile — the chart is not a detail, it is the branch's window.

## Elevation & Depth

Depth is a paper stack under a counter light: soft ambient shadows in light mode, and the inset, punched look of the rate boards. In dark mode, elevation is conveyed by granite tonal steps instead of shadow (cards are 900 on a 950 ground), keeping the night branch flat and calm.

### Shadow Vocabulary
- **Card** (`0 1px 2px rgb(13 12 11 / 0.18), 0 8px 24px -12px rgb(13 12 11 / 0.35)`): the paper slip's lift off the counter; light mode only.
- **Board** (`inset 0 1px 0 0 rgb(255 255 255 / 0.04), 0 1px 0 0 rgb(0 0 0 / 0.6)`): the inset rate-board panel; a display punched into the counter, never a floating card.
- **Press** (`inset 0 2px 4px rgb(13 12 11 / 0.3)`): the moment a plate is pressed (active nav plate, pressed buttons).

### Named Rules
**The No-Black-Cube Rule.** No hard offset shadows (`4px 4px 0`). The branch has a lighting model — soft paper lift and punched boards — and a costume block shadow is the one depth it never wears.

## Shapes

The form language is the branch counter and its paper. Surfaces are gently rounded at `10px` (radius token `slip`), controls at 8px, and the confirmation stamp at 2px — the stamp is a hard instrument, not a soft chip. Hairlines are `1px` in `slip-line` (light) or `granite-700` (dark).

Two signature silhouettes repeat across the product:
- **The Queue Ticket** (`.ticket` + `.ticket-notch`): a paper stub with two circular notches on the torn edge, used for streak/discipline state ("Số vé kỷ luật") — the visitor holds their number.
- **The Rate Board** (`.board`): a rounded inset dark panel with mono label and mono numerals, used for NAV, cash, bid/ask, and every counter metric.

## Components

### Buttons
- **Shape:** 10px radius; mono data never appears on buttons, text is bold sans.
- **Primary (Mua/Đăng ký/Đặt lệnh):** brass fill (`brass`), `granite-950` text, weight 700. Hover steps to `brass-bright`; press sinks via `press` shadow. The brass button is the action the branch wants you to take.
- **Secondary:** paper fill, hairline `slip-line`/`granite-600` border, `ink-700`/`granite-200` text; hover warms the border to brass. **Ghost:** no surface, brass-tinted hover.
- **Directional (Mua/Bán):** the buy/sell toggle is the one place the market lights drive an action — a full green fill for Mua, red for Bán, `granite-950`/white text as contrast dictates.

### Chips
- **Style:** `slip` paper with `ink-500` text in light mode; `granite-800` fill with `granite-300` text in dark. Filter chips, suggestion chips, category tags.
- **State:** selected = brass plate (`brass` fill, `granite-950` text); unselected = paper, brass border on hover.

### Cards / Containers
- **Corner Style:** 10px (`slip`).
- **Background:** `paper` in light, `granite-900` in dark.
- **Shadow Strategy:** `card` lift in light mode, none in dark (tonal step instead).
- **Border:** `1px slip-line` / `granite-700`.
- **Internal Padding:** 16–24px body; headers are a `slip-line` hairline row with a mono caption when the card is a board family.

### Inputs / Fields
- **Style:** paper fill, `ink-300`/`granite-600` hairline, 8px radius, `ink-900` text.
- **Focus:** brass border with a 25% brass ring; the pen touching the slip.
- **Error:** market-down border and message; **Disabled:** paper `ink-100` tint, dimmed.

### Navigation
- **Style:** the brass rail. Active item is a solid brass plate (`brass` fill, `granite-950` text) with a pressed shadow; inactive items are `granite-300`/`ink-500` text warming to brass on hover. Group headers are mono board-labels. Mobile: off-canvas drawer from the left.

### Signature Components
- **Rate Board** (`.board`): inset granite-950 panel, mono uppercase caption (`board-label`), mono `tabular-nums` value (`board-num`). Used for NAV, cash, bid/ask, quick stats, stat cards.
- **Queue Ticket** (`.ticket`/`.ticket-notch`): paper stub, two torn-edge notches, a mono serial number, and a stamp — the discipline card.
- **Confirmation Stamp** (`.stamp`/`.stamp-success`/`.stamp-danger`): 2px border, mono 11px uppercase, rotated -8°, stamped down with the `stamp-in` animation. "Hoàn thành", "Đã điểm danh", "Mô phỏng", "Sẵn sàng", "Live" — anything confirmed is stamped, never ringed.
- **Counter Header:** sticky row holding the NAV/Cash boards and the risk stamp (green "An toàn" / amber "Cẩn thận" / red "Rủi ro cao"), theme toggle, and user plate — the teller's side of the counter.

## Do's and Don'ts

### Do:
- **Do** render every number that means something on mono (`tabular-nums`) — prices, quantities, NAV, scores, timestamps that matter.
- **Do** stamp confirmations — completion, check-ins, live signals — with the rotated stamp and `stamp-in` motion; it is the branch's one authored moment.
- **Do** use paper (#FFFDF8) for light surfaces and granite-900/950 for dark surfaces; let borders be `slip-line` (light) or `granite-700` (dark).
- **Do** let market up/down drive green/red for prices, P&L, and buy/sell direction.
- **Do** keep the brass on the action and the active state; every other accent is a market light.

### Don't:
- **Don't** use pure white surfaces, pure black surfaces, or gradient text anywhere.
- **Don't** put an eyebrow or kicker label above a heading — the heading carries its own weight.
- **Don't** use hard offset shadows (`4px 4px 0`) or glassmorphism; depth is a paper lift and a punched board.
- **Don't** confirm with ringed pills or emoji; a confirmation is a stamp.
- **Don't** use mono as a costume for "technical" prose — mono is for data and measurement.
- **Don't** introduce a second accent hue; if it is not brass, it is a market light (green/red) or it is not accent.
