# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase already answers this: Next.js 14 (App Router) + TailwindCSS + Zustand, TypeScript. Backend is a FastAPI gateway + gRPC math engine + AI engine (Gemini with deterministic fallback); realtime via WebSocket. No stack change needed.

## Users

[Inferred — user told me to proceed without answering the interview round; confirmed by repo copy, task blurbs, and mentor prompts.]
Primary: individual beginner investors in Vietnam (F0) who want to train investing discipline before risking real money. They use the product alone on desktop and phone. Secondary: contest participants competing in simulated arenas; admin/host operators running content, contests, and users.

## Product Purpose

FinSimAI is a simulated stock market where all news, companies, prices, and social posts are AI-generated from real-market context, plus a Socratic AI Mentor that challenges (never recommends) trading decisions. It exists to let people practice investing and train discipline in a safe, time-compressed environment. Success means a user completes the read → explore → trade loop daily, builds consistent habits (check-in streaks, tasks), and makes better-reasoned trades over time.

## Positioning

[Inferred positioning distilled from README mechanics.]
A closed-loop simulated market: real news drives AI-written stories, which move company financials and prices, which trigger social noise and penalties — so behavior has consequences inside a sandbox. The Socratic Mentor policy forbids buy/sell recommendations and correctness verdicts; it questions decisions to expose psychological bias (FOMO, panic selling). No real-money product truthfully combines "AI-generated market from real context" with a mentor that refuses to advise.

## Operating Context

- Core loop: (1) read news on /news (AI articles with sentiment, impact level, knowledge tags), (2) explore companies on /companies (financials, charts, health score, related news/social), (3) trade on /trade (order book, candles, orders, portfolio), with the Mentor at /trade/mentor.
- Social feed (/social) injects deliberate noise: fake KOLs, pump-and-dump "lùa gà", rumors, insider tips; users must verify against data before trading.
- Discipline mechanics: daily check-in, tasks/rewards, streak; penalties suspend trading and deduct discipline points on FOMO/panic behavior.
- Time compression: a trading day compresses into a short real session; prices stream in realtime via WebSocket.
- Roles: user, admin, host; each gets its own portal/navigation.
- UI language is Vietnamese throughout; money shown in VND.

## Capabilities and Constraints

Confirmed surfaces in code: landing page, login/register, dashboard, news list+detail, companies list+detail, trade terminal (symbol strip, candlestick chart, order book, trade panel, portfolio, order table), mentor chat (streaming), social feed, tasks & rewards, contests list+detail, admin portal (content/contests/users), host portal (contests).
- Realtime WebSocket channels: prices, trade fills/order updates, mentor streaming.
- Light/dark theme toggle exists today (dark mode via class); mobile responsive is expected.
- 100% type safety (no `any`), TypeScript strict, tsc typecheck is the verification gate (`npm run typecheck`).
- API base URL auto-derived for LAN device testing; token stored in localStorage.
- The brand name and Vietnamese copy are confirmed and must be preserved.
- Knowledge-base tags (concepts) are static and free; three touchpoints: news badges, company "apply" actions, trade reminders.

## Brand Commitments

- Name: FinSimAI (wordmark "FinSim" + "AI").
- UI copy is Vietnamese; formality is warm-but-serious (mentor, discipline, "rèn kỷ luật").
- The incumbent emerald-on-slate "fintech" look is the current implementation; this redesign replaces it rather than polishes it. No other external brand assets or logos exist.

## Evidence on Hand

- README.md and ROADMAP.md at repo root: product mechanics, user journey, feature list, backend status.
- apps/frontend/src: full incumbent implementation (App Router pages, components, stores, hooks, services).
- Backend enforces mentor policy (no buy/sell advice) — do not fabricate any recommendation claims in UI.
- No real customer testimonials, benchmarks, or case studies exist; do not invent them.

## Product Principles

1. Discipline over returns — the product trains process and habit; the UI should make streaks, tasks, and discipline-state visible and rewarding, never noisy hype.
2. Learn-then-apply — knowledge surfaces at the moment of reading/acting; the interface should connect news → company → trade as one journey.
3. Simulated but consequential — choices have real in-sim consequences (price moves, penalties); the UI must feel alive and honest about being a simulation.
4. The mentor challenges, never recommends — anywhere trade advice could appear, the voice is a question, not an answer.
5. Vietnamese-first — copy, currency, and market framing (VN-style price steps, VND) are product truth.

## Accessibility & Inclusion

[Not confirmed; assumed baseline.]
Follow standard web accessibility (contrast, focus, semantic HTML, keyboard-usable controls). No product-specific accessibility requirement was established in repo evidence.
