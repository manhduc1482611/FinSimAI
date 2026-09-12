---
name: FinSimAI
description: Mô phỏng đầu tư chứng khoán — bảng giao dịch thông minh với AI Mentor Socratic.
colors:
  brand: "#00E6D9"
  brand-bright: "#7FF7F0"
  brand-deep: "#00A69C"
  accent: "#6A7CFF"
  accent-deep: "#5261EE"
  paper: "#FBFFFE"
  slip: "#F1F9F8"
  slip-line: "#DAE9E7"
  ink-900: "#171C24"
  ink-700: "#2F3741"
  ink-500: "#55606D"
  ink-400: "#66727F"
  granite-950: "#0A0E14"
  granite-900: "#141A24"
  granite-800: "#1E2430"
  granite-700: "#2B3340"
  granite-400: "#7C8897"
  granite-300: "#A7B1BE"
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
    backgroundColor: "{colors.brand}"
    textColor: "{colors.granite-950}"
    rounded: "{rounded.slip}"
    padding: "12px 24px"
  button-primary-hover:
    backgroundColor: "{colors.brand-bright}"
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

**Creative North Star: "Bảng giao dịch thông minh — The Smart Terminal"**

FinSimAI is a digital trading terminal rendered as a calm, data-forward product. The app is a cool slate counter running the length of the screen with one vivid teal signal for every system action and one violet pulse for the AI Mentor's intelligence. The world refuses two defaults at once — the warm legacy bank counter (brass, paper, cream) and the loud crypto dashboard (neon green, black glass, holographic gradients). Its DNA is the focused terminal you already trust: rate boards tick over in mono numerals, a queue ticket clocks today's discipline, a violet teller (the AI Mentor) questions you before a risky order, and a filled slip comes back stamped.

Dark mode is the signature: a deep slate counter where teal signals and violet intelligence glow softly. Light mode is the same counter under diffused daylight on cool paper. The toggle is preserved; the world does not pick light or dark by category.

Every action is a *giao dịch*: it is filled, stamped, and counted. Content is never weightless; state is never silent.

**Key Characteristics:**
- Two signals on cool neutrals: teal for system/action, violet for AI/intelligence; never a third accent.
- Numerals and data live only on inset dark rate boards, in mono.
- Confirmation is a physical stamp, animated with a hard stamp-down; never a ringed pill.
- Cool paper surfaces in light mode, deep slate counter in dark mode; nothing is pure `#ffffff` or pure black.
- VN market convention: up is green, down is red — treated as the terminal's indicator lights.

## Colors

The palette is a focused terminal: cool slate and paper neutrals, one teal signal, one violet intelligence, two market lights.

### Primary
- **Hệ thống (Brand teal)** (#00E6D9): system signal and primary action. Fills primary buttons, the active nav plate, focus rings, and buy-side accents, always with dark text (`granite-950`). `brand-400` (#23EBE1) for mid-bright states; `brand-bright` (#7FF7F0) for dark-mode glow and light-mode tints; `brand-deep` (#00A69C) for borders and stamp outlines in light mode. The teal button is the action the terminal wants you to take.

### Intelligence
- **Trí tuệ (Accent violet)** (#6A7CFF): AI Mentor surfaces and intelligence labels. `accent-400` (#8394FC) for dark-mode mentor accents; `accent-deep` (#5261EE) for mentor chat chips and concept cards. Violet appears only where the system is thinking, teaching, or challenging — never on generic system actions.

### Secondary
- **Ánh đèn xanh (Market up)** (#16A34A, bright #2AC364): price increases, profit, "Sẵn sàng"/"Live" stamps.
- **Ánh đèn đỏ (Market down)** (#DC2626, bright #F04949): price decreases, losses, errors, like-hearts on the social feed.

### Neutral
- **Giấy phiếu (Paper)** (#FBFFFE): the content surface, light mode — cool near-white.
- **Giấy nền (Slip)** (#F1F9F8): the page ground, light mode — faint aqua tint.
- **Gạch ngang phiếu (Slip line)** (#DAE9E7): hairline dividers and borders on paper — cool mist.
- **Đá granit (Granite) 950/900/800/700** (#0A0E14 → #2B3340): dark-mode ground and counter surfaces; 900 for cards, 950 for the page ground and boards, 800 for raised chips, 700 for hairline borders on granite — blue-black slate.
- **Mực (Ink) 900/700/500/400** (#171C24 → #66727F): light-mode text ramp; 900 headings, 700 body, 500 secondary, 400 meta/timestamps (deepened to hold 4.5:1 on paper).

### Named Rules
**The Two-Signal Rule.** Teal is the system action; violet is the AI intelligence. Teal fills the buy button, the active nav, and every "go" state. Violet fills the mentor chat header, concept cards, and every "think" state. Market lights (green/red) are the only other hues that receive accent treatment.

**The Counter Rule.** Dark surfaces use granite, never black; light surfaces use paper, never white. Pure black and pure white do not exist in this system.

**The Market Lights Rule.** Up is green, down is red, always, per VN convention. Profit never turns teal; losses never turn violet.

## Typography

**Display Font:** System sans (Segoe UI / Aptos / Roboto fallback) at weight 900, tracking -0.02em.
**Body Font:** Same system sans at 400, 14px, line-height 1.5.
**Label/Mono Font:** System mono (SFMono / Consolas) at 700, 10–11px, uppercase, tracking 0.12em.

**Character:** The terminal does not ornament its lettering. Headings are the blocky, confident weight of signage; every numeral and every data label drops into mono as the board would. This pairing is the machine inside the calm room: bold human sans carries the message, mono carries the numbers.

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

The dashboard is a single terminal floor: a fixed slate rail on the left (nav groups with mono board-label headers), a sticky counter header above (NAV / Cash boards and a risk stamp, theme toggle, user plate), and cool paper content in a centered container (`max-w-7xl`). The rail is the persistent frame; the header is the counter display; the content is the queue.

Spacing rhythm is tight inside groups (4–8px), generous between groups (16–24px), and more air above a heading than below it. Cards sit on the slip ground with a soft lift, never flush and never stacked nested. Tables are paper slips with `slip-line` hairline rows; numeric columns align right in mono.

Responsive: the rail collapses to an off-canvas drawer under `lg`; the header compresses its boards to a compact row on mobile; grids stack at one column. The trade surface (`/trade`) stays a 2-up composition of chart + order panel on desktop and stacks on mobile — the chart is not a detail, it is the terminal's window.

## Elevation & Depth

Depth is a paper stack under a terminal light: soft ambient shadows in light mode, and the inset, punched look of the rate boards. In dark mode, elevation is conveyed by granite tonal steps instead of shadow (cards are 900 on a 950 ground), keeping the night terminal flat and calm.

### Shadow Vocabulary
- **Card** (`0 1px 2px rgb(13 12 11 / 0.18), 0 8px 24px -12px rgb(13 12 11 / 0.35)`): the paper slip's lift off the counter; light mode only.
- **Board** (`inset 0 1px 0 0 rgb(255 255 255 / 0.04), 0 1px 0 0 rgb(0 0 0 / 0.6)`): the inset rate-board panel; a display punched into the counter, never a floating card.
- **Press** (`inset 0 2px 4px rgb(13 12 11 / 0.3)`): the moment a plate is pressed (active nav plate, pressed buttons).

### Named Rules
**The No-Black-Cube Rule.** No hard offset shadows (`4px 4px 0`). The terminal has a lighting model — soft paper lift and punched boards — and a costume block shadow is the one depth it never wears.

## Shapes

The form language is the terminal counter and its paper. Surfaces are gently rounded at `10px` (radius token `slip`), controls at 8px, and the confirmation stamp at 2px — the stamp is a hard instrument, not a soft chip. Hairlines are `1px` in `slip-line` (light) or `granite-700` (dark).

Two signature silhouettes repeat across the product:
- **The Queue Ticket** (`.ticket` + `.ticket-notch`): a paper stub with two circular notches on the torn edge, used for streak/discipline state ("Số vé kỷ luật") — the visitor holds their number.
- **The Rate Board** (`.board`): a rounded inset dark panel with mono label and mono numerals, used for NAV, cash, bid/ask, and every counter metric.

## Components

### Buttons
- **Shape:** 10px radius; mono data never appears on buttons, text is bold sans.
- **Primary (Mua/Đăng ký/Đặt lệnh):** brand-teal fill (`brand-500`), `granite-950` text, weight 700. Hover steps to `brand-bright` (#7FF7F0); press sinks via `press` shadow. The teal button is the action the terminal wants you to take.
- **Secondary:** paper fill, hairline `slip-line`/`granite-600` border, `ink-700`/`granite-200` text; hover warms the border to teal. **Ghost:** no surface, teal-tinted hover.
- **Directional (Mua/Bán):** the buy/sell toggle is the one place the market lights drive an action — a full green fill for Mua, red for Bán, `granite-950`/white text as contrast dictates.

### Chips
- **Style:** `slip` paper with `ink-500` text in light mode; `granite-800` fill with `granite-300` text in dark. Filter chips, suggestion chips, category tags.
- **State:** selected = teal plate (`brand-500` fill, `granite-950` text); unselected = paper, teal border on hover. AI/Mentor mode chips use violet (`accent-500`) when selected.

### Cards / Containers
- **Corner Style:** 10px (`slip`).
- **Background:** `paper` in light, `granite-900` in dark.
- **Shadow Strategy:** `card` lift in light mode, none in dark (tonal step instead).
- **Border:** `1px slip-line` / `granite-700`.
- **Internal Padding:** 16–24px body; headers are a `slip-line` hairline row with a mono caption when the card is a board family.

### Inputs / Fields
- **Style:** paper fill, `ink-300`/`granite-600` hairline, 8px radius, `ink-900` text.
- **Focus:** teal border with a 25% teal ring; the pen touching the slip.
- **Error:** market-down border and message; **Disabled:** paper `ink-100` tint, dimmed.

### Navigation
- **Style:** the slate rail. Active item is a solid teal plate (`brand-500` fill, `granite-950` text) with a pressed shadow; inactive items are `granite-300`/`ink-500` text warming to teal on hover. Group headers are mono board-labels. Mobile: off-canvas drawer from the left.

### Signature Components
- **Rate Board** (`.board`): inset granite-950 panel, mono uppercase caption (`board-label`), mono `tabular-nums` value (`board-num`). Used for NAV, cash, bid/ask, quick stats, stat cards.
- **Queue Ticket** (`.ticket`/`.ticket-notch`): paper stub, two torn-edge notches, a mono serial number, and a stamp — the discipline card.
- **Confirmation Stamp** (`.stamp`/`.stamp-success`/`.stamp-danger`): 2px border, mono 11px uppercase, rotated -8°, stamped down with the `stamp-in` animation. "Hoàn thành", "Đã điểm danh", "Mô phỏng", "Sẵn sàng", "Live" — anything confirmed is stamped, never ringed. Default stamp color is teal; success/danger stamps remain green/red per market lights.
- **Counter Header:** sticky row holding the NAV/Cash boards and the risk stamp (green "An toàn" / amber "Cẩn thận" / red "Rủi ro cao"), theme toggle, and user plate — the teller's side of the counter.
- **Mentor Card** (`.concept-card`): violet-tinted border (`accent-500/30`) with mono formula line, used for AI concept explanations, strategy cards, and challenge cards — the violet voice of the Mentor.

## Do's and Don'ts

### Do:
- **Do** render every number that means something on mono (`tabular-nums`) — prices, quantities, NAV, scores, timestamps that matter.
- **Do** stamp confirmations — completion, check-ins, live signals — with the rotated stamp and `stamp-in` motion; it is the terminal's one authored moment.
- **Do** use paper (#FBFFFE) for light surfaces and granite-900/950 for dark surfaces; let borders be `slip-line` (light) or `granite-700` (dark).
- **Do** let market up/down drive green/red for prices, P&L, and buy/sell direction.
- **Do** keep teal on the action and the active state, and violet on the AI mentor surfaces; every other accent is a market light.

### Don't:
- **Don't** use pure white surfaces, pure black surfaces, or gradient text anywhere.
- **Don't** put an eyebrow or kicker label above a heading — the heading carries its own weight.
- **Don't** use hard offset shadows (`4px 4px 0`) or glassmorphism; depth is a paper lift and a punched board.
- **Don't** confirm with ringed pills or emoji; a confirmation is a stamp.
- **Don't** use mono as a costume for "technical" prose — mono is for data and measurement.
- **Don't** introduce a third accent hue; if it is not teal (system) or violet (AI), it is a market light (green/red) or it is not accent.
