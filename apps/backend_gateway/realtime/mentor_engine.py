"""Deterministic Socratic Mentor Engine — 0 token Gemini.

Port tầng fallback của ``SocraticMentorAgent`` (ai_engine) sang gateway để
WebSocket mentor luôn trả phản hồi Socratic chuẩn mà KHÔNG tốn một lượt Gemini
nào. Question-bank dùng chung nội dung với ``ai_engine/prompts/mentor_prompts.yaml``:

- 8 nhóm thiên kiến tâm lý (FOMO, bầy đàn, loss aversion, ...).
- Phát hiện focus bằng keyword scoring theo ``priority_order``.
- Câu hỏi phản biện + bài tập quy trình + disclaimer, không chứa lời khuyên mua/bán.

Nguyên tắc tuyệt đối: KHÔNG đưa lời khuyên mua/bán, KHÔNG phán xét đúng/sai —
chỉ đặt câu hỏi phản biện. Dữ liệu là hằng số (không có đầu vào AI), nên không
cần quét chính sách runtime.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Thứ tự ưu tiên khi nhiều focus cùng có điểm: giống ai_engine mentor_prompts.yaml.
_PRIORITY_ORDER = [
    "fomo",
    "herding",
    "loss_aversion",
    "overconfidence",
    "anchoring",
    "confirmation_bias",
    "noise_trading",
    "process",
]

# Keyword phát hiện thiên kiến tâm lý (đồng bộ với ai_engine).
_DETECTION: dict[str, list[str]] = {
    "fomo": [
        "fomo",
        "bỏ lỡ",
        "bùng nổ",
        "to the moon",
        "lên không ngừng",
        "tăng vùn vụt",
        "đu theo",
        "ai cũng mua",
        "sóng mới",
        "kẻo hết",
        "sốt",
    ],
    "herding": [
        "nghe theo",
        "cả group",
        "cả room",
        "ai cũng khuyên",
        "admin khuyến nghị",
        "mọi người đều",
        "đám đông",
        "cả hội",
    ],
    "loss_aversion": [
        "đang lỗ",
        "thua lỗ",
        "lỗ sâu",
        "chờ về bờ",
        "gỡ vốn",
        "không nỡ bán",
        "cắt lỗ thì tiếc",
    ],
    "overconfidence": [
        "chắc chắn",
        "chắc thắng",
        "không thể sai",
        "nghiên cứu kỹ rồi",
        "tự tin tuyệt đối",
        "bao giờ cũng đúng",
    ],
    "anchoring": [
        "giá cũ",
        "từng đạt",
        "so với hôm qua",
        "tham chiếu",
        "về mốc",
        "hồi giá cao hơn",
    ],
    "confirmation_bias": [
        "chỉ thấy tin tốt",
        "tìm đủ lý do",
        "ủng hộ quyết định",
        "phớt lờ tin xấu",
        "phân tích đều ủng hộ",
    ],
    "noise_trading": [
        "tin đồn",
        "nghe nói",
        "insider",
        "mai có tin",
        "bí mật",
        "mua ngay bây giờ",
    ],
}

# Question-bank mỗi focus: câu hỏi phản biện + bài tập quy trình + nhãn kiến thức.
_QUESTION_BANK: dict[str, dict[str, Any]] = {
    "fomo": {
        "questions": [
            "Điều gì khiến bạn tin rằng nhịp tăng này sẽ còn tiếp tục, "
            "thay vì chỉ là cơn sóng ngắn hạn?",
            "Nếu tất cả những người đang hào hứng mua trên mạng xã hội đều sai, "
            "bạn sẽ phát hiện ra điều đó bằng cách nào?",
            "Bạn đã chuẩn bị kịch bản xử lý khi giá đi ngược kỳ vọng "
            "ngay sau khi bạn quyết định chưa?",
        ],
        "coaching_tip": (
            "Viết ra 3 kịch bản có thể xảy ra (tăng mạnh, đi ngang, giảm mạnh) kèm "
            "phản ứng của bạn với từng kịch bản, rồi đối chiếu xem kịch bản nào bạn "
            "chưa chuẩn bị."
        ),
    },
    "herding": {
        "questions": [
            "Quyết định của bạn dựa trên phân tích của chính bạn, "
            "hay dựa trên việc nhiều người khác cùng làm giống vậy?",
            "Nếu cộng đồng mạng hôm nay quay ngoắt 180 độ, "
            "bạn sẽ giữ nguyên lập trường hay lật theo họ?",
            "Bạn có thể chỉ ra một điểm yếu trong nhận định phổ biến "
            "mà mọi người đang tin không?",
        ],
        "coaching_tip": (
            "Ghi lại nguồn gốc từng thông tin bạn đang dựa vào: bài báo nào, "
            "bài viết mạng xã hội nào, con số nào. Sau đó đánh dấu xem nguồn nào "
            "là dữ liệu, nguồn nào chỉ là ý kiến của đám đông."
        ),
    },
    "loss_aversion": {
        "questions": [
            "Nếu bạn đang đứng ở vị trí người ngoài nhìn vào danh mục này, "
            "bạn sẽ khuyên người chủ nó xử lý thế nào?",
            "Việc chờ đợi để gỡ vốn có làm quyết định của bạn khách quan hơn không, "
            "hay chỉ khiến bạn đeo đuổi một con số trong quá khứ?",
            "Chi phí cơ hội của việc giữ một vị thế đang lỗ là gì?",
        ],
        "coaching_tip": (
            "Tách hai câu hỏi riêng biệt: (1) giữ hay thoát khỏi vị thế hiện tại, "
            "và (2) mức giá nào bạn từng trả. Viết câu trả lời cho câu (1) "
            "mà không nhắc đến câu (2)."
        ),
    },
    "overconfidence": {
        "questions": [
            "Điều gì có thể khiến nhận định của bạn sai, "
            "dù bạn đã tự tin vào nó?",
            "Bạn có từng đúng mà không phải vì phân tích của mình không?",
            "Nếu buộc phải đặt cược rằng mình sai, bạn sẽ đặt cược vào kịch bản nào "
            "và với xác suất bao nhiêu?",
        ],
        "coaching_tip": (
            "Liệt kê 3 lý do khiến quyết định của bạn có thể thất bại. Nếu không "
            "tìm ra nổi 3 lý do, hãy tự hỏi mình đang thiếu thông tin gì."
        ),
    },
    "anchoring": {
        "questions": [
            "Mức giá bạn đang so sánh được lấy từ đâu, và nó có còn phản ánh "
            "giá trị hiện tại của doanh nghiệp không?",
            "Nếu bạn chưa từng biết mức giá cũ, "
            "bạn sẽ định giá cổ phiếu này như thế nào?",
            "Con số bạn đang bám víu có thay đổi bất kỳ yếu tố cơ bản nào "
            "của công ty không?",
        ],
        "coaching_tip": (
            "Viết ra giá trị bạn ước tính cho cổ phiếu dựa trên báo cáo tài chính "
            "hiện tại, KHÔNG nhìn vào bất kỳ mức giá lịch sử nào. So sánh hai con số "
            "sau khi đã viết xong."
        ),
    },
    "confirmation_bias": {
        "questions": [
            "Bạn đã chủ động tìm kiếm thông tin PHẢN BÁC quyết định của mình, "
            "hay chỉ gom nhặt những gì ủng hộ nó?",
            "Nếu cùng một bài báo mang dấu hiệu tiêu cực, "
            "bạn sẽ đọc kỹ đến đâu?",
            "Lần gần nhất bạn thay đổi quan điểm vì một bằng chứng mới là khi nào?",
        ],
        "coaching_tip": (
            "Tìm 2 nguồn tin trái chiều về cùng một chủ đề và tóm tắt lập luận "
            "của cả hai bên trước khi quyết định."
        ),
    },
    "noise_trading": {
        "questions": [
            "Thông tin bạn vừa nghe có kiểm chứng được từ báo cáo tài chính "
            "hoặc tin tức chính thức không?",
            "Nếu tin đồn đó không bao giờ thành sự thật, "
            "quyết định của bạn dựa trên cái gì?",
            "Bạn có phân biệt được đâu là tín hiệu có giá trị, "
            "đâu chỉ là tiếng ồn của thị trường không?",
        ],
        "coaching_tip": (
            "Với mỗi thông tin bạn định hành động, ghi nguồn gốc và mức độ tin cậy "
            "(1-5). Chỉ xem xét hành động khi nguồn tin đạt độ tin cậy cao "
            "và có thể kiểm chứng."
        ),
    },
    "process": {
        "questions": [
            "Trước khi hành động, bạn đã xác định giới hạn chịu lỗ và mục tiêu "
            "của quyết định này chưa?",
            "Thông tin bạn đang dựa vào đến từ đâu, và độ tin cậy của nó "
            "được kiểm chứng bằng cách nào?",
            "Nếu quyết định này thất bại, hậu quả lớn nhất là gì "
            "và bạn có kế hoạch xử lý không?",
        ],
        "coaching_tip": (
            "Viết ra câu trả lời cho 3 câu hỏi: tôi hành động vì lý do gì, "
            "nguồn thông tin đó đáng tin cậy ở mức nào, và tôi sẽ làm gì "
            "nếu mọi thứ ngược lại với kỳ vọng."
        ),
    },
}

_DISCLAIMER = (
    "Capia là môi trường mô phỏng. Tôi không đưa ra lời khuyên mua bán — "
    "tôi chỉ giúp bạn phản biện quyết định của chính mình."
)

# ─── Glossary khái niệm (deterministic, đồng bộ ai_engine/data/knowledge_base.yaml) ──
# Chỉ là bản mirror 0-token cho gateway; nguồn chân lý + nội dung đầy đủ nằm ở
# ai_engine (docs/ai_mentor_3mode_plan.md v2.0). test_mentor_content_sync đảm bảo
# không drift giữa hai nơi.
_CONCEPT_GLOSSARY: dict[str, dict[str, str]] = {
    "pe": {
        "name": "P/E (Price-to-Earnings)",
        "keywords": ["p/e", "p e", "giá trên lợi nhuận", "price-to-earnings", "hệ số pe"],
        "definition": (
            "Tỷ lệ giá cổ phiếu chia cho lợi nhuận trên mỗi cổ phần (EPS) — đo "
            "mức giá bạn trả cho mỗi đồng lợi nhuận."
        ),
        "explanation": (
            "P/E cao thường nghĩa là nhà đầu tư kỳ vọng tăng trưởng; P/E thấp có thể "
            "là rẻ hoặc là dấu hiệu tăng trưởng yếu."
        ),
        "formula": "P/E = Giá / EPS",
    },
    "roe": {
        "name": "ROE (Return on Equity)",
        "keywords": ["roe", "return on equity", "lợi nhuận trên vốn chủ"],
        "definition": (
            "Khả năng sinh lời của vốn chủ sở hữu — bao nhiêu lợi nhuận tạo ra trên "
            "mỗi đồng vốn cổ đông bỏ ra."
        ),
        "explanation": (
            "ROE cao + bền vững thường phản ánh doanh nghiệp hiệu quả, nhưng nên "
            "đối chiếu với vay nợ."
        ),
        "formula": "ROE = Lợi nhuận ròng / Vốn chủ sở hữu",
    },
    "net_margin": {
        "name": "Biên lợi nhuận ròng (Net Margin)",
        "keywords": ["net margin", "biên lợi nhuận ròng", "biên lợi nhuận"],
        "definition": (
            "Phần trăm doanh thu còn lại sau mọi chi phí, thuế — đo độ hiệu quả "
            "sinh lời tổng thể."
        ),
        "explanation": "Net margin cao cho thấy doanh nghiệp kiểm soát chi phí tốt.",
        "formula": "Net Margin = Lợi nhuận ròng / Doanh thu × 100%",
    },
    "cut_loss": {
        "name": "Cắt lỗ (Stop-Loss)",
        "keywords": ["cắt lỗ", "stop-loss", "stop loss", "chốt lỗ"],
        "definition": (
            "Lệnh/mốc thoát khỏi vị thế khi lỗ đạt một mức định trước để giới hạn "
            "thiệt hại."
        ),
        "explanation": (
            "Cắt lỗ giúp quản trị rủi ro — tránh để một sai lầm tài chính ăn mòn "
            "cả danh mục."
        ),
    },
    "risk": {
        "name": "Quản trị rủi ro (Risk Management)",
        "keywords": ["quản trị rủi ro", "rủi ro", "risk management", "risk"],
        "definition": (
            "Quy trình nhận diện, đánh giá và giới hạn rủi ro trong từng quyết định "
            "và cả danh mục."
        ),
        "explanation": (
            "Nhà đầu tư kỷ luật xác định trước mức chịu lỗ, tỷ trọng vị thế và "
            "kịch bản xấu nhất."
        ),
    },
    "volume": {
        "name": "Khối lượng giao dịch (Volume)",
        "keywords": ["volume", "khối lượng giao dịch", "khối lượng"],
        "definition": (
            "Số cổ phiếu được giao dịch trong một khoảng thời gian — phản ánh độ "
            "quan tâm và thanh khoản."
        ),
        "explanation": "Giá đi kèm volume lớn thường đáng tin hơn giá đi kèm volume nhỏ.",
    },
    "support_resistance": {
        "name": "Hỗ trợ & Kháng cự (Support / Resistance)",
        "keywords": ["hỗ trợ", "kháng cự", "support", "resistance", "ngưỡng"],
        "definition": (
            "Các mức giá mà giá có xu hướng dừng giảm (hỗ trợ) hoặc dừng tăng "
            "(kháng cự) do tâm lý đám đông."
        ),
        "explanation": "Là công cụ phân tích kỹ thuật, không phải quy tắc đảm bảo giá sẽ phản ứng.",
    },
    "market_order": {
        "name": "Lệnh thị trường (Market Order)",
        "keywords": ["market order", "lệnh thị trường", "lệnh market", "mua giá thị trường"],
        "definition": (
            "Lệnh mua/bán ngay với giá hiện hành — đảm bảo khớp nhưng chịu trượt "
            "giá (slippage)."
        ),
        "explanation": (
            "Phù hợp khi cần vào/thoát nhanh, chấp nhận giá thực tế có thể kém hơn "
            "giá hiển thị."
        ),
    },
    "limit_order": {
        "name": "Lệnh giới hạn (Limit Order)",
        "keywords": ["limit order", "lệnh giới hạn", "lệnh limit", "giá giới hạn"],
        "definition": (
            "Lệnh chỉ khớp ở mức giá bằng hoặc tốt hơn mức bạn đặt — kiểm soát giá "
            "nhưng không đảm bảo khớp."
        ),
        "explanation": "Phù hợp khi bạn muốn kiểm soát giá vào lệnh, chấp nhận có thể không khớp.",
    },
    "fomo": {
        "name": "FOMO (Fear Of Missing Out)",
        "keywords": ["fomo", "sợ bỏ lỡ", "bỏ lỡ cơ hội"],
        "definition": "Cảm giác sợ bỏ lỡ cơ hội sinh lời khi thấy người khác ăn nên làm ra.",
        "explanation": (
            "FOMO thường khiến quyết định vội vàng, không theo kế hoạch — dễ mua "
            "đuổi đỉnh."
        ),
    },
    "diversification": {
        "name": "Đa dạng hoá (Diversification)",
        "keywords": ["đa dạng hoá", "đa dạng hóa", "diversification", "dàn trải"],
        "definition": "Phân bổ vốn vào nhiều tài sản/mã khác nhau để giảm rủi ro tập trung.",
        "explanation": (
            "Trải vốn giúp giảm biến động, nhưng không loại bỏ hoàn toàn rủi ro "
            "thị trường."
        ),
    },
    "compound_interest": {
        "name": "Lãi kép (Compound Interest)",
        "keywords": ["lãi kép", "compound interest", "lãi mẹ đẻ lãi con"],
        "definition": (
            "Lợi nhuận được tái đầu tư để sinh lợi nhuận mới — tăng trưởng theo "
            "cấp số nhân theo thời gian."
        ),
        "explanation": (
            "Thời gian là yếu tố quan trọng nhất của lãi kép — bắt đầu sớm thường "
            "giúp ích rất lớn."
        ),
    },
    "time_value": {
        "name": "Giá trị thời gian của tiền (Time Value of Money)",
        "keywords": ["giá trị thời gian của tiền", "time value of money", "tvom"],
        "definition": (
            "Nguyên tắc một đồng hôm nay có giá trị hơn một đồng trong tương lai do "
            "khả năng sinh lời."
        ),
        "explanation": "Nền tảng để so sánh dòng tiền ở các thời điểm khác nhau và hiểu lãi kép.",
    },
    "market_cap": {
        "name": "Vốn hoá thị trường (Market Cap)",
        "keywords": ["vốn hoá", "vốn hóa", "market cap", "marketcap", "giá trị vốn hóa"],
        "definition": (
            "Tổng giá trị thị trường của một công ty = giá cổ phiếu × số cổ phiếu "
            "lưu hành."
        ),
        "explanation": "Phân loại công ty lớn/nhỏ và mức độ biến động thường gặp.",
        "formula": "Market Cap = Giá × Số cổ phiếu lưu hành",
    },
    "dividend": {
        "name": "Cổ tức (Dividend)",
        "keywords": ["cổ tức", "dividend", "chia cổ tức"],
        "definition": "Phần lợi nhuận công ty trả cho cổ đông, thường bằng tiền mặt hoặc cổ phiếu.",
        "explanation": "Cổ tức là nguồn thu nhập; tỷ lệ cổ tức phụ thuộc chính sách công ty.",
        "formula": "Tỷ suất cổ tức = Cổ tức mỗi cổ / Giá",
    },
    "liquidity": {
        "name": "Thanh khoản (Liquidity)",
        "keywords": ["thanh khoản", "liquidity", "tính thanh khoản"],
        "definition": "Khả năng mua/bán một tài sản mà không làm thay đổi giá quá nhiều.",
        "explanation": (
            "Thanh khoản cao → khớp dễ, trượt giá thấp; thanh khoản thấp → "
            "vào/thoát khó hơn."
        ),
    },
    "trend": {
        "name": "Xu hướng (Trend)",
        "keywords": ["xu hướng", "trend", "xu the"],
        "definition": (
            "Hướng di chuyển chung của giá trong một khoảng thời gian (tăng, giảm, "
            "đi ngang)."
        ),
        "explanation": (
            "Nhận diện xu hướng giúp định vị quyết định, nhưng xu hướng có thể "
            "đảo chiều bất ngờ."
        ),
    },
    "slippage": {
        "name": "Trượt giá (Slippage)",
        "keywords": ["trượt giá", "slippage"],
        "definition": (
            "Chênh lệch giữa giá khớp thực tế và giá dự kiến, do thanh khoản hoặc "
            "tốc độ lệnh."
        ),
        "explanation": "Lệnh lớn hoặc thị trường kém thanh khoản dễ trượt nhiều hơn.",
    },
    "eps": {
        "name": "EPS (Earnings Per Share)",
        "keywords": ["eps", "lợi nhuận trên mỗi cổ phần", "earnings per share"],
        "definition": "Phần lợi nhuận ròng tương ứng với mỗi cổ phiếu.",
        "explanation": "Nền tảng cho nhiều chỉ số định giá như P/E.",
        "formula": "EPS = Lợi nhuận ròng / Số cổ phiếu",
    },
    "volatility": {
        "name": "Biến động (Volatility)",
        "keywords": ["biến động", "volatility", "độ biến động"],
        "definition": "Mức độ dao động giá của một tài sản theo thời gian.",
        "explanation": "Biến động cao → rủi ro cao nhưng cũng tiềm năng lợi nhuận lớn hơn.",
    },
}

# Mirror ai_engine/data/knowledge_base.yaml — nội dung tham chiếu ngắn gọn cho
# gateway deterministic. Đồng bộ bởi test_mentor_content_sync.
_CONCEPT_KEYWORDS: list[tuple[str, list[str]]] = [
    (key, entry["keywords"]) for key, entry in _CONCEPT_GLOSSARY.items()
]

# Cờ rủi ro deterministic cho Chế độ 3 (trade_now) — map focus thành câu hỏi.
_TRADE_RISK_BANK: dict[str, dict[str, Any]] = {
    "concentration": {
        "questions": [
            (
                "Tỷ trọng cổ phiếu này trong danh mục của bạn đang rất cao. Nếu nó "
                "giảm sâu, bạn sẵn sàng chịu mất bao nhiêu phần trăm tổng tài sản?"
            ),
            (
                "Bạn đã có kế hoạch giảm bớt vị thế khi tỷ trọng vượt quá một "
                "ngưỡng định trước chưa?"
            ),
        ],
        "coaching_tip": (
            "Tính tỷ trọng phần trăm của từng vị thế so với tổng NAV và thiết lập "
            "ngưỡng giới hạn cho riêng bạn."
        ),
    },
    "no_stop": {
        "questions": [
            (
                "Nếu giá cổ phiếu này đảo chiều giảm 10% ngay sau khi bạn giữ vị "
                "thế, bạn sẽ xử lý thế nào?"
            ),
            "Bạn đã xác định mức giá nào buộc phải thoát (ngưỡng chịu lỗ) chưa?",
        ],
        "coaching_tip": (
            "Xác định trước mức chịu lỗ tối đa và điều kiện thoát cho mỗi vị thế "
            "trước khi vào lệnh."
        ),
    },
    "all_cash_low": {
        "questions": [
            (
                "Bạn đã dành hầu hết vốn vào thị trường — còn lại rất ít tiền mặt. "
                "Bạn giữ lại khoản dự phòng nào cho cơ hội hoặc biến cố bất ngờ?"
            ),
            "Nếu cần tiền gấp mà mọi vị thế đều đang giảm, bạn làm gì?",
        ],
        "coaching_tip": (
            "Liệt kê khoản tiền mặt dự phòng của bạn và xét xem nó có đủ cho các "
            "tình huống bất ngờ không."
        ),
    },
    "fomo": {
        "questions": [
            (
                "Lợi nhuận của vị thế này đang rất cao — có phải bạn đang cố giữ "
                "thêm vì sợ bỏ lỡ nhịp tăng tiếp?"
            ),
            (
                "Bạn đã có kế hoạch chốt bớt lợi nhuận khi đạt một mức định trước "
                "chưa?"
            ),
        ],
        "coaching_tip": (
            "Tách cảm xúc khỏi con số: viết ra lý do ra vào lệnh dựa trên kế hoạch, "
            "không dựa trên đà giá."
        ),
    },
    "process": {
        "questions": [
            (
                "Trước khi đặt lệnh, bạn đã xác định giới hạn chịu lỗ và mục tiêu "
                "của quyết định này chưa?"
            ),
            (
                "Thông tin bạn đang dựa vào đến từ đâu, và độ tin cậy của nó được "
                "kiểm chứng thế nào?"
            ),
        ],
        "coaching_tip": (
            "Viết ra kế hoạch ra vào lệnh (mua ở đâu, thoát ở đâu, chịu lỗ bao nhiêu) "
            "trước khi hành động."
        ),
    },
}


def _lookup_concept(message: str) -> str | None:
    """Tìm khái niệm khớp với tin nhắn (deterministic, bỏ dấu)."""
    haystack = _normalize(message or "")
    best_key: str | None = None
    for key, keywords in _CONCEPT_KEYWORDS:
        for kw in keywords:
            if _normalize(kw) and _normalize(kw) in haystack:
                best_key = key
                break
        if best_key:
            break
    return best_key


def concept_reply_text(message: str) -> str | None:
    """Trả về văn bản giải thích khái niệm (0 token) hoặc None nếu không khớp."""
    key = _lookup_concept(message)
    if key is None:
        return None
    entry = _CONCEPT_GLOSSARY[key]
    lines = [
        f"**{entry['name']}**",
        entry["definition"],
    ]
    if entry.get("formula"):
        lines.append(f"Công thức: {entry['formula']}")
    lines.append(entry.get("explanation", ""))
    lines.append("")
    lines.append(
        "Bạn có hiểu cách áp dụng khái niệm này vào một tình huống cụ thể của mình không? "
        "Hãy thử mô tả quyết định bạn đang cân nhắc để cùng phản biện."
    )
    lines.append("")
    lines.append(_DISCLAIMER)
    return "\n".join(lines)


# ─── Framework bank Chế độ 2 (plan) — mirror deterministic, đồng bộ ai_engine
#     prompts/mentor_prompts.yaml `strategy_bank`. Nội dung KHÓA CỨNG (đã duyệt
#     pháp lý, docs v2.0 mục 4.2): mọi reply plan đều render từ đây, không thêm
#     ticker/giá mục tiêu/dự đoán thị trường. Sync bởi test_mentor_content_sync.
_STRATEGY_BANK: dict[str, dict[str, Any]] = {
    "value": {
        "name": "Value (Giá trị)",
        "objective": "Tăng trưởng bền vững nhờ cổ phiếu định giá thấp hơn giá trị nội tại.",
        "criteria": [
            "P/E thấp hơn trung bình ngành.",
            "ROE > 15% trong 3 năm gần nhất.",
            "Tỷ lệ nợ/vốn chủ nhỏ hơn 50%.",
        ],
        "allocation_rule": "Không quá 20% vốn vào mỗi cổ phiếu.",
        "risk_rule": "Xác định ngưỡng cắt lỗ trước khi vào lệnh.",
        "how_to_trade": [
            "Chọn doanh nghiệp có báo cáo tài chính minh bạch.",
            "Kiểm chứng định giá bằng so sánh cùng ngành.",
            "Đặt lệnh theo khối lượng xác định trước.",
        ],
        "questions": [
            "Bạn đã xác định khả năng chịu rủi ro của mình đến đâu chưa?",
            "Kế hoạch thoát khẩn cấp của bạn khi giá đi ngược kỳ vọng là gì?",
        ],
    },
    "growth": {
        "name": "Growth (Tăng trưởng)",
        "objective": "Ưu tiên tăng trưởng doanh thu và lợi nhuận nhanh.",
        "criteria": [
            "Tăng trưởng doanh thu > 15%/năm.",
            "ROE tăng đều qua các kỳ.",
            "Ngành có nhu cầu dài hạn.",
        ],
        "allocation_rule": "Không quá 25% vốn vào cổ phiếu tăng trưởng cao (biến động mạnh).",
        "risk_rule": "Giới hạn tối đa 10% thua lỗ mỗi vị thế.",
        "how_to_trade": [
            "Theo dõi báo cáo tài chính và tin tức doanh nghiệp.",
            "Thiết lập quy tắc chốt lời theo từng bậc khi giá tăng.",
            "Đa dạng hoá tối thiểu 5 mã.",
        ],
        "questions": [
            "Bạn sẵn sàng chấp nhận biến động lớn để đổi lấy tăng trưởng cao hơn chưa?",
            "Nếu giá cổ phiếu tăng 20% rồi đảo chiều, bạn làm gì?",
        ],
    },
    "income": {
        "name": "Income (Thu nhập/Cổ tức)",
        "objective": "Tạo thu nhập ổn định từ cổ tức.",
        "criteria": [
            "Tỷ suất cổ tức > 4%/năm.",
            "Lịch sử trả cổ tức đều > 5 năm.",
            "Dòng tiền hoạt động tích cực.",
        ],
        "allocation_rule": "Không quá 30% vốn vào một cổ phiếu trả cổ tức.",
        "risk_rule": "Nắm giữ tối thiểu 10 mã để giảm rủi ro cắt giảm cổ tức.",
        "how_to_trade": [
            "Chọn doanh nghiệp có chính sách cổ tức rõ ràng.",
            "Theo dõi lịch trả cổ tức hằng quý.",
        ],
        "questions": [
            "Thu nhập cổ tức có phải nguồn thu chính của bạn không, hay chỉ phụ thêm?",
            "Nếu doanh nghiệp cắt giảm cổ tức bất ngờ, bạn xử lý thế nào?",
        ],
    },
    "index": {
        "name": "Index/ETF (Theo dõi chỉ số)",
        "objective": "Bám theo thị trường chung với chi phí thấp, rủi ro phân tán.",
        "criteria": [
            "Nắm danh mục đa dạng nhiều ngành.",
            "Chi phí quản lý thấp.",
            "Phù hợp nhà đầu tư mới.",
        ],
        "allocation_rule": "Đa dạng hoá tối thiểu 10 mã hoặc ETF chỉ số.",
        "risk_rule": "Định kỳ tái cân bằng danh mục mỗi quý.",
        "how_to_trade": [
            "Chọn sản phẩm index phổ biến, thanh khoản cao.",
            "Không theo đuổi dự đoán ngắn hạn.",
        ],
        "questions": [
            "Bạn có kiên nhẫn giữ vị thế dài hạn khi thị trường điều chỉnh không?",
            "Kế hoạch đóng góp định kỳ của bạn là gì?",
        ],
    },
}

# Mirror ai_engine `_match_framework` (socratic_mentor.py:370) — giữ NGUYÊN thứ tự
# ưu tiên + nhánh "can slim"/"trend" rơi về growth trước default index.
_STRATEGY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("income", ["an toan", "roi ro thap", "thu nhap"]),
    ("growth", ["tang truong", "nhanh", "lai suat cao"]),
    ("index", ["danh muc", "phan theo doi"]),
    ("growth", ["can slim", "trend"]),
]


def _match_framework(text: str) -> str:
    """Chọn framework theo từ khoá mục tiêu (deterministic, 0 token)."""
    haystack = _normalize(text or "")
    for framework, keywords in _STRATEGY_KEYWORDS:
        if any(_normalize(kw) in haystack for kw in keywords):
            return framework
    return "index"


def strategy_reply_text(message: str, portfolio_text: str = "") -> str:
    """Render văn bản framework Chế độ 2 (plan) từ bank đã duyệt (0 token).

    Không bao giờ nêu ticker/giá mục tiêu/cảm tính — nội dung lấy nguyên từ
    ``_STRATEGY_BANK`` + disclaimer. ``portfolio_text`` từ snapshot (đã quét
    policy) chỉ dùng để match framework, KHÔNG đưa vào reply.
    """
    framework_id = _match_framework(f"{message} {portfolio_text}")
    entry = _STRATEGY_BANK[framework_id]
    lines = [
        f"**Framework phù hợp: {entry['name']}**",
        "",
        f"Mục tiêu: {entry['objective']}",
        "",
        "Tiêu chí:",
        *[f"- {c}" for c in entry["criteria"]],
        "",
        f"Phân bổ vốn: {entry['allocation_rule']}",
        f"Quản trị rủi ro: {entry['risk_rule']}",
        "",
        "Cách triển khai:",
        *[f"- {s}" for s in entry["how_to_trade"]],
        "",
        "Hãy tự phản biện:",
        *[f"- {q}" for q in entry["questions"]],
        "",
        _DISCLAIMER,
    ]
    return "\n".join(lines)


def trade_challenge_text(snapshot: Any) -> str:
    """Phản hồi phản biện lúc giao dịch dựa trên risk-flags from snapshot (0 token).

    ``snapshot`` là object có ``risk_flags``, ``selected_symbol``, ``current_price``,
    ``to_prompt_text()`` (TradeSnapshot). Trả về văn bản để stream.
    """
    flags = getattr(snapshot, "risk_flags", None) or []
    # Chọn focus ưu tiên theo thứ tự rủi ro nghiêm trọng.
    priority = ["concentration", "all_cash_low", "no_stop", "fomo", "process"]
    focus = next((f for f in priority if f in flags), "process")
    bank = _TRADE_RISK_BANK[focus]
    symbol = getattr(snapshot, "selected_symbol", None)
    company = symbol or ""
    questions = [
        q if not company else q.replace("cổ phiếu này", f"cổ phiếu {company}")
        for q in bank["questions"]
    ]
    lines = [
        *questions,
        "",
        f"Bài tập: {bank['coaching_tip']}",
        "",
        _DISCLAIMER,
    ]
    return "\n".join(lines)


class SocraticFocus(str, Enum):
    """Thiên kiến tâm lý mà lượt hỏi đang hướng tới."""

    FOMO = "fomo"
    HERDING = "herding"
    LOSS_AVERSION = "loss_aversion"
    OVERCONFIDENCE = "overconfidence"
    ANCHORING = "anchoring"
    CONFIRMATION_BIAS = "confirmation_bias"
    NOISE_TRADING = "noise_trading"
    PROCESS = "process"


@dataclass(frozen=True)
class SocraticReply:
    """Phản hồi Socratic deterministic — chỉ chứa câu hỏi phản biện."""

    focus: SocraticFocus
    questions: tuple[str, ...]
    coaching_tip: str
    disclaimer: str = _DISCLAIMER


def _normalize(text: str) -> str:
    """Bỏ dấu tiếng Việt + đ→d để bắt tin nhắn viết không dấu (đồng bộ A2.1)."""
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(ch)
    )
    return stripped.replace("đ", "d")


def detect_focus(text: str) -> SocraticFocus:
    """Phát hiện thiên kiến tâm lý theo keyword scoring + priority order.

    Chuẩn hoá bỏ dấu cả haystack lẫn keyword — nhất quán với agent ai_engine.
    """
    haystack = _normalize(text)
    scores = {
        focus: sum(1 for keyword in keywords if _normalize(keyword) in haystack)
        for focus, keywords in _DETECTION.items()
    }
    best_key = max(
        _PRIORITY_ORDER,
        key=lambda key: (scores.get(key, 0), -_PRIORITY_ORDER.index(key)),
    )
    if scores.get(best_key, 0) == 0:
        return SocraticFocus.PROCESS
    return SocraticFocus(best_key)


def _render(template: str, *, company: str) -> str:
    if company:
        return template.replace("{{company}}", company)
    return template


def socratic_reply(message: str, company: str = "") -> SocraticReply:
    """Soạn phản hồi Socratic deterministic cho tin nhắn (0 token Gemini)."""
    focus = detect_focus(message or "")
    bank = _QUESTION_BANK[focus.value]
    questions = tuple(
        _render(q, company=company) for q in bank["questions"]
    )
    coaching_tip = _render(bank["coaching_tip"], company=company)
    return SocraticReply(
        focus=focus,
        questions=questions,
        coaching_tip=coaching_tip,
    )


def reply_to_text(reply: SocraticReply) -> str:
    """Chuyển phản hồi có cấu trúc thành văn bản để stream chunk."""
    lines = [*reply.questions, "", f"Bài tập: {reply.coaching_tip}", "", reply.disclaimer]
    return "\n".join(lines)
