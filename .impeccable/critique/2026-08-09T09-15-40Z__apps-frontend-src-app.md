---
target: toàn bộ web — nền tảng học đầu tư cho người mới
total_score: 21
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-08-09T09-15-40Z
slug: apps-frontend-src-app
---
# Critique: FinSimAI — Nền tảng học đầu tư cho người mới

Method: dual-agent (A: ses_01a380caeffeEmHgdkwwi5FmQo · B: ses_01a37ff58ffevBoHuRDlZrVSi4)

Lens: "Đây có thực sự là nền tảng cho người mới học đầu tư?" — đánh giá theo khả năng dùng của người mới (F0), pedagogy, và xây dựng kỷ luật. Không có trình duyệt live — đánh giá dựa trên source (trạng thái, label, empty/error state, affordance). Detector scan: 1 CLI finding (documentation gap, xem phần Detector).

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Skeleton/spinner/retry/WS stamps tốt; nhưng kết quả đặt lệnh leak tiếng Anh `trạng thái: filled`, "Hỏi Mentor" là nút chết |
| 2 | Match System / Real World | 2 | Tiếng Việt chuẩn, xanh/đỏ đúng VN; nhưng NAV/P/E/ROE/Spread/Mid/“KL lũy kế” không được giải thích cho F0 |
| 3 | User Control and Freedom | 2 | Có Hủy lệnh, đổi theme, logout; nhưng đặt lệnh KHÔNG xác nhận — 1 click đóng băng tiền sim |
| 4 | Consistency and Standards | 3 | Hệ thống kỷ luật nội bộ cao (1 accent, primitives dùng chung); lệch: status order lúc localize lúc raw, nút chết, filter trùng |
| 5 | Error Prevention | 1 | Guard input tốt (đủ tiền, quantity>0); nhưng hậu quả lớn không chắn: không confirm, không cảnh báo limit có thể không khớp, không cảnh báo giá thị trường |
| 6 | Recognition Rather Than Recall | 3 | Sidebar mô tả, inline hints, suggestion chips; nhưng mọi thuật ngữ tài chính phải nhớ, rail 100 symbol chỉ hiện symbol+giá |
| 7 | Flexibility and Efficiency | 2 | Mentor suggestion chips tốt; không watchlist, không phím tắt, không recall symbol gần đây |
| 8 | Aesthetic and Minimalist Design | 2 | Nhận diện mạnh; nhưng trade page 6 module, dashboard 10 “cửa” bằng trọng lượng, stamp chồng stamp |
| 9 | Error Diagnosis and Recovery | 2 | Nút retry khắp nơi, lỗi WS tiếng Việt; nhưng `detail` từ backend render raw, không có hướng dẫn "giờ phải làm gì" |
| 10 | Help and Documentation | 1 | KHÔNG có onboarding/tour/tooltip/FAQ; glossary chỉ nằm trên news detail — nơi jargon nhiều nhất (companies/trade) lại trống |
| **Total** | | **21/40** | **Acceptable** |

## Design Specificity Verdict

**Authored-for-this-product ở tầng thị giác, nhưng generic ở tầng tương tác.** Bộ "quầy giao dịch" là hệ thống thật: `board`/`stamp`/`ticket` trong `globals.css:53-120` dùng đúng ngữ nghĩa (board cho dữ liệu, stamp cho xác nhận, ticket cho kỷ luật), brass một accent, xanh-đỏ VN nhất quán cả trong chart. Nhưng yếu tố khiến thế giới này khác biệt — "giao dịch viên cản lệnh rủi ro, phiếu được đóng dấu" — lại không có ở khoảnh khắc quyết định: không xác nhận, không đóng dấu, nút Hỏi Mentor trên đúng trang giao dịch là `onClick={() => {}}` (`trade/page.tsx:79`).

**Detector scan:** 1 finding duy nhất — `#1F9E5F` (`CompanyMap.tsx:96`, legend màu "Khá 60–79"). Đây là `brand.500` có chủ đích trong `tailwind.config.js:14`, NHƯNG không có trong DESIGN.md → chủ yếu là lỗ hổng tài liệu, không phải bug người dùng. Bonus phát hiện: rule này là `advisory` nhưng thiếu cờ `advisory: true` nên bị đếm vào primary → exit 2 (lỗi registry, không phải lỗi app).

**Visual overlays:** Không khả dụng — môi trường không có trình duyệt để chạy live-server + inject detect.js. Chỉ có CLI scan.

## Overall Impression

Thế giới "quầy giao dịch" đẹp, trung thực, và có bộ xương học tập thật (glossary, mentor Socratic, ticket kỷ luật). Nhưng toàn bộ giá trị học tập bị chặn bởi 2 vấn đề: (1) người mới đăng ký xong bị thả vào 10 cánh cửa ngang hàng không có đường đi, và (2) đúng lúc cần sự trấn an nhất (lần đầu đặt lệnh, lỗ tiền) thì app im lặng — thậm chí nút đại diện cho "sự trấn an" (Hỏi Mentor) là nút chết. Cơ hội lớn nhất: biến chuỗi "đọc tin → xem công ty → giao dịch → hỏi mentor" thành một hành trình có dẫn dắt, với friction đúng chỗ khi đặt lệnh.

## What's Working

1. **Thế giới "quầy giao dịch" được thực thi, không chỉ trang trí** — `board`/`stamp`/`ticket` dùng đúng ngữ nghĩa khắp app, brass một accent, xanh/đỏ VN tôn trọng cả trong `PriceChart` và `OrderBook`. Nhận diện mạnh mà fintech generic không copy được.
2. **Trung thực như một tính năng** — "AI tạo" (`news/[id]/page.tsx:102`), "Mô phỏng" trên sổ lệnh fake (`OrderBook.tsx:114`), "Số liệu mô phỏng cho mục đích học tập" (`FinancialReport.tsx:58`). Với người mới, đây là nền tảng của niềm tin.
3. **Bộ xương học tập đúng chỗ** — glossary tự khớp nội dung (`useKnowledge.ts`), mentor Socratic với câu hỏi gợi ý click được và cam kết "không đưa đáp án" (`MentorChat.tsx:16-21`), kỷ luật được khung hóa bằng ticket + stamp (`tasks/page.tsx:298-323`).

## Priority Issues

### P0 — Không có lối vào sau khi đăng ký
- **What**: Register xong → `/dashboard` với 10 "cửa" ngang hàng, không thứ tự, không nhiệm vụ đầu tiên. Thang nhiệm vụ onboarding tồn tại trong seed (`seed_db.py:439-463`) nhưng không bao giờ được trình bày như đường đi; "Ưu tiên" trên Tasks vs "Bắt đầu hành trình" trên News (`dashboard/page.tsx:33,71`) mâu thuẫn tín hiệu ưu tiên.
- **Why**: Người mới đúng lúc "hot" nhất lại không biết làm gì tiếp → bỏ đi ngay bước 2. Đây là lỗ hổng lớn nhất với mục tiêu học đầu tư.
- **Fix**: Progressive disclosure theo task — một CTA "Tiếp theo" nổi bật lái `đọc tin → xem công ty → đặt lệnh → hỏi mentor`; hoặc first-run tour.
- **Suggested command**: /impeccable onboard

### P0 — Lần giao dịch đầu tiên không được bảo vệ, "giao dịch viên" là bóng ma
- **What**: 1 click là đặt lệnh, đóng băng tiền sim ngay, không confirm, không tóm tắt chi phí, không câu hỏi rủi ro — trong khi nút đại diện Mentor trên chính màn đó là `onClick={() => {}}` (`trade/page.tsx:79`). Kết quả thắng/bại hiện raw tiếng Anh `trạng thái: filled` (`TradePanel.tsx:117`).
- **Why**: Sản phẩm tuyên bố dạy kỷ luật, nhưng hành động quan trọng nhất lại không có chút friction nào — dạy ngược lại. Và người mới sợ nhất là "bấm nhầm mất tiền" — ngay cả tiền sim.
- **Fix**: Bước xác nhận dạng stamp (tóm tắt giá/số lượng/chi phí), wire nút Hỏi Mentor mở `MentorChat` với symbol đang chọn, gate lệnh vượt ngưỡng rủi ro sau câu hỏi Mentor.
- **Suggested command**: /impeccable shape + /impeccable harden

### P1 — Bức tường jargon tại mọi điểm quyết định
- **What**: F0 gặp không giải thích: "Giới hạn" vs "Thị trường" (`TradePanel.tsx:184-205`), "Giá giới hạn" (`:216-226`), "Sổ lệnh · Mid · Spread · KL lũy kế" (`OrderBook.tsx:111-172`), "Chờ khớp · Khớp một phần" (`OrderTable.tsx:21-27`), "NAV" (`Portfolio.tsx:34`), "P/E · ROE" (`CompanyCard.tsx:50-53`), "Tác động 7.2/10" (`NewsCard.tsx:52`), persona "Lùa gà · Chim lợn tin đồn" (`social/page.tsx:112-118`).
- **Why**: Không hiểu thuật ngữ thì không thể đặt giá limit hay chọn khối lượng — người mới buộc phải nhớ, không nhận ra.
- **Fix**: Sub-label tiếng Việt thường ("Giá giới hạn = giá tối đa bạn chấp nhận trả"), tooltip định nghĩa, tái sử dụng `useKnowledge` glossary trên companies + trade.
- **Suggested command**: /impeccable clarify

### P1 — Con số quan trọng nhất (NAV) sai trên hầu hết trang và ẩn trên mobile
- **What**: Header NAV fallback về `cash_balance` khi `portfolio` null (`Header.tsx:80-91`) — xảy ra mọi trang trừ khi đã vào `/trade`; toàn bộ hàng NAV/Cash/Risk bị `hidden md:flex` (`Header.tsx:131`), mobile không thấy.
- **Why**: App dạy NAV nhưng dạy sai con số trên hầu hết màn hình — user mới học "NAV = tiền mặt" trong khi đang nắm cổ phiếu.
- **Fix**: Fetch portfolio ở tầng shell, tính NAV phía server, giữ ít nhất NAV hiển thị trên màn hình nhỏ.
- **Suggested command**: /impeccable layout + fix logic (shell-level data)

### P2 — Lỗ (và lãi) tiền không được phản hồi
- **What**: PnL đỏ không có reframe, không nudge mentor, không "đây là bài học" (`Portfolio.tsx:143-156`); social feed dạy nhận biết bẫy (`social/page.tsx:99`) nhưng chỉ gắn nhãn persona mà không giải thích vì sao "Khoe lãi"/"Tip nội bộ" là bẫy.
- **Why**: Chính khoảnh khắc sợ/tham là lúc người mới cần mentor nhất — sản phẩm lại im lặng. Câu trấn an duy nhất ("không phải lời khuyên thật") nằm ở footer.
- **Fix**: Ngày PnL âm → hiện thẻ mentor suy ngẫm; tooltip 1 dòng "vì sao post này là đèn đỏ"; gợi ý journal sau giao dịch.
- **Suggested command**: /impeccable delight + /impeccable onboard

## Persona Red Flags

**Jordan (người mới bối rối):** Đăng nhập xong đứng trước 10 cánh cửa ngang hàng (`dashboard/page.tsx:27-73`); ở trade panel phải chọn limit-vs-market không giải thích (`TradePanel.tsx:184-205`); đọc "Tác động 7.2" (`NewsCard.tsx:52`) không phán đoán được nghĩa; không có "làm gì tiếp theo" ở bất kỳ đâu.

**Casey (mobile mất tập trung):** NAV/Cash/Risk biến mất dưới `md:` (`Header.tsx:131`); rail symbol 100 chip cuộn ngang (`trade/page.tsx:101`); terminal 6 module dễ bấm nhầm (`trade/page.tsx:140-190`); "Di chuột để xem chi tiết" (`CompanyMap.tsx:213`) vô dụng trên touch; chạm "Hỏi Mentor" (`trade/page.tsx:79`) im lặng không gì xảy ra.

**F0 (không biết gì về tài chính):** Mọi màn đều giả định biết chữ: "NAV"/"Cash" không dịch (`Header.tsx:132-133`), "P/E · ROE · Vốn hóa" (`CompanyCard.tsx:50-60`), "khớp một phần" (`OrderTable.tsx:24`), tiếng lóng persona (`domain.ts:45-56`), "RỦI RO 42" không giải thích ngưỡng (`Header.tsx:38-56`). Tính năng duy nhất xây cho persona này — glossary — chỉ mở được từ một bài báo.

## Minor Observations

- `trạng thái: ${order.status}` raw tiếng Anh trong toast đặt lệnh (`TradePanel.tsx:117`).
- "Chia sẻ" trên post là nút trang trí, không có action (`SocialPostCard.tsx:158-161`).
- Lọc category tồn tại 2 lần trên News (sidebar buttons + NewsFilter select) — hai mô hình cho một filter.
- Empty state logged-out bảo user "kiểm tra backend đang chạy" (`NewsList.tsx:57`) — giọng lập trình viên.
- OrderTable 9 cột, tràn ngang, không pin cột đầu (`OrderTable.tsx:86-98`).
- Input giá `type="number"` dùng dấu chấm trong khi parser/formatter vi-VN dùng phẩy (`TradePanel.tsx:81, 219-226`).
- Không có nút hiện/ẩn mật khẩu login/register.
- Check-in là hành động riêng trên `/tasks`, dashboard chỉ hiện con số.
- Timestamp news dùng thời gian thật, không phải sim-time — phá vỡ premise "1 phút = nhiều ngày" (`news/[id]/page.tsx:118`).

## Questions to Consider

1. **Friction nằm ở đâu?** Kỷ luật đầu tư được xây bằng friction — một khoảng lặng trước khi quyết định. Nếu người mới có thể đóng băng 40 triệu VND sim bằng một click không xác nhận, FinSimAI đang dạy kỷ luật hay dạy ngược lại?
2. **Mentor là mentor hay chatbot?** Payload `ask` chỉ mang `{action, message, session_id}` (`useSocraticMentor.ts:89`) — không có portfolio, NAV, risk score, lịch sử giao dịch. Một giáo viên Socratic làm sao "thử thách quyết định" khi không biết gì về quyết định của bạn?
3. **Vì sao con số quan trọng nhất lại sai trên hầu hết màn hình?** NAV — thứ cả sản phẩm xoay quanh — fallback về tiền mặt ngoài `/trade`, ẩn trên mobile, và không được định nghĩa ở đâu.
