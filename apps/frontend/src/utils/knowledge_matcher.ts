/**
 * Keyword matching phía client — fallback khi backend `/knowledge/match` không
 * phản hồi, và nguồn "concept chip" cho Chế độ 1 (Hỏi đáp khái niệm).
 *
 * Glossary đồng bộ 26 khái niệm với `ai_engine/data/knowledge_base.yaml`
 * (docs/docs/ai_mentor_3mode_plan.md v2.0 mục 3.2). Không tự sửa nội dung ở đây
 * khi chưa sửa YAML — hai nguồn phải khớp.
 */
import type { KnowledgeResponse } from "@finsim/shared-types/generated/api-types";

export interface LocalConcept {
  id: string;
  keyword: string;
  concept: string;
  definition: string;
  explanation: string;
  example?: string;
  formula?: string;
  interpretation: string;
  related: string[];
  category: string;
  difficulty: number;
}

const LOCAL_GLOSSARY: LocalConcept[] = [
  {
    id: "pe",
    keyword: "p/e",
    concept: "P/E (Price-to-Earnings)",
    definition:
      "Tỷ lệ giá cổ phiếu chia cho lợi nhuận trên mỗi cổ phần (EPS) — đo mức giá người mua trả cho mỗi đồng lợi nhuận.",
    explanation:
      "P/E cho biết nhà đầu tư sẵn sàng trả bao nhiêu tiền cho mỗi đồng lợi nhuận tạo ra. P/E cao thường phản ánh kỳ vọng tăng trưởng mạnh; P/E thấp có thể là thị giá rẻ hoặc dấu hiệu tăng trưởng yếu.",
    example:
      "Cổ phiếu giá 100, EPS là 10, thì P/E = 100 / 10 = 10 lần. Tức bạn trả 10 đồng cho mỗi 1 đồng lợi nhuận hàng năm.",
    formula: "P/E = Giá / EPS",
    interpretation:
      "P/E cao chưa hẳn là 'đắt' và P/E thấp chưa hẳn là 'rẻ' — cần so sánh cùng ngành và cùng giai đoạn tăng trưởng.",
    related: ["eps", "net margin", "roe"],
    category: "định giá",
    difficulty: 1,
  },
  {
    id: "roe",
    keyword: "roe",
    concept: "ROE (Return on Equity)",
    definition:
      "Tỷ suất lợi nhuận trên vốn chủ sở hữu — đo hiệu quả tạo lợi nhuận trên mỗi đồng vốn mà cổ đông bỏ ra.",
    explanation:
      "ROE cao và ổn định nhiều năm thường phản ánh doanh nghiệp hoạt động hiệu quả. Tuy nhiên ROE cao có thể đến từ việc vay nợ nhiều, nên cần nhìn cùng hệ số nợ.",
    example: "Doanh nghiệp có lợi nhuận ròng 20 tỷ và vốn chủ 100 tỷ → ROE = 20%.",
    formula: "ROE = Lợi nhuận ròng / Vốn chủ sở hữu × 100%",
    interpretation:
      "ROE cao là tín hiệu tích cực về hiệu quả, nhưng phải kiểm tra nguồn gốc (hiệu quả hay đòn bẩy).",
    related: ["net margin", "eps", "p/e"],
    category: "tài chính doanh nghiệp",
    difficulty: 1,
  },
  {
    id: "eps",
    keyword: "eps",
    concept: "EPS (Earnings Per Share)",
    definition: "Lợi nhuận ròng tương ứng với mỗi cổ phiếu đang lưu hành.",
    explanation:
      "EPS là chỉ số cơ bản để đánh giá khả năng sinh lời trên mỗi cổ phần, và là thành phần của nhiều hệ số định giá như P/E.",
    example:
      "Lợi nhuận ròng 100 tỷ và 50 triệu cổ phiếu → EPS = 2.000 đồng/cổ.",
    formula: "EPS = Lợi nhuận ròng / Số cổ phiếu lưu hành",
    interpretation:
      "EPS tăng trưởng theo thời gian thường là dấu hiệu tích cực; cần xét chất lượng lợi nhuận, không chỉ con số.",
    related: ["p/e", "net margin", "roe"],
    category: "tài chính doanh nghiệp",
    difficulty: 1,
  },
  {
    id: "net-margin",
    keyword: "net margin",
    concept: "Biên lợi nhuận ròng (Net Margin)",
    definition:
      "Phần trăm doanh thu còn lại sau mọi chi phí, lãi vay và thuế — đo hiệu quả sinh lời tổng thể.",
    explanation:
      "Net margin cao nghĩa là doanh nghiệp giữ lại được nhiều hơn sau khi thanh toán chi phí. So sánh cùng ngành để đánh giá tương đối.",
    example: "Doanh thu 200 tỷ, lợi nhuận ròng 20 tỷ → Net margin = 10%.",
    formula: "Net margin = Lợi nhuận ròng / Doanh thu × 100%",
    interpretation:
      "Biên cao tốt về hiệu quả, nhưng biên thấp có thể chấp nhận nếu mô hình xoay vòng vốn nhanh.",
    related: ["roe", "eps", "p/e"],
    category: "tài chính doanh nghiệp",
    difficulty: 1,
  },
  {
    id: "cut-loss",
    keyword: "cut loss",
    concept: "Cắt lỗ (Stop-Loss)",
    definition:
      "Mốc hoặc lệnh thoát khỏi vị thế khi lỗ chạm mức định trước, nhằm giới hạn thiệt hại.",
    explanation:
      "Cắt lỗ là kỷ luật quản trị rủi ro giúp tránh để một sai lầm nhỏ trở thành tổn thất lớn. Một kế hoạch đầu tư tốt thường xác định trước mức cắt lỗ.",
    example:
      "Mua ở giá 50 và đặt mốc cắt lỗ 45: nếu giá chạm 45, thoát lệnh để nhận lỗ giới hạn 10%.",
    interpretation:
      "Không có mốc cắt lỗ nào chung cho mọi người — mức hợp lý phụ thuộc khả năng chịu đựng rủi ro và kế hoạch của bạn.",
    related: ["risk", "limit order", "volatility"],
    category: "quản trị rủi ro",
    difficulty: 1,
  },
  {
    id: "risk",
    keyword: "risk",
    concept: "Quản trị rủi ro (Risk Management)",
    definition:
      "Quy trình nhận diện, đánh giá, giới hạn và xử lý rủi ro trong từng quyết định cũng như toàn danh mục.",
    explanation:
      "Quản trị rủi ro không phải là tránh mọi rủi ro, mà là biết mình đang chấp nhận bao nhiêu và đã chuẩn bị cho kịch bản xấu nhất.",
    example:
      "Trước khi vào lệnh, xác định rõ: mức lỗ tối đa chấp nhận, tỷ trọng vốn dành cho vị thế, và kịch bản xử lý khi giá đảo chiều.",
    interpretation:
      "Quản trị rủi ro tốt không loại bỏ hoàn toàn rủi ro nhưng giúp tổn thất trong tầm kiểm soát.",
    related: ["cut loss", "diversification", "volatility"],
    category: "quản trị rủi ro",
    difficulty: 1,
  },
  {
    id: "diversification",
    keyword: "diversification",
    concept: "Đa dạng hoá (Diversification)",
    definition:
      "Phân bổ vốn vào nhiều loại tài sản hoặc cổ phiếu khác nhau để giảm tác động khi một vị thế giảm giá.",
    explanation:
      "Đa dạng hoá giúp giảm rủi ro tập trung nhưng không xoá bỏ rủi ro hệ thống. Mức đa dạng hợp lý phụ thuộc quy mô vốn và hiểu biết của bạn.",
    example:
      "Thay vì dồn toàn bộ vốn vào một cổ phiếu, chia cho 5-10 cổ phiếu thuộc các ngành khác nhau.",
    interpretation:
      "Đa dạng hoá là công cụ quản trị rủi ro; lạm dụng có thể làm loãng lợi nhuận và khó theo dõi.",
    related: ["risk", "allocation", "market cap"],
    category: "quản trị rủi ro",
    difficulty: 1,
  },
  {
    id: "allocation",
    keyword: "allocation",
    concept: "Phân bổ vốn (Allocation)",
    definition:
      "Cách chia vốn giữa các loại tài sản hoặc vị thế, theo mục tiêu và mức chấp nhận rủi ro.",
    explanation:
      "Phân bổ vốn quyết định phần lớn biến động của danh mục. Cân bằng tiền mặt, trái phiếu, cổ phiếu phù hợp với mục tiêu giúp giảm căng thẳng và rủi ro thua lỗ lớn.",
    example:
      "Danh mục 100 triệu: 60% cổ phiếu vốn hoá lớn, 30% trái phiếu, 10% tiền mặt dự phòng.",
    interpretation:
      "Không có tỷ lệ 'đúng' tuyệt đối — tỷ lệ phụ thuộc mục tiêu, thời gian và khả năng chịu đựng rủi ro của từng người.",
    related: ["risk", "diversification", "market cap"],
    category: "quản trị rủi ro",
    difficulty: 1,
  },
  {
    id: "compound-interest",
    keyword: "compound interest",
    concept: "Lãi kép (Compound Interest)",
    definition:
      "Lợi nhuận được tái đầu tư để tiếp tục sinh lợi nhuận mới — khiến tài sản tăng trưởng theo cấp số nhân theo thời gian.",
    explanation:
      "Sức mạnh của lãi kép nằm ở thời gian. Bắt đầu sớm dù số tiền nhỏ vẫn có thể tạo kết quả lớn sau nhiều năm nhờ phần lợi nhuận 'đẻ' thêm lợi nhuận.",
    example:
      "Đầu tư 100 triệu với mức sinh lời 10%/năm: sau 20 năm trở thành ~100 × 1.1^20 ≈ 673 triệu nếu không rút ra.",
    formula: "Giá trị tương lai = Vốn gốc × (1 + lãi suất)^số kỳ",
    interpretation:
      "Lãi kép là con dao hai lưỡi với khoản vay: lãi vay cũng kép lên. Hãy để thời gian đứng về phía bạn.",
    related: ["time value", "dividend", "risk"],
    category: "kiến thức nền",
    difficulty: 1,
  },
  {
    id: "time-value",
    keyword: "time value",
    concept: "Giá trị thời gian của tiền (Time Value of Money)",
    definition:
      "Nguyên tắc một đồng hôm nay có giá trị hơn một đồng trong tương lai, vì ngày hôm nay tiền có thể được đầu tư để sinh lời.",
    explanation:
      "Đây là nền tảng của mọi quyết định tài chính: so sánh dòng tiền ở các thời điểm khác nhau cần quy về cùng một thời điểm, thường là hiện tại, qua chiết khấu.",
    example:
      "Nhận 100 triệu ngay bây giờ hay sau 1 năm? 100 triệu hôm nay có thể sinh lời, nên 'lãi' hơn nhận cùng số tiền vào năm sau.",
    interpretation:
      "Khi so sánh các phương án đầu tư, luôn chú ý đến thời điểm của dòng tiền, không chỉ con số thô.",
    related: ["compound interest", "volatility"],
    category: "kiến thức nền",
    difficulty: 1,
  },
  {
    id: "market-cap",
    keyword: "market cap",
    concept: "Vốn hoá thị trường (Market Cap)",
    definition:
      "Tổng giá trị thị trường của một công ty = giá cổ phiếu × số cổ phiếu lưu hành.",
    explanation:
      "Vốn hoá giúp phân loại doanh nghiệp theo quy mô (lớn/vừa/nhỏ) — cổ phiếu vốn hoá lớn thường biến động nhẹ hơn, vốn hoá nhỏ tiềm năng cao nhưng rủi ro hơn.",
    example:
      "Cổ phiếu giá 50.000 đồng, có 1 tỷ cổ phiếu → vốn hoá 50.000 tỷ đồng.",
    formula: "Market cap = Giá × Số cổ phiếu lưu hành",
    interpretation:
      "Market cap phản ánh giá thị trường đặt cho công ty tại thời điểm đó, không phải 'giá trị đúng'.",
    related: ["p/e", "volume", "diversification"],
    category: "định giá",
    difficulty: 1,
  },
  {
    id: "dividend",
    keyword: "dividend",
    concept: "Cổ tức (Dividend)",
    definition:
      "Phần lợi nhuận mà công ty trả cho cổ đông, thường bằng tiền mặt hoặc cổ phiếu.",
    explanation:
      "Cổ tức là một nguồn thu nhập của nhà đầu tư. Doanh nghiệp có thể chọn trả cổ tức hoặc giữ lại để tái đầu tư; cả hai đều là chiến lược hợp lý tuỳ giai đoạn phát triển.",
    example:
      "Công ty trả cổ tức 2.000 đồng/cổ/năm với giá 40.000 → tỷ suất cổ tức 5%/năm.",
    formula: "Tỷ suất cổ tức = Cổ tức mỗi cổ / Giá × 100%",
    interpretation:
      "Tỷ suất cổ tức cao phải cân nhắc cùng sức khoẻ tài chính — nếu công ty vay nợ để trả cổ tức thì khác.",
    related: ["compound interest", "net margin"],
    category: "kiến thức nền",
    difficulty: 1,
  },
  {
    id: "market-order",
    keyword: "market order",
    concept: "Lệnh thị trường (Market Order)",
    definition:
      "Lệnh mua/bán ngay tại giá khớp lệnh hiện hành — ưu tiên khớp lệnh, không đảm bảo giá.",
    explanation:
      "Lệnh thị trường phù hợp khi cần vào/thoát nhanh và chấp nhận giá thực tế khớp có thể kém hơn giá hiển thị (do trượt giá, nhất là khi khối lượng lớn).",
    example:
      "Đặt 'mua 1.000 cổ theo giá thị trường' → hệ thống khớp ngay ở giá đối ứng hiện có trên sổ lệnh.",
    interpretation:
      "Nhanh và chắc chắn khớp, nhưng bạn không kiểm soát được giá chính xác.",
    related: ["limit order", "slippage", "volume"],
    category: "giao dịch",
    difficulty: 1,
  },
  {
    id: "limit-order",
    keyword: "limit order",
    concept: "Lệnh giới hạn (Limit Order)",
    definition:
      "Lệnh chỉ khớp ở mức giá bằng hoặc tốt hơn mức bạn đặt — kiểm soát giá nhưng không đảm bảo khớp.",
    explanation:
      "Lệnh giới hạn giúp bạn không trả quá mức mong muốn, nhưng có thể bị bỏ lỡ nếu giá không chạm mức. Là công cụ quan trọng trong kế hoạch giao dịch.",
    example:
      "Đặt lệnh mua 'tối đa 20.000' → chỉ khớp khi giá nhỏ hơn hoặc bằng 20.000.",
    interpretation:
      "Kiểm soát giá tốt hơn lệnh thị trường, nhưng thường không chắc chắn khớp ngay.",
    related: ["market order", "cut loss", "slippage"],
    category: "giao dịch",
    difficulty: 1,
  },
  {
    id: "slippage",
    keyword: "slippage",
    concept: "Trượt giá (Slippage)",
    definition:
      "Chênh lệch giữa giá khớp thực tế và giá dự kiến khi đặt lệnh, do thanh khoản hoặc tốc độ thay đổi giá.",
    explanation:
      "Trượt giá thường gặp khi lệnh lớn hoặc thị trường biến động mạnh. Hiểu về trượt giá giúp bạn đặt lệnh thực tế hơn.",
    example:
      "Giá hiển thị 20.000 nhưng lệnh thị trường khớp ở 20.200 → trượt 200 đồng (1%).",
    interpretation:
      "Không hoàn toàn tránh được; giảm tác động bằng cách dùng lệnh giới hạn và tránh lệnh quá lớn trong thị trường kém thanh khoản.",
    related: ["limit order", "market order", "volume"],
    category: "giao dịch",
    difficulty: 2,
  },
  {
    id: "volume",
    keyword: "volume",
    concept: "Khối lượng giao dịch (Volume)",
    definition:
      "Số cổ phiếu được giao dịch trong một khoảng thời gian — phản ánh mức độ quan tâm và thanh khoản.",
    explanation:
      "Giá đi kèm khối lượng lớn thường đáng tin cậy hơn giá đi kèm khối lượng nhỏ. Khối lượng cũng giúp nhận diện sự tham gia của thị trường.",
    example:
      "Hôm nay 2 triệu cổ phiếu được khớp so với trung bình 500 nghìn — cho thấy thanh khoản bất thường.",
    interpretation:
      "Khối lượng cao chưa nói lên xu hướng — cần nhìn kèm giá để hiểu bên nào đang chiếm ưu thế.",
    related: ["support/resistance", "liquidity", "trend"],
    category: "phân tích kỹ thuật",
    difficulty: 1,
  },
  {
    id: "support-resistance",
    keyword: "support/resistance",
    concept: "Hỗ trợ & Kháng cự (Support / Resistance)",
    definition:
      "Các mức giá mà giá có xu hướng dừng giảm (hỗ trợ) hoặc dừng tăng (kháng cự) do tập trung lệnh mua/bán tại đó.",
    explanation:
      "Hỗ trợ và kháng cự là khái niệm tâm lý thị trường, không phải quy luật đảm bảo. Chúng hữu ích khi kết hợp với khối lượng và xu hướng.",
    example:
      "Giá nhiều lần chạm 30.000 rồi bật lên → 30.000 được xem là vùng hỗ trợ.",
    interpretation:
      "Ngưỡng có thể bị phá vỡ; khi phá vỡ thường kèm khối lượng lớn, cần theo dõi không quá cứng nhắc.",
    related: ["volume", "trend", "moving average"],
    category: "phân tích kỹ thuật",
    difficulty: 2,
  },
  {
    id: "trend",
    keyword: "trend",
    concept: "Xu hướng (Trend)",
    definition:
      "Hướng di chuyển chung của giá trong một khoảng thời gian: tăng, giảm hoặc đi ngang.",
    explanation:
      "Nhận diện xu hướng giúp định vị quyết định — giao dịch thuận xu hướng thường được ưa chuộng. Xu hướng có thể đảo chiều bất ngờ nên luôn gắn kèm quản trị rủi ro.",
    example:
      "Giá tạo đáy sau đó tăng cao hơn nhiều lần liên tiếp → xu hướng tăng ngắn hạn.",
    interpretation:
      "Xu hướng có nhiều khung thời gian; xu hướng lớn và nhỏ có thể ngược nhau.",
    related: ["moving average", "support/resistance", "volume"],
    category: "phân tích kỹ thuật",
    difficulty: 1,
  },
  {
    id: "moving-average",
    keyword: "moving average",
    concept: "Trung bình động (Moving Average)",
    definition:
      "Đường trung bình giá trong N phiên liên tiếp, dùng để làm mượt biến động ngắn hạn và nhận diện xu hướng.",
    explanation:
      "Trung bình động không dự đoán giá mà tóm tắt lịch sử. Trung bình động ngắn hạn (5-20 phiên) phản ứng nhanh, dài hạn (50-200 phiên) thể hiện xu hướng nền.",
    example: "Tính trung bình động 20 phiên: cộng giá 20 phiên rồi chia 20.",
    formula: "MA(N) = Tổng giá N phiên / N",
    interpretation:
      "MA có độ trễ trong dữ liệu; nên dùng kết hợp nhiều loại và không xem nó là tín hiệu đảm bảo.",
    related: ["trend", "support/resistance", "volume"],
    category: "phân tích kỹ thuật",
    difficulty: 2,
  },
  {
    id: "liquidity",
    keyword: "liquidity",
    concept: "Thanh khoản (Liquidity)",
    definition:
      "Khả năng mua/bán một tài sản mà không làm thay đổi giá quá nhiều.",
    explanation:
      "Tài sản thanh khoản cao khớp dễ, trượt giá thấp; thanh khoản thấp khó vào/thoát lệnh khối lượng lớn. Đây là yếu tố thường bị người mới bỏ qua.",
    example:
      "Cổ phiếu có 10 triệu cổ khớp mỗi phiên thường thanh khoản tốt hơn cổ phiếu chỉ khớp 10 nghìn.",
    interpretation:
      "Thanh khoản quan trọng nhất khi bạn cần thoát lệnh — lúc khó khăn mà không khớp được là rủi ro lớn.",
    related: ["volume", "slippage", "market order"],
    category: "giao dịch",
    difficulty: 1,
  },
  {
    id: "volatility",
    keyword: "volatility",
    concept: "Biến động (Volatility)",
    definition:
      "Mức độ dao động giá của một tài sản trong một khoảng thời gian.",
    explanation:
      "Biến động cao nghĩa là giá thay đổi mạnh theo cả hai chiều — tiềm năng lợi nhuận lớn kèm rủi ro thua lỗ sâu. Nhà đầu tư nên hiểu rõ biến động của tài sản mình nắm giữ.",
    example:
      "Cổ phiếu A tăng/giảm 1% mỗi phiên biến động thấp hơn cổ phiếu B chênh 5% mỗi phiên.",
    interpretation:
      "Biến động không mang dấu hiệu tốt/xấu một chiều — nó mô tả mức độ dao động, và mức phù hợp phụ thuộc người chơi.",
    related: ["risk", "trend", "cut loss"],
    category: "quản trị rủi ro",
    difficulty: 1,
  },
  {
    id: "fomo",
    keyword: "fomo",
    concept: "FOMO (Fear Of Missing Out)",
    definition:
      "Cảm giác sợ bỏ lỡ cơ hội sinh lời khi thấy người khác đang kiếm lợi nhuận.",
    explanation:
      "FOMO thường khiến bạn quyết định vội vàng, không theo kế hoạch, dễ mua đuổi đỉnh. Đây là thiên kiến tâm lý phổ biến và là trọng tâm của phương pháp phản biện Socratic.",
    example:
      "Thấy cả room nói cổ phiếu sắp tăng mạnh, bạn vội mua dù chưa phân tích — đó là FOMO.",
    interpretation:
      "Nhận diện FOMO giúp bạn quay lại với quy trình và kế hoạch thay vì chạy theo đám đông.",
    related: ["risk", "trend", "support/resistance"],
    category: "tâm lý",
    difficulty: 1,
  },
  {
    id: "herding",
    keyword: "herding",
    concept: "Hiệu ứng bầy đàn (Herding)",
    definition:
      "Xu hướng bắt chước quyết định của số đông thay vì dựa trên phân tích của chính mình.",
    explanation:
      "Bầy đàn dễ tạo ra các cơn sóng giá ngắn hạn không tương xứng với giá trị thực. Hiểu để tránh bị cuốn theo.",
    example:
      "Mọi người đổ xô mua một cổ phiếu chỉ vì 'ai cũng mua' mà chưa xem báo cáo tài chính.",
    interpretation:
      "Không phải lúc nào đám đông cũng sai, nhưng quyết định nên có cơ sở của riêng bạn.",
    related: ["fomo", "confirmation bias"],
    category: "tâm lý",
    difficulty: 1,
  },
  {
    id: "confirmation-bias",
    keyword: "confirmation bias",
    concept: "Thiên kiến xác nhận (Confirmation Bias)",
    definition:
      "Xu hướng tìm kiếm và tin vào thông tin ủng hộ quan điểm sẵn có, bỏ qua thông tin ngược lại.",
    explanation:
      "Thiên kiến xác nhận khiến bạn tự xây 'bức tường' bảo vệ một quyết định dù dữ liệu mâu thuẫn. Cách đối phó: chủ động tìm ý kiến trái chiều.",
    example:
      "Bạn đã mua cổ X nên chỉ đọc tin tích cực về X và bỏ qua cảnh báo rủi ro.",
    interpretation:
      "Biết mình có thiên kiến là bước đầu để đưa quyết định khách quan hơn.",
    related: ["herding", "fomo", "overconfidence"],
    category: "tâm lý",
    difficulty: 2,
  },
  {
    id: "overconfidence",
    keyword: "overconfidence",
    concept: "Quá tự tin (Overconfidence)",
    definition:
      "Đánh giá quá cao độ chính xác nhận định hoặc kỹ năng ra quyết định của bản thân.",
    explanation:
      "Quá tự tin thường đến sau vài lần đúng liên tiếp. Nó khiến bạn giao dịch khối lượng lớn hơn và bỏ qua kế hoạch phòng ngừa.",
    example:
      "Sau 3 phiên đoán đúng hướng thị trường, bạn tin mình 'không thể sai' và tăng gấp đôi vị thế.",
    interpretation:
      "Ghi nhận chuỗi thắng cũng cần ghi nhận yếu tố may mắn — kế hoạch và kỷ luật quan trọng hơn cảm giác chắc chắn.",
    related: ["confirmation bias", "fomo", "risk"],
    category: "tâm lý",
    difficulty: 2,
  },
  {
    id: "risk-systematic",
    keyword: "systematic risk",
    concept: "Rủi ro hệ thống (Systematic Risk)",
    definition:
      "Rủi ro ảnh hưởng toàn thị trường, không thể loại bỏ bằng đa dạng hoá.",
    explanation:
      "Rủi ro hệ thống như suy thoái, thay đổi chính sách lãi suất tác động đến hầu hết cổ phiếu. Khác với rủi ro phi hệ thống (riêng một công ty), nó không biến mất khi bạn nắm nhiều cổ phiếu.",
    example:
      "Một quyết định tăng lãi suất của ngân hàng trung ương làm gần như toàn bộ cổ phiếu điều chỉnh.",
    interpretation:
      "Không thể loại bỏ rủi ro hệ thống hoàn toàn; bạn quản trị nó bằng mức độ tham gia thị trường và kỷ luật cắt lỗ.",
    related: ["risk", "diversification", "volatility"],
    category: "quản trị rủi ro",
    difficulty: 2,
  },
  {
    id: "alpha-beta",
    keyword: "alpha",
    concept: "Alpha / Beta",
    definition:
      "Beta đo độ nhạy cảm của cổ phiếu với biến động thị trường; alpha đo phần lợi nhuận vượt trội so với kỳ vọng từ beta.",
    explanation:
      "Beta = 1 đi cùng thị trường; beta > 1 biến động mạnh hơn; beta < 1 yếu hơn. Alpha dương nghĩa là cổ phiếu/danh mục làm tốt hơn mức kỳ vọng theo rủi ro.",
    example:
      "Beta 1,5: thị trường tăng 10% thì cổ phiếu kỳ vọng tăng 15%; nếu thực tế tăng 18% → alpha dương.",
    formula: "Alpha = Lợi nhuận thực tế − (Beta × Lợi nhuận thị trường)",
    interpretation:
      "Beta và alpha chỉ có ý nghĩa về thống kê trong giai đoạn dài và cần dữ liệu đủ — không phạt người dùng phải tự tính ngay.",
    related: ["volatility", "risk", "market cap"],
    category: "định giá",
    difficulty: 3,
  },
];

function normalize(text: string): string {
  return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

const TERM_CACHE: Map<string, LocalConcept[]> = new Map();

/** Tra cứu khái niệm từ glossary local theo đoạn text (không dấu, tiếng Việt ok). */
export function matchKnowledgeLocal(text: string): LocalConcept[] {
  if (!text.trim()) {
    return [];
  }
  const key = text.trim().toLowerCase();
  const cached = TERM_CACHE.get(key);
  if (cached) {
    return cached;
  }
  const haystack = normalize(text);
  const matched = LOCAL_GLOSSARY.filter((entry) => {
    const terms = [entry.keyword, ...entry.related];
    return terms.some((term) => haystack.includes(normalize(term)));
  });
  TERM_CACHE.set(key, matched);
  return matched;
}

/** Lấy 1 khái niệm khớp duy nhất (prefer keyword chính xác) — cho concept card. */
export function lookupConceptLocal(text: string): LocalConcept | null {
  const matched = matchKnowledgeLocal(text);
  if (matched.length === 0) {
    return null;
  }
  return (
    matched.find((entry) => haystackContainsKeyword(text, entry.keyword)) ??
    matched[0]
  );
}

function haystackContainsKeyword(text: string, keyword: string): boolean {
  return normalize(text).includes(normalize(keyword));
}

/** Chuyển LocalConcept → KnowledgeResponse (hợp khi cần API style). */
export function toKnowledgeResponse(
  concept: LocalConcept,
): KnowledgeResponse {
  return {
    id: `local-${concept.id}`,
    keyword: concept.keyword,
    concept: concept.concept,
    definition: concept.definition,
    category: concept.category,
    difficulty: concept.difficulty,
    related_keywords: concept.related,
    created_at: new Date(0).toISOString(),
  };
}

/** Danh sách khái niệm (chips) cho demo mode / gợi ý khi gõ. */
export function listKnowledgeLocal(): LocalConcept[] {
  return LOCAL_GLOSSARY;
}

export { LOCAL_GLOSSARY };