# FinSimAI — Kế hoạch cải tiến toàn diện

> Ngày lập: 2026-08-21 · Dựa trên rà soát codebase thực tế (math_engine, backend_gateway,
> ai_engine, frontend) + critique `.impeccable/critique/2026-08-10T15-07-43Z__apps-frontend.md`
> (24/40 điểm) + ROADMAP.md.
>
> Quy ước ưu tiên: **P0** = làm ngay (ảnh hưởng tính trung thực/tin cậy) · **P1** = quan trọng ·
> **P2** = nâng cao trải nghiệm. Mỗi hạng mục có: mô tả, file liên quan, tiêu chí chấp nhận (AC).

---

## PHẦN A — AI MENTOR (ưu tiên cao nhất)

### Trạng thái hiện tại

| Thành phần | File | Trạng thái |
|---|---|---|
| Agent Gemini + schema + retry | `apps/ai_engine/agents/socratic_mentor.py` | ✅ Hoạt động |
| Prompt store v3.1.0 | `apps/ai_engine/prompts/mentor_prompts.yaml` | ✅ Tốt |
| Policy scanner keyword | `apps/ai_engine/agents/policy.py` | ⚠️ Keyword đơn giản |
| Fallback deterministic 0-token | `apps/backend_gateway/realtime/mentor_engine.py` | ⚠️ Trùng lặp nội dung với YAML |
| WS mentor streaming | `apps/backend_gateway/realtime/mentor_ws.py` | ✅ Hoạt động |
| REST router + history 6 tin | `apps/ai_engine/routers/mentor.py` | ⚠️ History client-side, không lưu DB |
| Gemini client (temp 0.6) | `apps/ai_engine/integrations/gemini.py:56` | ⚠️ Free tier 20 req/ngày |

### A1. [P0] Nền tảng model & chi phí

- **A1.1** Giữ Gemini làm primary (`gemini-2.5-flash`), kiến trúc đã có lớp trừu tượng
  `GeminiClient` — bổ sung env `GEMINI_MODEL` để swap model không sửa code.
- **A1.2** Nâng quota: free tier 20 req/ngày chỉ đủ demo. Khi lên production 500 DAU × ~5
  câu/ngày ≈ 2.500 req/ngày → bật paid tier (~$0.30/1M token input ≈ **$1–3/ngày**).
- **A1.3** Per-user rate limit trên WS mentor: 10 câu/phút, 100 câu/ngày (tận dụng
  `core/ratelimit.py`). AC: user spam bị chặn, trả frame error chuẩn, không sập worker.
- **A1.4** Cache phản hồi theo `hash(context + message)` TTL 10 phút trên Redis — tiết kiệm
  quota + tăng nhất quán khi user hỏi lại cùng câu. AC: hit-rate đo được qua log.

### A2. [P0] Chống hallucination — kiến trúc 5 lớp

Hiện có 3 lớp, bổ sung 2 lớp:

| Lớp | Cơ chế | Trạng thái |
|---|---|---|
| 1 | Prompt policy (cấm mua/bán, đúng/sai, bịa số liệu) | ✅ `mentor_prompts.yaml:19-24` |
| 2 | Pydantic schema + validator loại output sai | ✅ `socratic_mentor.py:42-92` |
| 3 | Policy scanner keyword tiếng Việt | ⚠️ Cần mở rộng (A2.1) |
| 4 | **LLM-as-judge** kiểm tra độc lập trước khi phát | ❌ Mới (A2.2) |
| 5 | Fallback deterministic 0-token luôn an toàn | ✅ Có, cần refactor (A3.3) |

- **A2.1 Mở rộng policy scanner**: thêm từ khóa biến thể ("nên cân nhắc mua", "kèo tốt",
  "giải ngân", "gom", "xả", "chốt", "đánh vào"...); xử lý văn bản **không dấu** (normalize
  bỏ dấu trước khi quét — tham khảo cách `utils/knowledge_matcher.ts` phía frontend).
  AC: golden-set test gồm ≥30 câu lách luật đều bị chặn.
  ✅ *Xong 2026-08-21 — `agents/policy.py` chuẩn hoá NFD + đ→d, ~30 pattern mới viết dạng
  không dấu kèm tân ngữ chống báo nhầm; golden-set 36 câu lách luật + 8 câu hợp lệ trong
  `tests/test_policy_golden.py`.*
- **A2.2 LLM-as-judge (lớp 4)**: sau khi agent sinh reply, gọi 1 request flash rẻ tiền với
  prompt judge: "Reply này có vi phạm: khuyến nghị mua/bán, phán xét đúng/sai, bịa số liệu
  không có trong context?" — trả JSON `{violation: bool, reason}`. Vi phạm → retry 1 lần
  → vẫn lỗi thì dùng fallback deterministic. Chi phí tăng ~30% token nhưng bảo đảm ranh giới.
  AC: judge chặn được reply mà scanner keyword bỏ sót (test với 10 case thật).
- **A2.3 Grounding số liệu**: số liệu portfolio/giá phải do hệ thống tính sẵn và inject dạng
  text vào `{{context}}`; prompt cấm LLM tự tính toán; kiểm tra hậu kỳ: mọi con số xuất hiện
  trong reply phải tồn tại trong context (regex extract + so khớp). AC: test phát hiện reply
  chứa số lạ bị loại.
- **A2.4 Golden-set eval suite**: tạo `apps/ai_engine/tests/golden/*.yaml` — ≥50 hội thoại
  chuẩn (input message + context → kỳ vọng: pass policy, đúng schema, focus thuộc tập hợp
  chấp nhận, không chứa số ngoài context). Chạy bằng pytest, đưa vào CI. Đây là công cụ
  chống regression chất lượng khi đổi prompt/model. AC: `pytest apps/ai_engine -m golden` xanh.

### A3. [P0] Nhất quán & hạ tầng hội thoại

- **A3.1 Hạ temperature 0.6 → 0.3** cho mentor (creative không cần thiết, nhất quán quan trọng
  hơn). File: `integrations/gemini.py:56`. ✅ *Xong 2026-08-21.*
- **A3.2 Lưu session vào DB**: bảng mới `mentor_messages(id, user_id, session_id, role,
  content, focus, prompt_version, created_at)` — thay history client-side 6 tin. Lợi ích:
  continuity giữa các phiên, dữ liệu cho cá nhân hóa (A4.2) và kiểm toán (A5.3).
  AC: reload trang vẫn thấy hội thoại cũ; history gửi cho LLM lấy từ DB (12 tin gần nhất).
- **A3.3 Xóa duplicate question-bank**: `mentor_engine.py` copy tay toàn bộ nội dung YAML →
  drift chắc chắn xảy ra khi sửa một bên. Refactor: gateway load YAML từ package chung
  (hoặc sync script + test so khớp 2 nguồn). AC: test assert nội dung 2 bên giống hệt nhau.
  ✅ *Xong 2026-08-21 — chọn phương án sync test: `backend_gateway/tests/test_mentor_content_sync.py`
  assert priority_order/detection/question_bank/disclaimer giống hệt YAML.*
- **A3.4 Ghi `prompt_version` + `model` vào mỗi response/log** để truy vết chất lượng theo
  phiên bản prompt (YAML đã có `meta.version`).

### A4. [P1] Cá nhân hóa & chất lượng

- **A4.1 Nhận diện tiếng Việt không dấu/nhầm dấu** ở detect_focus + policy scanner
  (normalize trước khi so khớp). Hiện "fomo" match được nhưng "bo lo" không match "bỏ lỡ".
- **A4.2 Cá nhân hóa theo lịch sử**: chọn focus dựa trên trap_events của user (user hay
  FOMO → ưu tiên câu hỏi FOMO), tránh lặp lại đúng 3 câu cũ: question-bank chọn câu chưa hỏi
  trong session (hiện fallback luôn trả cùng 3 câu → lặp máy móc). AC: 2 lần hỏi liên tiếp
  cùng chủ đề cho 2 bộ câu khác nhau.
- **A4.3 Telemetry**: log mỗi lượt mentor: focus, latency, token usage, nguồn
  (gemini/fallback/judge-retry), violation count. Aggregate tuần vào admin portal.
  AC: dashboard admin thấy fallback-rate < 20% mục tiêu.
- **A4.4 Proactive mentor (nối retention)**: 1 câu hỏi tự vấn/ngày sinh từ
  `insight_prompts.yaml` + hành vi gần nhất của user (vd: vừa đặt lệnh sau tin giật gân →
  "Lệnh vừa rồi của bạn dựa trên nguồn tin nào?"). Push kèm daily digest (Phần E).

### A5. [P0] Ranh giới giáo dục – tư vấn

Nguyên tắc kiến trúc giữ nguyên: **mentor chỉ đặt câu hỏi, không bao giờ khuyến nghị,
không phán xét đúng/sai** — đây chính là ranh giới pháp lý (không cấu thành "khuyến nghị
đầu tư").

- **A5.1** Disclaimer bắt buộc mỗi response (đã có `_DISCLAIMER`) + nhãn UI cố định ở đầu
  panel chat: "Mentor không khuyến nghị mua/bán — chỉ giúp bạn phản biện quyết định của mình".
  ✅ *Xong 2026-08-21 — nhãn cố định trong header `MentorChat.tsx`.*
- **A5.2** Hội thoại Socratic chuẩn (đưa vào golden set làm benchmark):

> **User:** VCB đang tăng 3 phiên liền, mình nên bán chưa?
> **Mentor:** *(focus: anchoring)* Bạn quyết định bán dựa trên điều gì — kế hoạch bạn đặt
> trước khi mua, hay mức giá hôm nay? Nếu giá tăng thêm 3 phiên nữa, tiêu chí bán của bạn
> thay đổi gì?
> **User:** Thì chắc bán để chốt lời.
> **Mentor:** "Chắc chắn" đến từ dữ liệu nào bạn đang có? Và nếu người khác giữ vị thế này,
> bạn sẽ hỏi họ điều gì trước khi họ hành động?

- **A5.3** Kiểm toán định kỳ: sample ngẫu nhiên 5% hội thoại/tuần review thủ công theo
  checklist (vi phạm policy? hữu ích? đúng focus?). Ghi kết quả vào issue tracker.

---

## PHẦN B — MÔ PHỎNG CHI TIẾT (realism engine)

### Trạng thái hiện tại

| Yếu tố | Trạng thái | Bằng chứng |
|---|---|---|
| Biên độ ±7% | ✅ | `price_generator.py:35` |
| Bước giá VN | ✅ | `_apply_vn_tick_size()` |
| Jump shock | ✅ khung | `jump_lambda/mu/sigma` + `external_shock` |
| Phí giao dịch | ❌ | `Transaction.fee` luôn 0, không tính lúc fill |
| Thuế bán 0.1% | ❌ | Không có |
| Slippage | ❌ | Market order khớp đúng market_price |
| Thanh khoản | ⚠️ | Market maker fill không giới hạn khối lượng |
| T+2 | ❌ | Tiền bán về cash ngay (`trading_service.py:181`) |
| Corporate events | ❌ | `shares_outstanding` tĩnh |

### Tasks

- **B1. [P0] Phí + thuế**: phí 0.15% cả 2 chiều + thuế 0.1% chiều bán. Trừ vào
  `cash_balance` lúc fill, ghi `Transaction.fee` (+ cột `tax`). Hiển thị rõ trong confirm
  sheet + lịch sử giao dịch. AC: unit test tính đúng làm tròn; UI hiển thị phí từng lệnh.
  Ước lượng: 1 ngày.
  ✅ *Xong 2026-08-21 — `_trade_costs()` + fill trừ/cộng ròng, freeze mua gồm buffer phí;
  migration 0007 cột `tax`; WS trade feed trả fee/tax; TradePanel hiện giá trị lệnh + phí +
  thuế + tổng chi/thực nhận; test `test_trade_costs.py`.*
- **B2. [P1] Slippage**: lưu volume mô phỏng mỗi tick (ADV rolling 20 sim-day);
  market order khớp `price × (1 ± k·√(qty/ADV))`, k≈0.1. AC: lệnh lớn khớp giá xấu hơn lệnh
  nhỏ cùng lúc; test chứng minh.
- **B3. [P1] T+2 settlement**: cột `settling_cash` ở User; bán xong tiền về settling,
  worker theo sim-day chuyển sang khả dụng sau 2 sim-day. UI hiển thị 3 số: khả dụng /
  đang về / đóng băng. AC: bán xong không mua được ngay bằng tiền chưa về.
- **B4. [P1] Corporate events**: bảng `corporate_actions(company_id, type[dividend|split|
  rights], ex_date_sim, cash_per_share|ratio)`; worker quét theo sim-day: cổ tức → cộng
  cash theo CP giữ; split → điều chỉnh quantity + average_buy_price. Tin sự kiện sinh kèm
  (scenario_prompts) để giá phản ứng trước ex-date. AC: cổ tức đúng số tiền, NAV không
  nhảy oan.
- **B5. [P2] Giới hạn thanh khoản market maker**: mỗi tick MM chỉ hấp thụ tối đa X% volume
  mô phỏng; phần còn lại chờ khớp các tick sau. AC: lệnh 10× volume trung bình không khớp
  ngay toàn bộ.

### Dữ liệu & pháp lý

- **Giá**: GBM tổng hợp + công ty hư cấu (`companies.yaml`: TECHA, FINA…) → không cần
  license, chi phí 0₫, an toàn pháp lý. **Giữ hướng này** cho bản giáo dục.
- **Tin tức**: RSS Google News + VnExpress (`news_sources.py`). Rủi ro: Google News RSS ToS
  hạn chế dùng thương mại. An toàn hơn: chỉ giữ tiêu đề + link gốc (đã làm), hoặc chuyển hẳn
  tin sinh bởi Gemini gắn công ty hư cấu (đã có `scenario_tasks.py`) — khuyến nghị chuyển dần.
- **Chi phí AI**: xem A1.2 (~$1–3/ngày ở 500 DAU).

---

## PHẦN C — TIME COMPRESSION & LOOK-AHEAD BIAS

### Cơ chế hiện tại (đúng hướng)

- Giá sinh **tuần tự** theo tick — tương lai chưa tồn tại nên không thể lộ
  (`market_sim.py:159-170`); batch path chỉ dùng test.
- Leader-only writer (fail-closed), `MAX_DT_SECONDS` chặn nhảy giá sau downtime,
  ratio 1440 (1 phút thực = 1 ngày sim).

### Lỗ hổng đã xác nhận

1. **Không filter as-of**: news/social chỉ `ORDER BY simulated_at DESC`
   (`api/v1/news.py:31`, `social.py:84`) — nội dung sinh trước có thể lộ sớm.
2. **Lẫn lịch thật/sim**: `api/v1/social.py:133` gán `simulated_at=datetime.now(utc)`
   (giờ thật) trong khi sim clock neo 2026-01-01 ratio 1440 → hai hệ quy chiếu.
3. **Mentor context** chưa cắt theo mốc sim time.

### Tasks

- **C1. [P0] Một hàm `sim_now()` duy nhất** làm chuẩn toàn hệ thống (gateway + workers).
  ✅ *Xong 2026-08-21 — `realtime/simtime.py:sim_now()`; news/social/contests/ai_sync đã chuyển.*
- **C2. [P0] Filter as-of**: mọi API đọc + mentor context bắt buộc
  `WHERE simulated_at <= sim_now()`. AC: unit test assert không row nào trả về có
  `simulated_at > sim_now()`.
  ✅ *Xong 2026-08-21 — list+detail news/social, contest news/social; test `test_asof_filters.py`.
  ⏳ Mentor context chưa cắt theo mốc sim time (nối với A3.2 session DB).*
- **C3. [P1] Pipeline draft/publish**: nội dung AI sinh trước lưu `draft` +
  `publish_at` (sim time); worker chuyển `published` đúng hạn. AC: bài viết không xuất hiện
  trước publish_at dù đã tồn tại trong DB.
- **C4. [P0] Sửa `social.py:133`** dùng `sim_now()` thay `datetime.now(utc)`.
  ✅ *Xong 2026-08-21.*

---

## PHẦN D — UX/UI (từ critique 24/40)

- **D1. [P0] Thực thi brass accent**: DESIGN.md khai báo brass #C9A227 nhưng
  `tailwind.config.js` chỉ có brand xanh (#1F9E5F) → nút "Đặt lệnh" trùng màu đèn "giá tăng"
  (#16A34A). Thêm token brass 4 mức; remap primary buttons, active nav, stamps, focus ring;
  giữ xanh riêng cho mkt-up. Sweep mọi `bg-brand-500`.
- **D2. [P1] Niềm tin dữ liệu**: confirm sheet lấy giá REST cũ (`TradePanel.tsx:72`) trong
  khi chart chạy WS live → sync panel từ `priceStream.snapshot` + nhãn "giá lúc hh:mm:ss";
  render banner "mất kết nối / giá tạm dừng từ hh:mm:ss" từ `lastError` (đã có, chưa render).
- **D3. [P1] Teaser cho khách chưa đăng nhập** (nhận xét mentor): landing cards hiện bounce
  thẳng `/login` → làm chế độ xem thử: giá delay 15 phút + 3 tin mới + danh mục demo, CTA
  đăng ký để giao dịch.
- **D4. [P1] Pagination** mọi list (news cap 20, companies 60, social 50, admin 100) —
  load-more nhận biết server.
- **D5. [P2] Onboarding**: tour chào mừng 1 lần → dẫn tới `/news`; CTA check-in lên
  dashboard; NAV/risk hiển thị cả mobile (Header ẩn dưới `sm`).
- **D6. [P2] Accessibility**: drawer đóng vẫn trong tab-order (thêm `inert`/`aria-hidden`);
  Escape + focus trap cho overlay; map bubbles reachable bàn phím; RiskBadge `title=` →
  tooltip visible trên touch; đậm hơn xanh-up (#16A34A fail AA).
- **D7. [P1] WS hygiene**: debounce đổi symbol (reconnect storm ở 500 users); gộp price +
  mentor về 1 socket nếu được; 99 chip symbol đang hiển thị giá REST cũ trong khi chip chọn
  chạy live → đồng bộ hoặc ẩn giá chip không active.

---

## PHẦN E — VÒNG LẶP GIỮ CHÂN (retention hooks)

- **E1. [P1] Daily digest sáng**: push/thông báo "Danh mục đêm qua: NAV ±X%, Y sự kiện mới"
  + 1 câu hỏi mentor của ngày (A4.4). Worker ARQ cron theo sim-day.
- **E2. [P1] Challenge hàng ngày**: nhiệm vụ kỷ luật ("hôm nay: đặt stop-loss trước khi
  mua") — nối vào hệ Task hiện có (`models/task.py`).
- **E3. [P2] Leaderboard theo giờ**: cron rank mỗi giờ cho contest (hạ tầng
  `contests_plan.md` migration 0005 đã có).
- **E4. [P2] Báo cáo tuần**: "kỷ luật tuần này" — số lệnh đúng kế hoạch, bẫy tâm lý đã né,
  streak check-in.

---

## PHẦN F — GAMIFICATION: DISCIPLINE SCORE (thưởng kỷ luật, không thưởng PnL)

Mô hình **Discipline Score 0–100** tách biệt hoàn toàn khỏi lợi nhuận:

| Hành vi | Điểm | Chống game hóa |
|---|---|---|
| Đặt lệnh kèm kế hoạch (stop-loss + target ghi trước khi khớp) | +5/lệnh | Tối đa 3 lệnh/ngày tính điểm |
| Hoàn thành checklist trước lệnh | +3 | 1 lần/lệnh |
| Check-in danh mục hàng ngày | +2 | Streak multiplier nhỏ x1.1^min(streak,30) |
| Hoàn thành khóa học | +20 | 1 lần/khóa |
| Nhận diện bẫy tâm lý trong MXH `has_deception` | +8 | Chấm bởi trap detector, không tự khai |
| Né revenge-trade (không tái nhập trong 1 sim-day sau lỗ >X%) | +10 | Tự động từ log lệnh |
| Vi phạm (overtrade, đu tin giật gân) | −điểm | TrapEvent đã có `points_deducted` |

- **F1. [P1]** Bảng `discipline_scores(user_id, contest_id, score, breakdown JSONB)` +
  service cộng điểm theo event (hook vào trading_service fill + task completion).
- **F2. [P1]** Leaderboard xếp theo Discipline Score + Sharpe, **không bao giờ** theo PnL
  tuyệt đối.
- **F3. [P2]** Phần thưởng = cosmetic/avatar/mở khóa học — **không cộng tiền ảo** vào tài
  khoản (tránh bóp méo động lực học).
- **F4. [P2]** Host contest bật/tắt từng loại thưởng qua config (FR-4 contests_plan.md).

---

## THỨ TỰ TRIỂN KHAI ĐỀ XUẤT

| Sprint | Nội dung | Vì sao trước |
|---|---|---|
| 1 | C1–C4 (as-of + sim_now) · B1 (phí/thuế) · A2.1, A3.1, A3.3, A5.1 (mentor quick wins) | Vá lỗi trung thực mô phỏng + mentor rẻ, tác động lớn |
| 2 | A2.2–A2.4 (judge + grounding + golden set) · A3.2 (session DB) · D1, D2 (brass + giá live) | Nền tảng chất lượng mentor + niềm tin UI |
| 3 | B2–B4 (slippage/T+2/events) · D3, D4, D7 · E1, E2 | Realism + retention |
| 4 | F1–F2 (Discipline Score) · A4 (cá nhân hóa + telemetry) · D5, D6 · E3, E4 · B5, F3, F4 | Nâng cấp trải nghiệm dài hạn |

---

## NHẬT KÝ TIẾN ĐỘ

### 2026-08-21 — Sprint 1 hoàn thành

- **C1** `sim_now()`/`sim_now_epoch()` trong `realtime/simtime.py` — nguồn thời gian duy nhất,
  phân biệt rõ đồng hồ sim-label vs ranh giới as-of.
- **C2** As-of filter: list/detail news + social, contest news/social (`simulated_at <= sim_now()`).
- **C4** `social.py` tạo post dùng `sim_now()`.
- **B1** Phí 0.15% + thuế bán 0.1%: `_trade_costs()` (ROUND_HALF_UP), fill trừ/cộng ròng,
  giá vốn mua gồm phí, freeze mua gồm buffer phí; migration **0007** cột `transactions.tax`;
  WS trade feed trả `fee`/`tax`; TradePanel hiện bảng giá trị lệnh → phí → thuế → tổng chi/thực nhận
  và check số dư theo chuẩn backend; util `frontend/src/utils/trading.ts`.
- **A2.1** Policy scanner: chuẩn hoá NFD bỏ dấu + đ→d, toàn bộ pattern viết không dấu,
  ~30 pattern lách luật mới (cân nhắc/kèo/giải ngân/gom/xả/chốt/all-in/mua ngay...),
  siết từ để hỏi ("Bạn đã…", "Nếu…" không còn miễn trừ nhầm câu khẳng định);
  golden-set **36 câu bị chặn + 8 câu hợp lệ** (`test_policy_golden.py`).
- **A3.1** Gemini temperature 0.6 → 0.3.
- **A3.3** Sync test gateway ↔ YAML (`test_mentor_content_sync.py`) — sửa YAML mà quên sync sẽ đỏ test.
- **A5.1** Nhãn disclaimer cố định trong header MentorChat.

Kiểm chứng: `pytest` gateway **226 passed**, ai_engine **90 passed**, ruff sạch (file mới/sửa),
`tsc --noEmit` + `next lint` frontend sạch.

### Kế hoạch kế tiếp (Sprint 2)

A2.2 LLM-as-judge · A2.3 grounding số liệu · A2.4 golden-set eval hội thoại ·
A3.2 session DB (`mentor_messages` + migration) · D1 brass accent · D2 giá live trong confirm sheet.
