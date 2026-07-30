FIN SIM AI
===============================
HỆ THỐNG MÔ PHỎNG THỊ TRƯỜNG TÀI CHÍNH VỚI AI

===============================

MỤC LỤC
-------
I.   Hướng dẫn sử dụng cơ bản
II.  Các thành phần và cách dữ liệu được tạo ra
III. Học & Áp dụng (Learn & Apply)
IV.  Quy trình vận hành tổng thể
V.   Nhật ký cập nhật

===============================
I. HƯỚNG DẪN SỬ DỤNG CƠ BẢN
===============================

FinSimAI là trang web mô phỏng thị trường chứng khoán. Mọi tin tức, công ty, bài viết trên mạng xã hội và giá cổ phiếu đều do AI tạo ra dựa trên bối cảnh thị trường thật.

Người dùng phải tuân theo trình tự 3 bước sau đây trước khi có thể giao dịch.

----------------------------------------------------------------------
1. Đọc báo — Hiểu thị trường (Trang /news)
----------------------------------------------------------------------

Trước khi mua bán cổ phiếu, người dùng cần nắm được bối cảnh thị trường thông qua trang báo.

Các thao tác có thể thực hiện:
    a. Xem danh sách tin tức tài chính trong nước và quốc tế
    b. Lọc tin theo ngành nghề (ngân hàng, bất động sản, năng lượng...)
    c. Lọc tin theo cảm xúc (tích cực / tiêu cực / trung tính)
    d. Tìm kiếm tin tức theo từ khóa
    e. Xem chi tiết bài báo và các bài viết liên quan

Lưu ý: Đọc tin tức để nhận định xu hướng trước khi đầu tư. Tin tốt về một ngành có thể báo hiệu cơ hội mua.

----------------------------------------------------------------------
2. Khám phá công ty trên bản đồ (Trang /companies)
----------------------------------------------------------------------

Sau khi nắm được bối cảnh thị trường, người dùng đến bản đồ doanh nghiệp.

Bản đồ hiển thị vị trí các công ty ảo theo từng ngành. Khi click vào một công ty, người dùng xem được các thông tin sau:

    a. Hồ sơ công ty:
       - Tên công ty, ngành nghề kinh doanh
       - Vốn điều lệ, lịch sử hình thành

    b. Báo cáo tài chính:
       - Lợi nhuận / lỗ (PnL)
       - Tỷ suất lợi nhuận (Margin)
       - Mức sụt giảm tối đa (Drawdown)

    c. Biểu đồ giá cổ phiếu

    d. Tin tức liên quan:
       - Các bài báo AI có nhắc đến công ty

    e. Bài viết trên mạng xã hội:
       - Dư luận cộng đồng về công ty

    f. Chỉ số sức khỏe:
       - Thang điểm đánh giá nội tại công ty

Lưu ý: Không đầu tư vào công ty khi chưa hiểu rõ. Cần xem báo cáo tài chính và tin tức liên quan trước khi quyết định.

----------------------------------------------------------------------
3. Giao dịch chứng khoán (Trang /trade)
----------------------------------------------------------------------

Khi đã tự tin với nhận định của mình, người dùng bước vào bảng giao dịch.

Các chức năng chính:

    a. Bảng giá real-time:
       - Giá cổ phiếu biến động theo tin tức và thị trường

    b. Sổ lệnh:
       - Đặt lệnh mua hoặc bán

    c. Danh mục đầu tư:
       - Theo dõi lãi / lỗ theo thời gian thực

    d. AI cố vấn:
       - Hệ thống sẵn sàng trả lời câu hỏi
       - Phản biện quyết định của người dùng theo phương pháp Socrates

    e. Cơ chế phạt:
       - Nếu người dùng FOMO (mua theo tâm lý đám đông) hoặc bán tháo hoảng loạn
       - Hệ thống tạm khóa giao dịch và trừ điểm kỷ luật

----------------------------------------------------------------------
Sơ đồ lộ trình người dùng
------------------------------------------------------------------------------

    [Bước 1: Đọc báo] ---> [Bước 2: Khám phá công ty] ---> [Bước 3: Giao dịch]
         │                        │                            │
         │ (học khái niệm)        │ (áp dụng thử chỉ số)       │ (coach thực chiến)
         ▼                        ▼                            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  III. Học & Áp dụng (Learn & Apply)          │
    │        Kiến thức tĩnh — gắn sẵn vào từng bài báo/chỉ số     │
    └─────────────────────────────────────────────────────────────┘

    Sau đó quay lại Bước 1 để tiếp tục theo dõi thị trường.

===============================
II. CÁC THÀNH PHẦN VÀ CÁCH DỮ LIỆU ĐƯỢC TẠO RA
===============================

----------------------------------------------------------------------
1. Trang báo (News)
----------------------------------------------------------------------

Tin tức trên trang báo không phải tin thật được hiển thị trực tiếp. AI đọc tin thật để hiểu bối cảnh, sau đó tự viết tin mới.

Quy trình tạo tin tức gồm 3 bước:

    Bước 1: AI đọc báo thật
            - Nguồn: Cafef, VnEconomy, Bloomberg, Reuters
            - Nội dung được lưu lại làm tư liệu tham khảo

    Bước 2: AI phân tích bối cảnh
            - Phân loại tin theo ngành nghề
            - Đánh giá cảm xúc (tích cực / tiêu cực / trung tính)
            - Đo mức độ ảnh hưởng (thang 1-10)
            - Xác định xu hướng thị trường hiện tại

    Bước 3: AI viết báo mới
            - Dựa trên bối cảnh thật để sáng tác nội dung mới
            - Không sao chép bài gốc
            - Gắn nhãn "AI Generated" cho mỗi bài viết

Có 5 dạng bài báo xuất hiện trên trang:

    Loại bài báo                     Ví dụ tiêu đề
    -------------------------------  ------------------------------------------------
    Vĩ mô trong nước                 "NHNN điều chỉnh lãi suất cơ bản lên 5.5%"
    Vĩ mô quốc tế                    "FED giữ nguyên lãi suất, phát tín hiệu thận trọng"
    Theo ngành                       "Ngành ngân hàng ghi nhận tín dụng tăng trưởng 15%"
    Theo công ty                     "Tập đoàn ABC ký kết hợp tác chiến lược với XYZ"
    Báo cáo thị trường               "VN-Index giảm 12 điểm trong phiên sáng"

----------------------------------------------------------------------
2. Mạng xã hội (Social) — Môi trường gây nhiễu thực chiến
------------------------------------------------------------------------------

Mô phỏng áp lực tâm lý đám đông (FOMO, hoảng loạn), tin đồn và thao túng
thị trường. Người dùng phải kiểm chứng thông tin bằng dữ liệu từ
/companies và /news trước khi giao dịch.

10 Persona chính:

    a. Phân tích TA/FA — KOL ảo, có thể chứa lỗi cố tình
    b. Khoe lãi / Than lỗ — Kích hoạt FOMO hoặc hoảng loạn
    c. Khoe lỗ & Lùa gà — "Cháy tài khoản" kiểu thành tích; đẩy giá xả hàng
    d. Chim lợn & Bìm bịp — Tin đồn M&A, thao túng phối hợp
    e. Chia sẻ kinh nghiệm — Chiến lược rủi ro (martingale, all-in, margin)
    f. Hỏi đáp F0 — Câu hỏi cơ bản, câu trả lời sai lẫn lộn
    g. Góc nhìn vĩ mô — Nhận định ngành, có thể phóng đại
    h. Insider Tips — "Mai có tin", rò rỉ nội bộ giả
    i. Memes & Giải trí — Tạo không khí chân thực
    j. Cảnh báo lừa đảo — Phốt sàn, có thật lẫn dàn dựng

Cơ chế lan truyền (Virality 1-10): cảm xúc càng cực đoan, trùng xu hướng,
nguồn càng uy tín → lan càng xa → tác động ngược lại giá cổ phiếu.

UI/UX: Lọc sentiment/loại/mã CP; Heatmap; Trending; Nút "Kiểm chứng AI
Mentor" (đối chiếu với Math Engine, phát hiện lùa gà).

----------------------------------------------------------------------
3. Bản đồ công ty (Companies)
----------------------------------------------------------------------

Các công ty giả lập do AI tạo ra dựa trên kịch bản gốc.

Nguồn gốc thông tin:

    Thông tin                         Nguồn tạo
    -------------------------------   ------------------------------------------------
    Tên, ngành, vốn điều lệ           Định nghĩa sẵn từ đầu (seed data)
    Báo cáo tài chính                 AI toán (Math Engine) tính tự động
    Biểu đồ giá                       AI toán dựa trên tin tức và giao dịch
    Chỉ số sức khỏe                   AI toán tổng hợp từ nhiều chỉ số
    Tin tức liên quan                 Truy vấn từ kho dữ liệu
    Bài viết MXH liên quan            Truy vấn từ kho dữ liệu

----------------------------------------------------------------------
4. Giao dịch (Trade)
----------------------------------------------------------------------

Đây là nơi người dùng tương tác trực tiếp.

    a. Giá cổ phiếu chịu tác động từ:
       - Tin tức trên trang báo
       - Dư luận trên mạng xã hội
       - Hành vi mua bán của những người dùng khác

    b. AI cố vấn:
       - Sẵn sàng trả lời câu hỏi
       - Phản biện quyết định của người dùng

    c. Cơ chế phạt:
       - Tạm ngưng giao dịch khi phát hiện hành vi mất kỷ luật
       - Trừ điểm kỷ luật

===============================
III. HỌC & ÁP DỤNG (LEARN & APPLY)
===============================

Hệ thống này giúp bạn vừa đọc tin tức, vừa được giải thích các khái niệm
tài chính — và quan trọng nhất là **hướng dẫn bạn áp dụng ngay vào thực tế
đầu tư**. Toàn bộ kiến thức đã được soạn sẵn, không cần đến trí tuệ nhân
tạo, nên hoàn toàn miễn phí và không mất thời gian chờ đợi.

----------------------------------------------------------------------
Nguyên lý hoạt động
----------------------------------------------------------------------

Mỗi bài báo hoặc chỉ số tài chính đều được **gắn thẻ (tag)** với các
khái niệm liên quan từ một kho kiến thức được soạn sẵn. Khi bạn đọc tin,
hệ thống tự động nhận ra khái niệm nào đang được nhắc đến và hiển thị
gợi ý tương ứng. Tất cả đều dựa trên việc so khớp từ khóa đơn giản —
giống như tra từ điển vậy.

Ví dụ: Bài báo có chữ "lãi suất" → hệ thống nhận ra đây là khái niệm
"Lãi suất" → hiển thị ô giải thích ngắn và nút gợi ý hành động.

----------------------------------------------------------------------
3 nơi bạn sẽ thấy tính năng này
----------------------------------------------------------------------

1. Khi đọc báo (trang /news) — Học khái niệm

   Mỗi bài báo có thể có một hoặc nhiều **thẻ kiến thức** (ví dụ:
   "📘 Lãi suất", "📘 Chỉ số P/E"). Bạn nhấp vào thẻ sẽ thấy:

     • Giải thích ngắn gọn khái niệm đó là gì (1-2 câu)
     • Nút "Tìm công ty hưởng lợi" — chuyển bạn sang trang danh sách
       công ty, tự động lọc sẵn theo ngành liên quan

   → Mục đích: Đọc báo xong, biết ngay nên nhìn vào công ty nào.

2. Khi xem hồ sơ công ty (trang /companies) — Áp dụng chỉ số

   Bên cạnh mỗi chỉ số tài chính (P/E, ROE, Biên lợi nhuận...) có nút
   **"Áp dụng"**. Nhấp vào sẽ thấy các gợi ý như:

     • "So sánh chỉ số P/E của công ty này với các công ty cùng ngành"
     • "Vẽ biểu đồ ROE để xem xu hướng"
     • "Mở sổ đặt lệnh, tự động cài sẵn mức cắt lỗ (stop-loss)"

   → Mục đích: Biết con số có ý nghĩa gì, và làm gì với nó.

3. Khi giao dịch (trang /trade) — Nhắc nhở thực chiến

   Khi bạn đặt lệnh mua hoặc bán, hệ thống xem lại những khái niệm bạn
   đã đọc trong phiên này và nhắc nhở nếu cần:

     • "Bạn vừa đọc về cắt lỗ (stop-loss) ở trang báo. Lệnh này của
       bạn chưa đặt cắt lỗ — có muốn thêm không?"
     • "Bài báo về ngành ngân hàng bạn đọc có gợi ý tìm cổ phiếu
       ngân hàng. Lệnh này có liên quan không?"

   → Mục đích: Kiến thức vừa học được áp dụng ngay, không bị quên.

----------------------------------------------------------------------
Tóm lại
----------------------------------------------------------------------

Mục tiêu: "Học cái gì — dùng cái đó ngay lập tức."

Không cần AI, không mất phí, không chờ đợi. Kiến thức đã được soạn sẵn
và gắn vào từng bài báo, từng chỉ số. Bạn chỉ cần đọc, bấm nút, và
thực hành.

===============================
IV. QUY TRÌNH VẬN HÀNH TỔNG THỂ
===============================

----------------------------------------------------------------------
4.1. Vòng tuần hoàn
----------------------------------------------------------------------

Hệ thống vận hành theo một vòng tuần hoàn khép kín gồm 5 giai đoạn:

    Giai đoạn 1: ĐỌC BÁO THẬT
                 (AI tự động truy cập Cafef, Bloomberg...)

         |
         v

    Giai đoạn 2: PHÂN TÍCH BỐI CẢNH
                 (AI tổng hợp tình hình thị trường)

         |
         v

    Giai đoạn 3: SINH TIN TỨC MỚI
                 (AI viết báo và hiển thị lên trang web)

         |
         v

    Giai đoạn 4: CẬP NHẬT CÔNG TY
                 (AI toán tính tác động lên giá và tài chính)

         |
         v

    Giai đoạn 5: SINH BÀI VIẾT MXH
                 (Cộng đồng ảo phản ứng)

         |
         v

    QUAY LẠI GIAI ĐOẠN 2 (bắt đầu chu kỳ mới)

    Mỗi chu kỳ tương ứng với 1 ngày giao dịch mô phỏng.

----------------------------------------------------------------------
4.2. Tần suất hoạt động
----------------------------------------------------------------------

    Tác vụ                          Tần suất
    ------------------------------- ----------------------------
    AI đọc báo thật                  Mỗi 6 đến 12 tiếng
    AI sinh tin tức mới              Đầu mỗi phiên giao dịch
    AI cập nhật công ty              Sau mỗi tin tức mới
    AI sinh bài MXH                  Sau khi công ty thay đổi
    Người dùng giao dịch             Bất kỳ lúc nào
    AI cố vấn phản hồi               Tức thời (real-time)

----------------------------------------------------------------------
4.3. Phân công nhiệm vụ
----------------------------------------------------------------------

    Thành phần                       Nhiệm vụ
    -------------------------------  ------------------------------------------------
    AI đọc báo (news_crawler)        Thu thập tin tức thật từ các trang tài chính
    AI phân tích (financial_analyst) Đánh giá bối cảnh, xu hướng, mức độ ảnh hưởng
    AI viết báo (scenario_gen)       Sáng tác tin giả lập dựa trên bối cảnh thật
    AI làm toán (math_engine)        Tính giá cổ phiếu, lợi nhuận, margin, drawdown
    AI cố vấn (socratic_mentor)      Tư vấn và phản biện quyết định người dùng
    AI social                        Viết bài phốt, đánh giá, thông báo
    Giao diện web (Frontend)         Hiển thị trang báo, bản đồ, giao dịch
    Máy chủ (Backend)                Kết nối các thành phần với nhau
    Kho dữ liệu (Database)           Lưu trữ tin tức, người dùng, giao dịch

----------------------------------------------------------------------
4.4. Khởi động hệ thống
----------------------------------------------------------------------

Khi người dùng truy cập trang web lần đầu tiên, hệ thống trải qua 3 bước sau:

    Bước 1: Nạp kịch bản gốc (Seed data)
            - Bối cảnh: Lãi suất 4.5%, lạm phát 3.2%, GDP 6.5%
            - Danh sách: 20 công ty thuộc 5 ngành khác nhau
            - Giá khởi điểm cho mỗi cổ phiếu

    Bước 2: AI thực hiện chu kỳ đầu tiên
            - Đọc báo thật lần đầu
            - Phân tích bối cảnh
            - Viết lô tin tức đầu tiên
            - Cập nhật giá và tài chính công ty
            - Sinh bài viết mạng xã hội

    Bước 3: Trang web có dữ liệu
            - Người dùng bắt đầu hành trình: Đọc báo, Khám phá, Giao dịch

----------------------------------------------------------------------
4.5. Dung lượng dự kiến
----------------------------------------------------------------------

    Hạng mục                     Mỗi tháng           Mỗi năm
    ---------------------------  ------------------  ------------------
    Tin tức thật + AI            ~700 bài            ~8.400 bài
    Bài viết mạng xã hội         ~2.000 bài          ~24.000 bài
    Dung lượng lưu trữ           ~87 MB              ~1 đến 1.5 GB

===============================
V. NHẬT KÝ CẬP NHẬT
===============================

Ngày 30 tháng 07 năm 2026 — Khởi tạo dự án

    - Xác định ý tưởng và kiến trúc tổng thể
    - Thiết kế 4 khu vực chính:
        + Trang báo tài chính
        + Mạng xã hội đầu tư
        + Bản đồ doanh nghiệp
        + Giao diện giao dịch chứng khoán
    - Xây dựng quy trình vận hành:
        Đọc báo thật -> Phân tích -> Viết báo mới -> Cập nhật công ty -> Sinh bài MXH
    - Viết tài liệu hướng dẫn

Ngày 30 tháng 07 năm 2026 — Mở rộng & tối ưu phần Mạng xã hội

    - Mở rộng từ 2 loại bài viết lên 10 Persona chính (KOL ảo, F0, lùa gà,
      chim lợn, insider, meme...)
    - Bổ sung cơ chế lan truyền (Virality Score) và tác động ngược thị trường
    - Thêm UI/UX: Heatmap, Trending, nút Kiểm chứng AI Mentor

Ngày 30 tháng 07 năm 2026 — Thêm hệ thống Knowledge Base (Học & Áp dụng)

    - Xây dựng Knowledge Base tĩnh (YAML + regex) — 0 token AI
    - 3 điểm chạm: /news (badge khái niệm), /companies (áp dụng chỉ số),
      /trade (coach thực chiến)
    - Thêm section III vào README
