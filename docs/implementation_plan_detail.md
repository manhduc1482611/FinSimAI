# Kế hoạch triển khai chi tiết — FinSimAI (Lõi thị trường thực + Gamification/Retention)

> Nguồn: `docs/Kế hoạch kinh doanh FinSimAI.docx` (12 mục kế hoạch kinh doanh).
> Mục tiêu: đưa **mọi** mục còn dang dở của bản kế hoạch vào trạng thái "đã hiện thực hoá trên code".
> Phạm vi: hai nhóm công việc còn lại —
> **(A) Lõi mô phỏng thị trường thực** + **(B) Gamification & Retention**.
> Nền tảng vận hành ưu tiên cho demo: **Google Colab + Google Sheets**; sản phẩm thật: **Postgres + Redis**.
> Triết lý gamification: thưởng **kỷ luật / quản trị rủi ro** (Discipline Score), **không** thưởng lợi nhuận ảo.

---

## 0. Bảng trạng thái hiện tại (đã audit code)

| Mục (DOCX) | Trạng thái | Vị trí hiện tại |
|---|---|---|
| AI Mentor Socratic (5 lớp bảo vệ + golden tests ~36 case) | ✅ Xong | `apps/ai_engine/agents/*`, `realtime/mentor_engine.py` |
| Streak / check-in / nhiệm vụ / thưởng | ✅ Xong | `services/task_service.py`, models `task.py` |
| Phí 0.15% / thuế bán 0.1% / giới hạn ±7% / tick size VN | ✅ Xong | `trading_service._trade_costs`, math engine |
| Nén thời gian 1440 (1 phút = 1 ngày ảo) | ✅ Xong | `realtime/simtime.py`, `realtime/market_sim.py` |
| Nhu cầu tránh look-ahead bias | 🔶 Một phần | `as_of` filters trong news/social/contests |
| **Slippage** | ❌ | — |
| **T+2 thanh toán thật (backend)** | ❌ | chỉ có hằng `settlement_days=2` chưa dùng |
| **Sự kiện doanh nghiệp (corporate actions)** | ❌ | — |
| **Giới hạn thanh khoản** | ❌ | — |
| **Discipline Score** | ❌ | chỉ có `risk_score` riêng |
| **Leaderboard** | ❌ | chỉ `_rank_in_contest` nội bộ |
| **Báo cáo / digest hằng ngày & hằng tuần** | ❌ | — |
| **Daily challenge / câu hỏi định kỳ từ Mentor** | ❌ | — |
| UX teaser cho khách chưa đăng nhập | 🔶 Một phần | landing tĩnh |

Kế hoạch dưới đây xử lý **toàn bộ các mục ❌** (cộng nâng mục 🔶 lên ✅).

---

## I. NHÓM LÕI: Mô phỏng thị trường thực (Core Market Realism)

### C1. T+2 Thanh toán thật (Real Settlement)

**Mô tả:** Khớp lệnh bán không cộng tiền ngay; tiền về sau đúng **2 ngày giao dịch ảo** (T+2) theo luật chứng khoán Việt Nam. Tiền chờ về phải tách khỏi `cash_balance` và `frozen_cash` → không thể chi tiêu khi chưa về.

**Thiết kế dữ liệu:**
- `users` thêm cột `settling_cash NUMERIC(20,2) DEFAULT 0` (tiền đang chờ thanh toán T+2, không dùng được).
- `transactions` thêm cột `settles_at TIMESTAMPTZ NULL` (mốc mà tiền bán được giải phóng). Null cho chiều mua & chiều bán khớp user↔user tức thời (xem bên dưới).
- Migration `0009_t_settlement.py` (down_revision `0008`).

**Quy tắc nghiệp vụ:**
1. **Bán khớp với thị trường (market maker)** hoặc **bán khớp user↔user**: Khi một lệnh *bán* được fill:
   - Chuyển `net_proceeds` (revenue − fee − tax) vào **`settling_cash`** thay vì `cash_balance`.
   - Ghi `settles_at = simulated_at + settlement_days ngày` (dùng đồng hồ thực vì `simulated_at` = đồng hồ thực theo config).
2. **Mua**: giữ nguyên (đóng băng tiền ngay khi đặt, trừ khi khớp — không liên quan T+2 tiền về).
3. **Giải phóng tiền (release)**: một worker theo chu kỳ (mỗi tick leader, hoặc cron) chạy `SettlementService.release_due()`:
   - `UPDATE users SET settling_cash -= X, cash_balance += X` cho mọi giao dịch bán có `settles_at <= now()`.
   - Đánh dấu `settles_at = NULL` (đã release) để idempotent.
   - Giữ vững bất biến `cash_balance >= frozen_cash` và `cash_balance + settling_cash >= frozen_cash` (tổng tài sản không bao giờ âm).

**Where:**
- `_apply_sell_fill` (trading_service.py:201): đổi nhánh "thị trường" sang `settling_cash` + `settles_at`.
- `_fill_against_market` & nhánh bán trong `match_orders`: đóng dấu `settles_at` lên `Transaction`.
- `services/settlement_service.py` (mới): `release_due()` + `pending_settlement(user)`.
- Hook gọi `release_due()` trong `MarketSim.tick()` (realtime/market_sim.py:159) — chỉ leader, đúng 1 lần mỗi nhịp.

**Acceptance Criteria:**
- [ ] Sau khi bán fill, `cash_balance` không đổi, `settling_cash` tăng đúng `net_proceeds`.
- [ ] Sau `settlement_days` ngày ảo (2×60s thực), `release_due()` chuyển toàn bộ sang `cash_balance`.
- [ ] `net_proceeds` (đã trừ phí + thuế) chính xác tới cent.
- [ ] Idempotent: chạy `release_due()` lặp lại không trừ tiền lại 2 lần.
- [ ] `frozen_cash` bất biến: không lệnh mua nào dùng được `settling_cash`.

---

### C2. Slippage (Trượt giá thực thi) & Giới hạn thanh khoản (Liquidity Limits)

**Mô tả:** Lệnh lớn không khớp trọn ở một mức giá. Model slippage theo **độ sâu thị trường mô phỏng**; tất cả fill có giá xấu hơn `market_price` theo đơn vị tick size, và khối lượng fill mỗi lượt bị chặn bởi **giới hạn thanh khoản** của công ty.

**Thiết kế:**
- `companies` thêm cột `liquidity_depth NUMERIC(20,0) DEFAULT ...` (ví dụ 5% × `shares_outstanding`) — khối lượng tối đa có thể khớp trong một nhịp với độ trượt chấp nhận được.
- `Company` thêm `tick_size` động (đã có trong math engine, chuẩn hoá vào model/helper).
- **Market impact model** (`services/slippage.py`):
  ```
  impact_fraction = participation_ratio * k
  fill_price = market_price * (1 + direction * impact_fraction)
  ```
  Trong đó `participation_ratio = fill_qty / liquidity_depth`, `k` là hằng cấu hình (vd `0.5`); mua → giá cao hơn, bán → giá thấp hơn. Kết quả làm tròn theo tick size.
- **Liquidity cap:** khối lượng khớp trong 1 nhịp của 1 công ty ≤ `liquidity_depth`. Phần dư chuyển thành `partially_filled` và khớp ở nhịp sau (đã có cơ chế `partially_filled`).

**Where:**
- `_fill_against_market` (trading_service.py:233) và nhánh khớp user↔user trong `match_orders`: áp `slippage.fill_price(...)` thay vì dùng trực tiếp `market_price`.
- `services/slippage.py` (mới): hàm thuần `compute_fill_price(side, quantity, market_price, liquidity_depth, tick)`.
- `models/company.py`, migration 0009.

**Acceptance Criteria:**
- [ ] Lệnh mua lớn khớp với giá ≥ `market_price` (trượt lên); lệnh bán lớn khớp với giá ≤ `market_price` (trượt xuống).
- [ ] Lệnh nhỏ (khối lượng ≪ depth) gần như không trượt (impact ≈ 0).
- [ ] Giá fill luôn bội số của tick size.
- [ ] Tổng khối lượng khớp mỗi nhịp/1 công ty ≤ `liquidity_depth`; phần thừa để `partially_filled`.
- [ ] Không tạo cơ hội arbitrage: giá fill không bao giờ "ăn" qua mức limit của chính lệnh (mua: fill ≤ limit; bán: fill ≥ limit).

---

### C3. Sự kiện doanh nghiệp (Corporate Actions)

**Mô tả:** Cổ tức (cash dividend), chia tách cổ phiếu (stock split), phát hành quyền mua (rights), tin tức tác động giá — sinh theo lịch mô phỏng, đúng nguyên tắc tránh look-ahead (sự kiện chỉ phát hành từ thời điểm mà đồng hồ sim đã "đi qua").

**Thiết kế:**
- Bảng mới `corporate_actions`:
  ```
  id, company_id FK, action_type ENUM('cash_dividend','stock_split','rights','delisting','news_shock'),
  ex_date TIMESTAMPTZ, record_date TIMESTAMPTZ, config JSONB,
  (ratio_buyer, ratio_seller, cash_amount_per_share, news_text...)
  is_active, created_at
  ```
- `services/corporate_events.py` (mới): generator scheduler chạy trong `MarketSim.tick()` (leader, do `simulated_at`):
  - Chỉ sinh sự kiện nếu `simulated_at <= now()` (không tạo sự kiện tương lai — **chống look-ahead**).
  - Cash dividend: khi `simulated_at >= ex_date`, ghi giảm price history (điều chỉnh giá) và phát tin.
  - Stock split: `adjust_factor` nhân vào `shares_outstanding`, chia `current_price`, điều chỉnh `average_buy_price` của mọi portfolio giữ cổ phiếu đó.
- Migration `0010_corporate_actions.py` (down_revision `0009`).

**Acceptance Criteria:**
- [ ] Sự kiện chỉ xuất hiện khi `simulated_at` đã đạt mốc — không leak thông tin tương lai.
- [ ] Stock split: tổng giá trị portfolio của mọi user không đổi (số cổ tăng, đơn giá giảm).
- [ ] Cash dividend: `cash_balance` user giữ cổ nhận đúng tiền, giá điều chỉnh.
- [ ] Mỗi sự kiện idempotent (không trùng khi restart).
- [ ] Tin tức kèm sự kiện có `simulated_at` hợp lệ để feed realtime.

---

### C4. Chống Look-ahead bias trong feed (nâng mục 🔶 → ✅)

**Mô tả:** Mọi nguồn dữ liệu mà host/contest phát hành cho user đều phải "time-stamped ≤ đồng hồ sim" tại thời điểm user quan sát. Hiện chỉ áp `as_of` cho news/social/contests. Bổ sung pipeline phát hành:
- `services/as_of_pipeline.py` (mới): mỗi nhịp leader, các `simulated_at` tương lai (nếu có) được "tuôn ra" đúng lúc `now()` đạt mốc, thay vì liệt kê từ trước.
- Không có bất kỳ endpoint nào trả dữ liệu có `simulated_at > now()`.

**Acceptance Criteria:**
- [ ] Không tồn tại record trả cho client có `simulated_at > now()`.
- [ ] Pipeline phát hành tuân theo đồng hồ nén 1440.
- [ ] Test `test_asof_filters.py` mở rộng cover corporate actions + digest.

---

## II. NHÓM GAMIFICATION & RETENTION

### G1. Discipline Score (Điểm kỷ luật)

**Mô tả:** Điểm thưởng/trừ theo **hành vi kỷ luật**, không theo lợi nhuận. Phân biệt với `risk_score` (điểm rủi ro hỗ trợ mentor). Discipline Score dùng để: xếp hạng kỷ luật, mở khoá thử thách, badge.

**Thiết kế:**
- Bảng mới `discipline_score_history`:
  ```
  id, user_id FK, score_delta INTEGER, reason VARCHAR(50), context JSONB,
  created_at
  ```
- `users` thêm cột `discipline_score INTEGER DEFAULT 100` (điểm gốc 100, clamp 0–100).
- `services/discipline_service.py` (mới) với bộ luật **event-driven**:
  - **Cộng (+):** giữ vị thế khi sóng giảm (không FOMO/panic), sử dụng stop-loss, không tăng margin khi thua, check-in đều, đọc bài học trước khi giao dịch lớn.
  - **Trừ (−):** FOMO mua đỉnh, panic bán đáy, all-in 1 cổ phiếu, trade tần suất cao không kế hoạch, vi phạm trigger cooldown (nối với `penalty_service`).
  - Sự kiện kỷ luật sinh từ: `trading_service` (fill), `penalty_service` (cooldown), `task_service` (check-in/hoàn thành bài học). Cùng hook với penalty hiện có.
- **Hook:** `penalty_service.enforce_cooldown` (đã gọi mỗi lần đặt lệnh, trades.py:70) → tích hợp `discipline_service` để ghi delta tại chỗ.

**Acceptance Criteria:**
- [ ] FOMO/panic/cooldown → `discipline_score` giảm đúng mức; check-in/đọc bài học → tăng.
- [ ] Clamp 0–100, có lịch sử đầy đủ để audit.
- [ ] Discipline Score **không** thay đổi khi user chốt lời/lỗ (không thưởng lợi nhuận).
- [ ] Gắn badge/label hiển thị (API trả về score + độ dài streak kỷ luật).

---

### G2. Leaderboard (Bảng xếp hạng)

**Mô tả:** Bảng xếp hạng toàn hệ thống theo **NAV** (chính + vị thế) và riêng **bảng kỷ luật** theo Discipline Score. Có phân đoạn: toàn cầu / theo cuộc thi.

**Thiết kế:**
- `services/leaderboard_service.py` (mới):
  - `global_nav`: tổng `cash_balance + frozen_cash + settling_cash + Σ portfolio.quantity × company.current_price` (thị trường chính, `contest_id IS NULL`).
  - `contest_nav`: theo `contest_id`.
  - `discipline`: xếp theo `discipline_score` DESC.
  - Trả kèm hạng của user hiện tại (`my_rank`) — KHÔNG cần rank mọi user.
- Endpoint `GET /api/v1/leaderboard?type=nav|discipline&contest_id=&limit=&offset=` trong `api/v1/leaderboard.py` (đăng ký vào `router.py`).
- Tối ưu: tính NAV bằng SQL (JOIN + GROUP BY) đã có pattern trong `_rank_in_contest`.

**Acceptance Criteria:**
- [ ] Trả đúng thứ hạng theo NAV đã trừ toàn bộ chi phí.
- [ ] Bảng kỷ luật độc lập với lợi nhuận.
- [ ] Có `my_rank` cho user hiện tại.
- [ ] Offset/limit phân trang, không nổ với nhiều user.

---

### G3. Daily Digest & Weekly Report

**Mô tả:** Bản tóm tắt hằng ngày (biến động danh mục, chỉ số, sự kiện, tiến độ kỷ luật) và báo cáo hằng tuần (hiệu suất, bài học, gợi ý Mentor) — tạo retention.

**Thiết kế:**
- `services/report_service.py` (mới):
  - `build_daily_digest(user, day)`: NAV đầu/cuối ngày, % thay đổi, top winner/loser trong danh mục, số lệnh thực hiện, fee/tax đã trả, discipline delta ngày, sự kiện doanh nghiệp hôm nay đã vượt qua `ex_date`.
  - `build_weekly_report(user, week)`: tổng hợp 7 digest, P/L thực hiện + chưa thực hiện, bài học từ Mentor, so sánh với benchmark (Index VN mô phỏng).
  - Lưu vào bảng `reports` (id, user_id, kind daily|weekly, period, payload JSONB, created_at).
- Endpoint `GET /api/v1/reports/...` (+ frontend hiển thị).
- Scheduler: gắn vào leader tick hoặc cron tạo `reports` khi hết chu kỳ ngày/tuần ảo.

**Acceptance Criteria:**
- [ ] Digest hằng ngày đầy đủ số liệu đã nêu, đúng period (app_timezone).
- [ ] Weekly tổng hợp 7 digest, đúng mốc tuần.
- [ ] Không trùng báo cáo (unique per user+kind+period).
- [ ] Số liệu khớp với transaction/portfolio thật.

---

### G4. Daily Challenge & Câu hỏi định kỳ từ Mentor

**Mô tả:** Thử thách hằng ngày (kỹ năng/kỷ luật) gắn thưởng, và Mentor chủ động hỏi lại người dùng theo chu kỳ (nối vào luồng mentor hiện có).

**Thiết kế:**
- Bảng `daily_challenges` (id, date, code, title, description, target JSONB, reward_amount, is_active) và `user_daily_challenges` (user_id, challenge_id, completed_at, reward).
- `services/challenge_service.py` (mới): sinh/klock thử thách hằng ngày; hoàn thành → credit reward + tăng discipline.
- **Periodic mentor questions:** mở rộng `services/mentor_history.py` + `realtime/mentor_engine.py` với endpoint `GET /api/v1/mentor/periodic` trả câu hỏi khi "đến hạn" (mỗi N ngày ảo, sau khi user có đủ hoạt động). Câu hỏi dạng Socratic, gắn context danh mục/user.
- Tận dụng khung nhiệm vụ `task_service` sẵn có khi có thể (tái dùng reward/streak).

**Acceptance Criteria:**
- [ ] Mỗi ngày ảo có ≥1 thử thách khả dụng; hoàn thành nhận thưởng đúng 1 lần.
- [ ] Mentor hỏi định kỳ đúng lịch, không spam (giới hạn tần suất).
- [ ] Không hỏi khi user chưa có hoạt động (tránh phiền).

---

## III. Thứ tự triển khai, ưu tiên & test

| Ưu tiên | Mục | Phụ thuộc | Test cần thêm |
|---|---|---|---|
| P0 | C1 T+2 | migration + settlement_service | `test_settlement.py` |
| P0 | C2 Slippage & Liquidity | slippage.py + model | `test_slippage.py` |
| P0 | G1 Discipline Score | discipline_service + hook penalty | `test_discipline.py` |
| P1 | G2 Leaderboard | leaderboard_service + api | `test_leaderboard.py` |
| P1 | C3 Corporate actions | migration + corporate_events | `test_corporate_events.py` |
| P1 | G3 Daily/Weekly report | report_service + api | `test_reports.py` |
| P1 | C4 As-of pipeline hoàn chỉnh | pipeline + các module news | mở rộng `test_asof_filters.py` |
| P2 | G4 Challenge & mentor periodic | challenge_service + mentor | `test_challenges.py` |

**Quy tắc chung:**
- Mọi thay đổi schema qua **migration thêm mới** (không sửa file cũ giữa chừng), cập nhật **cả** `models/*.py` và `packages/database/schema.sql` để đồng bộ.
- Mọi hành vi ghi tiền giữ bất biến: `cash_balance >= frozen_cash`, `cash_balance + settling_cash >= frozen_cash`, tổng menu NAV không đổi khi split.
- Backend: các hàm thuần (tính phí, slippage, discipline delta) đặt ở `services/` tách DB để dễ unit-test như `_trade_costs`.
- Chạy bộ test sau mỗi nhóm: `uv run pytest apps/backend_gateway/tests` (hoặc theo repo).
- Không vi phạm nguyên tắc **chống look-ahead** trong mọi nguồn feed.

## IV. Đánh dấu hoàn thành cho từng mục DOCX

Sau khi xong cả hai nhóm, cập nhật bảng trạng thái §0 để phản ánh:
- C1–C4, G1–G4 → ✅; UX teaser 🟡 (bước sau, ngoài phạm vi 2 nhóm này — xác nhận riêng).

### ✅ Đã triển khai (2026-09-01)

| Mục | Hiện thực hoá | Migration | API |
|---|---|---|---|
| C1 T+2 settlement | `settling_cash` (users), `settles_at` (transactions), `services/settlement_service.py`, hook trong `MarketSim.tick` | `0009_t_settlement.py` | portfolio `total_nav` đã gồm settling |
| C2 Slippage & liquidity | `services/slippage.py` (tick VN + impact cap 2%), `liquidity_depth` trên `Company`, cap khối lượng fill/nhịp | (thuộc tính dẫn xuất, không cần cột) | — |
| C3 Corporate actions | `models/corporate_action.py`, `services/corporate_events.py` (cash dividend + stock split, idempotent, chống look-ahead), hook trong `MarketSim.tick` | `0011_corporate_actions.py` | — |
| G1 Discipline Score | `services/discipline_service.py` (clamp 0–100, RULES, history), hook trong `penalty_service` & `task_service.checkin` | `0010_discipline.py` | `GET /discipline/me` |
| G2 Leaderboard | `services/leaderboard_service.py` (NAV + discipline, my_rank) | — | `GET /leaderboard` |
| G3 Digest/Report | `services/report_service.py` (daily digest, upsert reports) | `0012_reports.py` | `GET /reports` |
| G4 Challenge + mentor periodic | `services/challenge_service.py` + `api/v1/challenges.py` | `0013_challenges.py` | `GET /challenges`, `POST /challenges/{id}/complete`, `GET /challenges/mentor/periodic` |

**Kết quả test:** `uv run pytest apps/backend_gateway/tests` → **254 passed** (thêm
`test_slippage.py`, `test_settlement.py`, `test_discipline_service.py`,
`test_market_sim_extras.py`; cập nhật `test_trade_costs.py` cho hành vi T+2).

**Lưu ý triển khai tiếp:** chạy `uv run python apps/backend_gateway/run_migrations.py`
để nâng DB lên head (0013). `new_reports`/`corporate_events`/`discipline` cần DB đã
migrate trước khi dùng.

