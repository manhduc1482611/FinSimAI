# FinSimAI — Kế hoạch nâng cấp AI Mentor (3 chế độ hoàn thiện)

> Ngày lập: 2026-09-07 · Phiên bản: **2.0** · Dựa trên rà soát codebase thực tế
> (`ai_engine`, `backend_gateway`, `frontend`, `packages/database`).
>
> **Lịch sử:** v1.0 → v2.0 cập nhật từ phản biện chuyên sâu về ranh giới pháp lý & bảo mật.
> Các thay đổi chính: (1) Chế độ 2 khóa cứng nội dung framework vào template đã duyệt, LLM chỉ
> tham số hóa + sinh câu hỏi — **không tự soạn khung**; (2) Backend **tự fetch lại** dữ liệu tài
> chính từ DB, không tin số liệu client; (3) đảo lộ trình triển khai **1 → 3 → 2**; (4) cụ thể
> hóa whitelist policy thành bảng pattern tường minh; (5) rate limit nâng lên P0/P1 + breakdown
> chi phí LLM theo mode; (6) bổ sung golden-set phân biệt nhầm lẫn giữa các mode; (7) versioning
> `metadata_json`.
>
> Mục tiêu: biến AI Mentor từ **1 chế độ phản biện thuần (Socratic)** thành **3 chế độ toàn
> diện** đáp ứng vòng đời học tập — hiểu khái niệm → lên kế hoạch → thực hành & sửa sai.

---

## 0. Tóm tắt điều hành

Hiện tại Mentor chỉ có **1 chế độ Socratic** lồng trong `/ws/mentor` với 5 lớp bảo vệ an
toàn. Người dùng cần 3 năng lực bổ sung:

| # | Chế độ | Bản chất hiện tại | Yêu cầu mới |
|---|--------|-------------------|-------------|
| 1 | **Hỏi đáp khái niệm** | Chỉ có glossary 10 thuật ngữ cho demo mode | Cơ sở tri thức đầy đủ + trả lời giải thích rõ ràng |
| 2 | **Đề xuất hướng đầu tư** | Bị **cấm tuyệt đối** (policy cấm mua/bán) | Đề xuất **khung chiến lược** (không phải "mua cổ X") — giải quyết mâu thuẫn ranh giới |
| 3 | **Phản biện lúc giao dịch** | Không nhận context danh mục, chỉ nhận text | Nhận ngữ cảnh giao dịch + phản biện đúng thời điểm |

**Nguyên tắc xuyên suốt:** giữ nguyên bản sắc *giáo dục, mô phỏng, không phán xét*. Mọi chế độ
đều chạy qua **5 lớp bảo vệ an toàn** hiện có; không một chế độ nào được đưa lời khuyên
mua/bán trực tiếp, không phán xét đúng/sai — thay vào đó chuyển thành **câu hỏi & khung tư duy**.

---

## 1. Hiện trạng hệ thống (điểm bắt đầu)

### 1.1 Kiến trúc 3 service

```
[Next.js Frontend] ──WS /ws/mentor──▶ [Backend Gateway (FastAPI)]
      │                                          │  REST /api/v1/mentor/history
      ▼                                          ▼
[useSocraticMentor + useMentorStore]   [AI Engine (FastAPI)] → Gemini
      │                                          │
      ▼                                          ▼
[knowledge_matcher.ts (10 thuật ngữ)]  [PostgreSQL mentor_messages]
```

### 1.2 Thành phần đã có

| Thành phần | File | Vai trò |
|---|---|---|
| Socratic Agent (5 lớp bảo vệ) | `apps/ai_engine/agents/socratic_mentor.py` | Brain chính |
| Prompt store v3.2.0 | `apps/ai_engine/prompts/mentor_prompts.yaml` | System prompt + question bank 8 focus |
| Policy scanner | `apps/ai_engine/agents/policy.py` | Lớp 3 — cấm mua/bán, đúng/sai |
| LLM-as-judge | `apps/ai_engine/agents/judge.py` | Lớp 4 |
| Grounding | `apps/ai_engine/agents/grounding.py` | Lớp 4.5 — chống bịa số liệu |
| Deterministic engine 0-token | `apps/backend_gateway/realtime/mentor_engine.py` | Fallback mặc định |
| WS streaming | `apps/backend_gateway/realtime/mentor_ws.py` | HybridMentorStream |
| History persistence | `apps/backend_gateway/services/mentor_history.py` + `models/mentor.py` | DB |
| Glossary demo (10 thuật ngữ) | `apps/frontend/src/utils/knowledge_matcher.ts` | Chỉ dùng demo mode |
| Chat UI | `apps/frontend/src/components/mentor/MentorChat.tsx` | Giao diện |
| Store + hook | `useMentorStore.ts`, `useSocraticMentor.ts` | Trạng thái chat |

### 1.3 Các giới hạn hiện hữu trực tiếp ảnh hưởng 3 chế độ

1. **Chế độ 1 chưa tồn tại ở backend**: `knowledge_matcher.ts` chỉ có 10 thuật ngữ, chỉ chạy
   ở demo mode phía client. Không có cơ sở tri thức trả về định nghĩa/giải thích đầy đủ.
2. **Chế độ 2 xung đột với policy**: policy cấm tuyệt đối mua/bán. Cần thiết kế lại để
   "đề xuất hướng đầu tư" = đề xuất *khung*, không phải *lệnh*.
3. **Chế độ 3 thiếu context**: WS payload chỉ `{action, message, session_id}` — mentor không
   biết người dùng đang nhìn/muốn giao dịch gì (`trade/page.tsx:189` nhúng `MentorChat` nhưng
   không truyền context). Nút "Hỏi Mentor" trên trade page là nút chết (`onClick={() => {}}`).

---

## 2. Thiết kế tổng thể — Kiến trúc "3 chế độ + 1 bộ não"

### 2.1 Bộ não dùng chung

Giữ nguyên `SocraticMentorAgent` làm **bộ não thống nhất**, thêm **router phân định chế độ**
(`MentorRouter`) ở tầng AI Engine. Router phân loại ý định người dùng trước khi sinh reply:

```
User input
   │
   ▼
MentorIntentClassifier (phân loại ý định)
   ├── "concept"    → Chế độ 1: Giải thích khái niệm
   ├── "plan"       → Chế độ 2: Đề xuất hướng đầu tư (khung chiến lược)
   ├── "trade_now"  → Chế độ 3: Phản biện lúc giao dịch (có context)
   └── "socratic"   → Chế độ hiện tại (mặc định, fallback an toàn)
```

**Cách phân loại ý định (ưu tiên độ tin cậy, tránh chọn nhầm):**
- **Lớp 1 — Quy tắc cứng (deterministic, 0 token):** pattern từ khoá tiếng Việt (không dấu).
  Đây là lớp *mặc định & an toàn nhất*.
  - `concept`: từ khoá như "là gì", "nghĩa là", "giải thích", "khái niệm", "def", "là sao",
    "định nghĩa", và tên thuật ngữ trong glossary (`P/E`, `ROE`, `FOMO`...).
  - `plan`: "nên đầu tư gì", "hướng đầu tư", "chiến lược", "phân bổ", "nên mua cổ phiếu nào",
    "danh mục", "kế hoạch đầu tư".
  - `trade_now`: từ khoá chỉ ý định giao dịch tức thời ("sắp mua", "đang muốn bán", "vừa đặt
    lệnh", "có nên chốt", "có nên cắt lỗ") — được điểm bởi cả context giao dịch từ payload.
  - `socratic`: mọi trường hợp còn lại (mặc định).
- **Lớp 2 — LLM intent classifier (khi `MENTOR_LLM_MODE=on`):** nếu quy tắc cứng trả về độ tin
  cậy thấp (không khớp), gọi Gemini phân loại nhẹ ~1 lần, trả về `{mode, confidence, reason}`.
- **Lớp 3 — Fallback:** độ tin cậy thấp + LLM không sẵn sàng → mặc định `socratic` (an toàn nhất).

**Tiêu chí chấp nhận (AC) — hai nhóm bắt buộc:**

*Nhóm A — nhận diện từng mode riêng lẻ:* ≥95% câu khái niệm rõ ràng (có "là gì"/tên thuật ngữ)
→ `concept`; ≥90% câu chiến lược điển hình → `plan`; ≥90% câu giao dịch tức thời (có context)
→ `trade_now`.

*Nhóm B — phân biệt giữa các mode gần nhau (mới, bắt buộc):* đây là ranh giới rủi ro nhất, vì
câu hỏi mua/bán (bị cấm tuyệt đối), `plan` và `trade_now` đều có thể chứa "nên"/"mua"/"đầu tư".
Cần golden-set riêng (mục 4.5) kiểm tra từng cặp ranh giới:
- `plan` vs câu hỏi mua/bán bị cấm: "nên đầu tư gì" (plan) vs "nên mua cổ X không" (❌ cấm /
  quy về `socratic` phản biện). **Không được** để câu hỏi mua/bán cụ thể lọt vào `plan` (nơi
  sẽ sinh khung chiến lược).
- `plan` vs `trade_now`: "hướng đầu tư dài hạn" (plan) vs "sắp mua cổ X 1000 cổ" (trade_now).
- `concept` vs `plan`: "khái niệm đa dạng hoá là gì" (concept) vs "nên đa dạng hoá thế nào" (plan).
- Mọi trường hợp mơ hồ → fallback `socratic` (an toàn nhất).

### 2.2 5 lớp bảo vệ an toàn — áp dụng **tăng dần** theo chế độ

| Lớp | Cơ chế | Chế độ 1 (concept) | Chế độ 2 (plan) | Chế độ 3 (trade_now) |
|---|---|---|---|---|
| 1 | Prompt policy | ✅ áp | ✅ áp (thêm khung) | ✅ áp (thêm khung) |
| 2 | Pydantic schema | ✅ | ✅ | ✅ |
| 3 | Policy scanner | ✅ | ✅ (whitelist tường minh, mục bên dưới) | ✅ (whitelist tường minh) |
| 4 | LLM-as-judge | ✅ | ✅ | ✅ |
| 5 | Fallback deterministic | ✅ | ✅ | ✅ |

> Chế độ 2 & 3 **không** bỏ sinh khuyến nghị mua/bán (vẫn cấm). Điểm khác biệt: **không dựa
> vào scanner phát hiện *sau khi sinh***; thay vào đó **ngăn từ gốc** bằng (a) template framework
> đã được duyệt pháp lý và (b) whitelist pattern tường minh dưới đây.

**Whitelist pattern tường minh cho policy (mode 2 & 3) — thay cho cụm "nới có kiểm soát" mơ hồ:**

Quy tắc: một câu nhắc tới "mua/bán/gom/xả/chốt" **chỉ được phép** nếu thuộc đúng một trong các
pattern trắng sau, và **không có tân ngữ cụ thể** (không có mã/ticker/giá/ngày):

| # | Whitelist pattern (đã chuẩn hoá không dấu) | Ví dụ cho phép | Loại trừ (cấm) |
|---|---|---|---|
| W1 | Câu **hỏi** kết thúc bằng "?", chứa từ mua/bán như **giả thuyết** | "Bạn đã chuẩn bị kịch bản khi giá đi ngược sau khi mua chưa?" | "Nên mua cổ X không" (có tân ngữ cụ thể) |
| W2 | Mô tả **quy trình chung** trong `how_to_trade`, không nêu mã | "Xác định ngưỡng cắt lỗ trước khi vào lệnh" | "Cắt lỗ khi X giảm xuống 30" (có mã/giá) |
| W3 | Rule **tổng quát** "không quá x% một mã" | "Giới hạn tối đa 20% vốn một cổ phiếu" | "Đổ 20% vào cổ X ngay" (điều khiển cụ thể) |
| W4 | Tiêu chí **định lượng chung** (PE < x, ROE > y%) | "Chọn mã có ROE > 15%" | "Mua ABC vì ROE 18%" (chỉ điểm mã) |

Mọi câu **không** khớp whitelist trên mà vẫn chứa từ mua/bán/gom/xả/chốt/kèo/giải ngân →
vẫn bị `scan_policy` chặn như cũ (không nới). Mỗi pattern có test riêng (mục 4.5).

**Versioning `metadata_json` (mới, bắt buộc):**
`metadata_json` lưu trade_context tóm lược cho mục đích audit (regulator có thể yêu cầu xem lại
"vì sao Mentor hỏi câu X") → **phải có schema version rõ ràng ngay từ đầu**, không phải JSON thuần
tự do. Định nghĩa Pydantic model `MentorMetadata` ngay ở Giai đoạn 1:

```python
class MentorMetadata(BaseModel):
    schema_version: Literal[1]      # bắt buộc — bump khi thay đổi cấu trúc
    mode: Literal["concept", "plan", "trade_now", "socratic"]
    prompt_version: str             # "kb-1.0", "framework-2.0", "qbank-3.1.0"...
    model: str | None               # "gemini-2.5-flash" hoặc "deterministic"
    focus: str | None               # focus socratic nếu mode=socratic
    trade_snapshot: TradeSnapshot | None  # tóm lược portfolio/cash/orders đã dùng (không token nhạy cảm)
    used_layers: list[str]          # danh sách lớp bảo vệ đã kích hoạt
```

Migration lưu `metadata_json` tuân thủ model này; nếu decode thất bại vì version cũ → audit tool
báo rõ, không im lặng bỏ qua.

---

## 3. Kế hoạch chi tiết theo từng chế độ

---

## CHẾ ĐỘ 1 — Hỏi đáp khái niệm (Learning Mode)

### 3.1 Mục tiêu

Khi người dùng hỏi về khái niệm tài chính, Mentor **giải thích rõ ràng bằng tiếng Việt**,
kèm ví dụ trực quan, và (quan trọng) luôn kết thúc bằng **1 câu hỏi phản biện** để nối vào
triết lý Socratic.

### 3.2 Giải pháp

Xây **cơ sở tri thức có cấu trúc** (Concept Knowledge Base) thay cho glossary 10 thuật ngữ
cũ. Mỗi khái niệm lưu dạng schema chuẩn:

```yaml
concept_pe:
  id: pe
  name: "P/E (Price-to-Earnings)"
  keywords: ["P/E", "P E", "gia tren loi nhuan", "price earnings", "he so PE"]
  definition: "Tỷ lệ giá cổ phiếu chia cho lợi nhuận trên mỗi cổ phần (EPS)..."
  explanation: "Giải thích dễ hiểu cho người mới, ngắn 2-3 câu."
  example: "Nếu cổ phiếu giá 100, EPS là 10, thì P/E = 10..."
  formula: "P/E = Giá / EPS"
  interpretation: "P/E cao/ thấp nghĩa là gì — không phán xét tốt/xấu tuyệt đối."
  related: ["EPS", "Net Margin", "ROE"]
  difficulty: 1      # 1 dễ → 3 nâng cao
  category: "định giá"  # thuộc nhóm để tra cứu nhanh
```

**3.2.1 Kho dữ liệu tri thức** — `apps/ai_engine/data/knowledge_base.yaml`
- Bắt đầu với **25–30 khái niệm cốt lõi** (nâng từ 10 hiện tại): FOMO, P/E, ROE, EPS, Net
  Margin, Cut Loss, Risk, Volume, Support/Resistance, Market/Limit Order, **thêm:** đa dạng
  hoá, lãi kép, giá trị thời gian của tiền, rủi ro hệ thống vs phi hệ thống, alpha/beta,
  vốn hoá thị trường, cổ tức, spread, thanh khoản, xu hướng, trung bình động, volatility...
- Cấu trúc theo schema chuẩn (định nghĩa + giải thích + ví dụ + công thức + diễn giải + liên
  quan + độ khó + nhóm).
- Load bằng `prompts/loader.py` (tận dụng infra YAML render sẵn có).

**3.2.2 Trả lời khái niệm** — schema `ConceptReply` mới trong `socratic_mentor.py`
```python
class ConceptReply(BaseModel):
    concept: str            # tên khái niệm được hỏi
    definition: str         # định nghĩa ngắn gọn
    explanation: str        # giải thích dễ hiểu 2-4 câu
    example: str            # ví dụ số học trực quan
    formula: str | None     # công thức (nếu có)
    interpretation: str     # diễn giải — KHÔNG phán xét tốt/xấu
    related: list[str]      # 1-3 khái niệm liên quan
    followup_question: str  # 1 câu hỏi phản biện Socratic để nối tiếp
    disclaimer: str = ""
```
- `followup_question` là **điểm khác biệt** so với giáo trình thường: mọi câu trả lời vẫn đưa
  người dùng về tư duy phản biện, giữ nguyên bản sắc Socratic.

**3.2.3 Nguồn dữ liệu (ưu tiên từ cao xuống thấp)**
1. **Deterministic glossary lookup (0 token):** câu hỏi khớp `keywords` → render thẳng
   `ConceptReply` từ YAML. Đây là đường dẫn mặc định — nhanh, miễn phí, chính xác 100%.
2. **LLM mở rộng** (khi `MENTOR_LLM_MODE=on`): nếu không khớp glossary, Gemini sinh `ConceptReply`
   theo 5 lớp bảo vệ; `concepts` bị grounding bắt buộc các con số phải xuất hiện trong context.
3. **Fallback "không biết":** nếu cả 2 thất bại, trả về câu hỏi Socratic `process` và gợi ý
   thuật ngữ gần nhất — **không được bịa định nghĩa** (A2.3 grounding).

**3.2.4 Frontend — hiển thị cấu trúc**
- Thêm type `ConceptReply` vào `apps/frontend/src/types/websocket.ts`.
- `MentorChat` nhận message loại `concept` → render **card khái niệm** (kèm công thức,
  ví dụ, khái niệm liên quan dạng chip) thay vì chỉ text.
- Các thuật ngữ trong `related` hiển thị chip nhấn được → hỏi tiếp (auto-fill).
- Nâng cấp `knowledge_matcher.ts` glossary lên đúng 25-30 thuật ngữ đồng bộ với YAML (dùng
  cho demo mode + suggest chips khi gõ).

### 3.3 Luồng xử lý
```
User: "P/E là gì?"
   │
   ▼
MentorRouter → IntentClassifier → mode = "concept"
   │
   ├── Deterministic: glossary lookup "P/E" khớp
   │       → render ConceptReply (0 token)
   └── (nếu không khớp + LLM on) → Gemini sinh ConceptReply (5 lớp)
   ▼
reply_to_text(co thành text) hoặc trả object ConceptReply qua WS (type "mentor_concept")
   ▼
Frontend render card khái niệm + followup_question
   ▼
save_exchange (role mentor, focus=NULL?id, prompt_version="kb-1.0")
```

### 3.4 Tiêu chí chấp nhận (AC)
- ✅ 25–30 khái niệm có đầy đủ schema (definition, explanation, example, formula, related,
  interpretation, difficulty, category) trong `knowledge_base.yaml`.
- ✅ Hỏi bất kỳ thuật ngữ nào trong kho → trả về `ConceptReply` đúng, có `followup_question`.
- ✅ Câu trả lời **không chứa** khuyến nghị mua/bán (policy scanner passing).
- ✅ Thuật ngữ không có trong kho + LLM off → fallback Socratic + gợi ý thuật ngữ gần nhất,
  **không bịa**.
- ✅ Có test: ≥10 khái niệm tiêu biểu, gồm định nghĩa không dấu & có dấu.
- ✅ Các chip "khái niệm liên quan" nhấn được để hỏi tiếp (auto-fill).

---

## CHẾ ĐỘ 2 — Đề xuất hướng đầu tư (Strategy Mode)

> ⚠️ **Đây là chế độ nhạy cảm nhất về ranh giới pháp lý/đạo đức.** FinSimAI là môi trường
> mô phỏng, nhưng phải giữ nguyên tắc: **đề xuất KHUNG, không đề xuất LỆNH.**

### 4.1 Mục tiêu

Người dùng muốn AI gợi ý "hướng đầu tư" — nhưng thay vì "mua cổ X", AI:
- Trả về **khung chiến lược có thể kiểm chứng** (tiêu chí lựa chọn, cách đánh giá rủi ro,
  quy tắc phân bổ vốn, cách xây dựng giả thuyết).
- Kèm **câu hỏi phản biện** theo tình huống cụ thể của người dùng.
- Luôn đính kèm disclaimer mô phỏng.

### 4.2 Giải pháp — khái niệm "Strategy Framework" thay cho "Tip"

Định nghĩa lại ngữ nghĩa: *"đề xuất hướng đầu tư"* = **đề xuất một framework** chứa đựng
các *điều kiện* để người dùng tự đưa ra quyết định, không phải *mệnh lệnh mua/bán*.

Schema `StrategyReply` mới:
```python
class StrategyReply(BaseModel):
    framework_name: str                 # tên khung chiến lược (vd "CANSLIM", "Value", "Trend-following")
    objective: str                      # mục tiêu của khung (tăng trưởng, giá trị, thu nhập...)
    criteria: list[str]                 # 2-4 tiêu chí có thể định lượng để chọn cổ phiếu
    allocation_rule: str                # quy tắc phân bổ vốn (vd "không quá x% 1 mã")
    risk_rule: str                      # quy tắc quản trị rủi ro (vd "cắt lỗ khi giảm y%")
    how_to_trade: list[str]             # các bước thực hiện KHÔNG nêu mã/ticker cụ thể
    questions: list[str]                # 1-3 câu hỏi phản biện để người dùng tự phản biện
    disclaimer: str = "Capia là môi trường mô phỏng..."
```

**Ranh giới rõ ràng (critical):**
- ✅ Được phép: nêu **tiêu chí định lượng chung** ("PE < x lần", "ROE > y%", "tăng trưởng
  doanh thu > z%"), **quy tắc** ("đa dạng hoá tối thiểu 5 mã", "cắt lỗ dưới 8%").
- ❌ Cấm: nêu **ticker/cổ phiếu cụ thể**, **giá mục tiêu cụ thể**, **thời điểm mua/bán cụ thể**,
  **dự đoán thị trường** ("thị trường sẽ tăng").

**4.2.1 Xử lý policy scanner** (`agents/policy.py`)
- Áp dụng **whitelist pattern tường minh** (mục 2.2, bảng W1–W4) cho mode `plan`.
- Thêm pattern cấm mới riêng cho chế độ plan: cấm "tôi khuyên bạn mua X", "giá mục tiêu",
  "sẽ tăng/sẽ giảm".
- Bổ sung golden-set test cho phạm vi plan (≥10 case hợp lệ + ≥10 case lách luật bị chặn).

**4.2.2 Kiến trúc khóa cứng nội dung (thay cho LLM tự soạn) — quyết định thiết kế then chốt**

> ⚠️ **Thay đổi lớn so với v1.0:** *không* để LLM tự soạn câu chữ cho
> `criteria/allocation_rule/risk_rule/how_to_trade`. LLM sinh văn bản tự do + chặn *sau* bằng
> scanner/judge có tỷ lệ false-negative không bao giờ về 0 — không đủ an toàn ở production.
> Thay vào đó:

1. **Framework bank = nguồn chân lý duy nhất** (đã duyệt pháp lý) trong `mentor_prompts.yaml`,
   5-8 framework (Value, Growth, CANSLIM, Trend-following, Income/Dividend, Index/ETF,
   Risk-parity). Mỗi framework có `criteria`, `allocation_rule`, `risk_rule`, `how_to_trade`
   **viết cố định, đã được phê duyệt** — không thay đổi theo từng user.
2. **LLM chỉ đóng 2 vai trò phạm vi hẹp, rủi ro thấp:**
   - **Chọn framework** phù hợp nhất (từ public enum đóng trong bank) dựa trên `risk_profile`,
     `horizon`, `experience` của user.
   - **Sinh `questions` phản biện** (1-3 câu) — phần này được phép tự do vì chỉ là câu hỏi,
     không phải khuyến nghị.
3. **Tham số hóa có giới hạn:** LLM có thể *điền giá trị số* vào placeholder của rule
   (vd `<MAX_ALLOC_PCT>`) **chỉ trong khoảng hợp lệ đã định nghĩa** (`min..max`), validate bằng
   Pydantic `field_validator` chặn ngoài khoảng → không tạo câu chữ mới.
4. **BẰNG matrix:** `policy` quét *toàn bộ output*; nếu mode `plan` mà có field nằm ngoài bank
   (không phải 1 trong các framework đã duyệt) → **reject & fallback deterministic ngay**, không
   phụ thuộc judge.

**4.2.2b Nguồn dữ liệu (đã đổi)**
1. **Đường deterministic (0 token, mặc định):** match từ khoá mục tiêu ("sinh lời nhanh" →
   Growth, "an toàn" → Income/Index...) → render thẳng `StrategyReply` từ bank.
2. **Đường LLM tham số hóa (khi `MENTOR_LLM_MODE=on`):** LLM chọn framework enum + sinh câu hỏi
   + điền tham số trong khoảng hợp lệ; output validate lại với bank → không khớp thì fallback
   deterministic.
3. **Fallback:** không có framework phù hợp hoặc LLM vi phạm → trả lại `StrategyReply` từ
   framework mặc định (Index/ETF an toàn nhất) + câu hỏi phản biện.

**4.2.3 Cần context đầu vào**
- Thêm vào `MentorContext`: `risk_profile` (thấp/vừa/cao), `investment_horizon`
  (ngắn/trung/dài), `experience` (mới/trung bình/nâng cao), `capital_scale`.
- Frontend: khi user chọn chế độ "Đề xuất hướng đầu tư", hiển thị **modal mini-form** hỏi
  3 câu (mục tiêu, thời gian, mức rủi ro) trước khi gửi → giúp LLM chỉ *chọn* framework đúng
  (không tự bịa khung).

### 4.3 Luồng xử lý
```
User chọn tab/mode "Đề xuất hướng đầu tư" → điền risk/khung time → gửi
   │
   ▼
MentorRouter → mode = "plan" (kèm context risk_profile,...)
   │
   ├── Deterministic: match framework bank → render StrategyReply (0 token)
   └── (LLM on) → Gemini CHỈ chọn framework enum + sinh questions + điền tham số trong khoảng hợp lệ
        │         → validate output khớp bank (bảng matrix) → lệch thì fallback deterministic
        ▼
reply → WS type "mentor_strategy"
   ▼
Frontend render card khung chiến lược (criteria chips, allocation, risk, questions)
   ▼
save_exchange (focus=NULL, prompt_version="framework-2.0")
```

### 4.4 Tiêu chí chấp nhận (AC)
- ✅ Có ≥5 framework trong bank, mỗi khung đủ `criteria/allocation_rule/risk_rule/how_to_trade`
  **viết cố định, đã duyệt pháp lý** — nội dung khung KHÔNG đổi theo từng user.
- ✅ Mọi `StrategyReply` đều có `disclaimer` và ít nhất 1 `question` phản biện.
- ✅ **Không một reply nào chứa ticker cụ thể, giá mục tiêu, hay dự đoán thị trường** — do
  *kiến trúc khóa cứng* (không do judge), kiểm chứng bằng đoạn test assert output khớp bank.
- ✅ **LLM không thể sinh câu chữ khung chiến lược mới**: test đưa prompt cố tình lách → output
  nằm ngoài bank → bị reject & fallback deterministic.
- ✅ Tham số LLM điền luôn nằm trong khoảng hợp lệ (validate bằng `field_validator`).
- ✅ Người dùng điền risk/khung time → framework được *chọn* đúng (test 5 tình huống).
- ✅ Golden-set plan: ≥10 hợp lệ + ≥10 bị chặn + ≥10 cố lách → tất cả bị chặn, chạy trong CI.
- ✅ UI có cơ chế hỏi mục tiêu/rủi ro trước khi generate.

---

## CHẾ ĐỘ 3 — Phản biện lúc giao dịch (Real-time Guard)

> Đây là "sai đâu đắp đấy": mentor nhận **ngữ cảnh giao dịch thực tế** của người dùng ngay
> khi họ đang thao tác, phản biện kịp thời trước/sau/trong lúc đặt lệnh.

### 5.1 Mục tiêu

Loại bỏ giới hạn "mentor không biết người dùng đang làm gì" — gắn mentor trực tiếp vào Page
Trade để người dùng hỏi: *"Sắp mua cổ X 1000 cổ, khổng?"* và mentor trả lời dựa trên **portfolio
thật, giá hiện tại, lệnh đang chờ, lịch sử giao dịch** của chính user đó.

### 5.2 Hiện trạng vấn đề
- `trade/page.tsx:189` nhúng `<MentorChat/>` nhưng **không truyền context**.
- Nút "Hỏi Mentor" (`trade/page.tsx:79`) là **nút chết** `onClick={() => {}}`.
- WS payload chỉ `{action, message, session_id}`.

### 5.3 Giải pháp

**5.3.1 Payload WS — client CHỈ gửi dữ liệu server không có sẵn**

> ⚠️ **Thay đổi lớn so với v1.0:** client **KHÔNG gửi số liệu tài chính** (portfolio, cash,
> orders, giá, PNL, tỷ trọng). Đây là dữ liệu nhạy cảm; nếu tin client, client có thể gửi giả
> để "lừa" mentor. Backend **tự fetch lại từ DB bằng `user_id`** (từ JWT). `trade_context` từ
> client chỉ mang **`selected_symbol` + `message`** — những thứ server không biết tại thời điểm
> gõ.

```ts
{
  action: "ask",
  message: "Sắp mua cổ X 1000 cổ, được không?",
  session_id,
  trade_context: {
    mode: "trade_now",          // flag chế độ 3 (do client chỉ định khi ở Page Trade)
    selected_symbol: "X"        // ĐÂY là dữ liệu duy nhất client gửi (server không tự biết)
    // KHÔNG gửi portfolio/cash/orders/giá/PNL — backend tự lấy
  }
}
```

**Kiến trúc backend (bắt buộc làm ở Giai đoạn 1, không để "note"):**

Tạo service `apps/backend_gateway/services/trade_snapshot.py` cung cấp API fetch dữ liệu tài
chính đáng tin cậy:

```python
class TradeSnapshotService:
    def get_snapshot(self, user_id: str, selected_symbol: str | None) -> TradeSnapshot:
        # Đọc trực tiếp từ DB bằng user_id (JWT đã xác thực)
        portfolio = self.repo.get_portfolio(user_id)        # tỷ trọng, PNL từ avg_price vs current
        cash       = self.repo.get_cash(user_id)            # tiền mặt khả dụng
        open_orders = self.repo.get_open_orders(user_id)    # lệnh đang chờ
        recent     = self.repo.get_recent_trades(user_id, limit=5)
        current    = self.price_provider.get(selected_symbol) if selected_symbol else None
        return TradeSnapshot(portfolio=portfolio, cash=cash, open_orders=open_orders,
                             recent=recent, selected_symbol=selected_symbol, current_price=current)
```

- **Nguồn chân lý = DB/biểu đồ giá server**, không phải payload client.
- `selected_symbol` từ client được kiểm tra: phải nằm trong danh sách cổ phiếu hợp lệ của hệ
  thống (chống gửi symbol giả).
- **Độ trễ:** snapshot là dữ liệu tĩnh tại thời điểm giao dịch (portfolio, cash) — fetch nhanh
  ~ms. Giá hiện tại lấy từ price provider cache (không gọi lại phí). Giới hạn chấp nhận
  < 200ms; nếu vượt → vẫn trả lời với dữ liệu snapshot cuối cùng + ghi log.
- **Khi lệch / fetch lỗi:** truy cập DB fail → ghi log lỗi, gửi `mentor_error` rõ ràng
  ("không đọc được dữ liệu danh mục"), **không** tự ý dùng payload client. Không có cơ chế
  "fallback về dữ liệu client".

**5.3.2 Backend — tiếp nhận & dùng trade snapshot**
- `mentor_ws.py`: sửa `_run_ask` — khi `mode == "trade_now"`, gọi `TradeSnapshotService.get_snapshot()`
  để lấy dữ liệu thật, xây `MentorContext(company=selected_symbol, portfolio=snapshot.portfolio,
  market_context=...)` rồi đưa vào prompt.
- `HybridMentorStream`: nếu `mode == "trade_now"` và LLM on → dùng prompt chuyên biệt
  "in-trade challenge" (trong `mentor_prompts.yaml`), grounding bắt buộc con số lấy từ
  **snapshot server** (không bịa giá/PNL).
- `MentorContext` hiện đã có `portfolio`, `market_context`, `company` — **tái sử dụng**, chỉ
  cần mở rộng để nhận cấu trúc portfolio đầy đủ.

**5.3.3 Deterministic fallback cho chế độ 3 (0 token)**
Xây thêm logic trong `mentor_engine.py`:
- Nhận `trade_context` → kiểm tra **cờ rủi ro nhanh**:
  - Tỷ trọng 1 mã > ngưỡng (vd >40%) → focus `concentration` → hỏi về đa dạng hoá.
  - Lệnh limit không có stop → focus `risk_mgmt` → hỏi về kịch bản giảm giá.
  - Lướt vốn toàn bộ tiền mặt → focus `allocation` → hỏi về dự phòng.
  - Mua đuổi khi PNL đã cao → focus `fomo`.
- Nếu không có cờ → vẫn dùng question bank socratic theo `message`.

**5.3.4 Frontend — UI lồng vào thao tác**
- **Fix nút chết** `trade/page.tsx:79`: nút "Hỏi Mentor" → scroll & focus vào `MentorChat` +
  chuyển mode `trade_now`, gắn `selected_symbol` đang chọn.
- **Chip context**: trong `MentorChat`, khi user đang chọn cổ X, hiển thị chip
  `"💡 Phản biện quyết định của tôi với cổ X"` → nhấn → gửi kèm `selected_symbol` (không gửi
  số liệu tài chính).
- **Nút "Phản biện thời điểm này"** cạnh nút Đặt Lệnh: pre-fill tin nhắn phản biện với
  `selected_symbol` lệnh đang định đặt.
- Render `StrategyReply`/phase-3 replies dạng card có highlight các con số rủi ro (backend trả
  `risk_flags` trong reply).

### 5.4 Luồng xử lý
```
User đang trên Page Trade, chọn cổ X, điền số lượng, nhấn "Phản biện" / gõ câu hỏi
   │
   ▼
sendAsk(msg, trade_context={mode:"trade_now", selected_symbol:"X"})
   │
   ▼
mentor_ws → mode="trade_now"
   │  └─ TradeSnapshotService.get_snapshot(user_id, "X")   ← fetch từ DB, không tin client
   │        → portfolio, cash, orders, recent, current_price
   ▼
MentorContext(portfolio=snapshot, ...)
   │
   ├── Deterministic: risk-flag scan → chọn focus phù hợp (0 token)
   └── (LLM on) → Gemini in-trade challenge + grounding từ snapshot server + judge
   ▼
reply → WS "mentor_challenge" (kèm risk flags phát hiện)
   ▼
Frontend render card + highlight con số → user cân nhắc trước khi đặt lệnh
```

### 5.5 Tiêu chí chấp nhận (AC)
- ✅ Backend có `TradeSnapshotService` **fetch lại từ DB** bằng `user_id` (JWT); client chỉ gửi
  `selected_symbol` + `message` — **không tin bất kỳ số liệu tài chính nào từ client**.
- ✅ `selected_symbol` được validate thuộc danh sách cổ phiếu hệ thống (chặn symbol giả).
- ✅ Nút "Hỏi Mentor" chết đã được fix & hoạt động.
- ✅ Khi user hỏi với context cổ X, mentor reply **có nhắc** tới X, giá, PNL, tỷ trọng (từ
  snapshot server) — không trả lời chung chung (test grounding).
- ✅ Deterministic: nhận diện ≥4 cờ rủi ro (concentration, no-stop, all-cash, fomo) và hỏi
  đúng focus.
- ✅ Fetch DB lỗi → `mentor_error` rõ ràng, không tự dùng payload client.
- ✅ Không bao giờ nói "nên mua/bán X" — vẫn là câu hỏi phản biện (judge passing).
- ✅ Có golden-set trade_now (≥10 case context thật từ snapshot).

---

## 4. Kế hoạch tích hợp — sửa đổi chi tiết theo tầng

### 4.1 AI Engine (`apps/ai_engine/`)
| File | Thay đổi |
|---|---|
| `prompts/mentor_prompts.yaml` v3.3.0 | Thêm `concept` prompt + `strategy` prompt + `trade_now` prompt; thêm framework bank; thêm glossary-driven instruction |
| `data/knowledge_base.yaml` (mới) | 25-30 khái niệm schema đầy đủ |
| `agents/socratic_mentor.py` | Thêm `ConceptReply`, `StrategyReply` models; thêm `generate_concept/strategy/challenge`; mở rộng `MentorContext` (risk_profile...); `StrategyReply` chỉ nhận framework enum + tham số hợp lệ (khóa cứng bank) |
| `agents/intent.py` (mới) | `MentorRouter` + `IntentClassifier` (pattern + LLM) |
| `agents/policy.py` | Whitelist tường minh W1-W4 cho plan/trade_now; pattern cấm chế độ plan; bảng matrix so khớp output với bank |
| `agents/judge.py` | Thêm rule check cho strategy/trade framework |
| `routers/mentor.py` | Nhận `mode` + `trade_snapshot` từ gateway; route theo mode |
| `main_ai.py` | Không đổi (router cũ) |

### 4.2 Backend Gateway (`apps/backend_gateway/`)
| File | Thay đổi |
|---|---|
| `realtime/mentor_ws.py` | Đọc `mode` + `selected_symbol`; xây `MentorContext` từ `TradeSnapshotService`; add promoter cho 3 mode |
| `services/trade_snapshot.py` (mới) | Fetch portfolio/cash/orders/recent/current **từ DB + price provider** by `user_id` — không tin client |
| `realtime/mentor_engine.py` | Thêm risk-flag scan cho trade_now; glossary lookup cho concept |
| `clients/mentor_client.py` | Chuyển `mode` + snapshot sang AI Engine |
| `services/mentor_history.py` | Lưu `mode`, `metadata_json` (theo `MentorMetadata` versioned) để audit |
| `models/mentor.py` + migration 0014 | Thêm cột `mode` (string), `metadata_json` (JSONB) |
| `api/v1/mentor_history.py` | Trả thêm `mode`, `metadata_json` nếu cần |

> Lưu ý migration: `packages/database/migrations/versions/` — tạo file mới tuần tự (0014) chứa
> `ALTER TABLE mentor_messages ADD COLUMN mode VARCHAR(16), ADD COLUMN metadata_json JSONB`.
> `metadata_json` tuân thủ Pydantic `MentorMetadata` versioned (mục 2.2).

### 4.3 Frontend (`apps/frontend/`)
| File | Thay đổi |
|---|---|
| `components/mentor/MentorChat.tsx` | Render 3 loại card (concept/strategy/challenge); chips suggestion theo mode; textarea/input responsive |
| `hooks/useSocraticMentor.ts` | `sendAsk(msg, opts)` nhận `{mode, selected_symbol}`; KHÔNG gửi số liệu tài chính client |
| `hooks/useWebSocket.ts` | Không đổi (generic) |
| `store/useMentorStore.ts` | Xử lý `mentor_concept/mentor_strategy/mentor_challenge` events |
| `types/websocket.ts` | Thêm `ConceptReply`, `StrategyReply`, `TradeContext`(chỉ mode+symbol), `MentorChallengeEvent` |
| `utils/knowledge_matcher.ts` | Nâng glossary lên 25-30 thuật ngữ (đồng bộ YAML) |
| `app/(dashboard)/trade/page.tsx` | **Fix nút chết**: scroll/focus MentorChat + chuyển mode; truyền `selected_symbol` |
| `components/trade/OrderEntry` | Thêm nút "Phản biện thời điểm này" |
| `app/(dashboard)/trade/mentor/page.tsx` | Thêm mode selector (Hỏi đáp / Đề xuất / Phản biện) |

### 4.4 Database (`packages/database/`)
| File | Thay đổi |
|---|---|
| Migration `0014_mentor_mode.py` | `ADD COLUMN mode`, `ADD COLUMN metadata_json` |

### 4.5 Tests (bổ sung)
| Test | Coverage |
|---|---|
| `test_intent_classifier.py` | Nhận diện từng mode ≥95% (concept/plan/trade_now/socratic) |
| `test_intent_confusion.py` (mới) | **Golden-set phân biệt nhầm lẫn giữa mode** (mục 2.1 Nhóm B): plan vs câu hỏi mua/bán cấm, plan vs trade_now, concept vs plan — đảm bảo câu mua/bán cụ thể KHÔNG rơi vào plan |
| `test_concept_reply.py` | 10+ khái niệm: định nghĩa đúng, followup question, không bịa |
| `test_strategy_reply.py` | Khung chiến lược khóa cứng: output khớp bank; test LLM cố lách → bị reject & fallback; không ticker/giá/dự đoán; golden-set 30 case |
| `test_policy_whitelist.py` (mới) | Whitelist W1-W4: mỗi pattern có test cho phép + test cấm (câu không khớp pattern mà chứa từ mua/bán → vẫn bị chặn) |
| `test_trade_snapshot.py` (mới) | `TradeSnapshotService` fetch từ DB đúng user_id; symbol giả bị chặn; DB lỗi → báo lỗi, không dùng payload client |
| `test_trade_challenge.py` | Context thật (snapshot server): nhắc symbol/giá/PNL/tỷ trọng; risk-flag 4 loại |
| `test_prompt_store.py` (mở rộng) | Số framework ≥5, concept bank ≥25 |
| `test_mentor_content_sync.py` (mở rộng) | glossary frontend ↔ YAML đồng bộ; framework bank ↔ engine đồng bộ |
| `test_metadata_schema.py` (mới) | `metadata_json` tuân thủ `MentorMetadata` versioned; decode version lỗi → báo rõ |

---

## 5. Lộ trình triển khai (đề xuất theo giai đoạn)

> Đánh số theo mức ưu tiên: **P0** = nền tảng/ranh giới pháp lý/chi phí & abuse · **P1** = trải
> nghiệm · **P2** = tinh chỉnh.
>
> **Thứ tự triển khai đã đảo: 1 → 3 → 2.** Lý do: Chế độ 3 (chỉ phản biện bằng câu hỏi trên
> dữ liệu thật, không sinh nội dung tư vấn mới) rủi ro thấp hơn nhiều Chế độ 2 (sinh khung
> chiến lược — rủi ro pháp lý cao nhất). Làm Chế độ 3 trước giảm rủi ro tiến độ; **Chế độ 2
> chỉ bắt đầu sau khi quyết định mục 7.1 được khoá** → tránh build xong mới biết stakeholder
> không duyệt hướng này.

### Giai đoạn 1 — Nền tảng chung (P0)
- [ ] **1.1** [P0] Mở rộng DB: migration 0014 (`mode`, `metadata_json`) + model update +
      Pydantic `MentorMetadata` versioned.
- [ ] **1.2** [P0] Mở rộng `mentor_ws.py` + `mentor_client.py` để nhận `mode` & `selected_symbol`.
- [ ] **1.3** [P0] `IntentClassifier` nền (lớp quy tắc cứng deterministic) trong `intent.py`.
- [ ] **1.4** [P0] Xây `TradeSnapshotService` fetch portfolio/cash/orders từ DB by `user_id`
      (nền cho Chế độ 3).
- [ ] **1.5** [P0] Mở rộng `policy.py` whitelist tường minh W1-W4 + pattern cấm chế độ plan.
- [ ] **1.6** [P0] **Per-user rate limit (10/min, 100/day)** cho WS mentor + cache phản hồi
      (nâng từ P2 lên P0 — kiểm soát chi phí & abuse, áp cho cả 3 mode).
- **AC cổng:** intent phân loại đúng ≥95% câu concept; policy W1-W4 có test riêng; migration
  chạy sạch; rate limit chặn spam; `TradeSnapshotService` trả đúng data từ DB.

### Giai đoạn 2 — Chế độ 1: Hỏi đáp khái niệm (P0/P1)
- [ ] **2.1** [P0] Xây `data/knowledge_base.yaml` 25-30 khái niệm + loader.
- [ ] **2.2** [P0] `ConceptReply` schema + deterministic glossary lookup (0 token).
- [ ] **2.3** [P1] LLM path sinh `ConceptReply` (khi không khớp glossary) + grounding.
- [ ] **2.4** [P1] Frontend: render card khái niệm + related chips + nâng glossary local.
- [ ] **2.5** [P1] Test `test_concept_reply.py`.
- **AC cổng:** hỏi khái niệm bất kỳ trong bank nhận card đầy đủ + followup question; không bịa.

### Giai đoạn 3 — Chế độ 3: Phản biện lúc giao dịch (P0/P1)  ← làm trước Chế độ 2
- [ ] **3.1** [P0] Fix nút "Hỏi Mentor" chết (`trade/page.tsx:79`) → scroll/focus + mode trade_now.
- [ ] **3.2** [P0] Frontend gửi `{mode, selected_symbol}`; backend gọi `TradeSnapshotService`
      lấy data thật từ DB (không tin client).
- [ ] **3.3** [P0] Deterministic risk-flag scan (concentration/no-stop/all-cash/fomo) trong
      `mentor_engine.py`.
- [ ] **3.4** [P1] LLM prompt in-trade challenge + grounding từ snapshot server + judge.
- [ ] **3.5** [P1] UI: nút "Phản biện thời điểm này" cạnh Đặt Lệnh + chip context + card challenge.
- [ ] **3.6** [P1] Tests: `test_trade_snapshot.py`, `test_trade_challenge.py`, golden-set (≥10).
- **AC cổng:** user hỏi với context cổ X → reply nhắc X/giá/PNL/tỷ trọng (từ DB); không "nên
  mua/bán X"; symbol giả bị chặn; fetch DB lỗi → báo, không dùng payload client.

### Giai đoạn 4 — Chế độ 2: Đề xuất hướng đầu tư (P0/P1)  ← sau khi khoá quyết định 7.1
> 🔐 **GATE:** Giai đoạn này chỉ bắt đầu sau khi stakeholder khoá quyết định **7.1**
> (ngữ nghĩa "khung chiến lược, không nêu mã").
- [ ] **4.1** [P0] Framework bank ≥5 (viết cố định, duyệt pháp lý) + `StrategyReply` schema
      + bảng matrix so khớp output với bank (khóa cứng).
- [ ] **4.2** [P0] Deterministic match framework (0 token) + whitelist W1-W4 cho plan.
- [ ] **4.3** [P1] LLM CHỈ chọn framework enum + sinh questions + điền tham số trong khoảng
      hợp lệ; ngoài khoảng → reject & fallback deterministic.
- [ ] **4.4** [P1] Frontend: modal hỏi mục tiêu/rủi ro + card strategy.
- [ ] **4.5** [P1] Tests: `test_strategy_reply.py`, `test_policy_whitelist.py`; golden-set 30 case
      (10 hợp lệ + 10 lách bị chặn + 10 cố lách bị reject).
- **AC cổng:** output luôn khớp bank; mọi reply plan có disclaimer + ít nhất 1 câu phản biện;
  không ticker/giá/dự đoán; LLM không thể sinh câu chữ khung mới.

### Giai đoạn 5 — Tinh chỉnh & telemetry (P1/P2)
- [ ] **5.1** [P1] Golden-set **phân biệt nhầm lẫn giữa mode** (`test_intent_confusion.py`) —
      chạy ngay khi có đủ 3 mode, đảm bảo câu mua/bán cụ thể không rơi vào plan.
- [ ] **5.2** [P2] Luân phiên câu hỏi trong bank (không lặp) — A4.2 cũ.
- [ ] **5.3** [P2] Telemetry: mode, latency, token, fallback rate, focus (A4.3 cũ).
- [ ] **5.4** [P2] Nâng cao: proactive daily strategy question theo hành vi user (A4.4 / G4).

### Chi phí LLM (ước tính theo từng mode — breakdown)
> Giả định: `gemini-2.5-flash`, 500 DAU, ~5 lượt/ngày/người, mixed deterministic/LLM. Con số
> *ước tính*, theo dõi thực tế bằng telemetry (5.3) sau khi đi vào vận hành.

| Mode | Deterministic mặc định | LLM chỉ khi | Ước lượng chi phí/ngày (khi bật LLM) |
|---|---|---|---|
| Socratic (hiện tại) | ✅ | `MENTOR_LLM_MODE=on` | ~$1-3 (input/1M token giá thấp) |
| Concept (1) | ✅ (glossary lookup) | khong khớp glossary | +$0.2-0.5 |
| Trade_now (3) | ✅ (risk-flag) | user lệnh cụ thể | +$0.3-0.8 |
| Plan (2) | ✅ (framework bank) | user chọn cá nhân hoá | +$0.3-0.8 (thấp nhất nhờ khóa cứng) |

- **Cap cứng:** rate limit user (10/min, 100/day — Giai đoạn 1.6) + global quota theo ngày;
  vượt → tự động chuyển tất cả mode về deterministic 0-token.
- **Khuyến nghị:** giữ `MENTOR_LLM_MODE=off` ở staging; bật `on` sau khi hoàn tất 4 giai đoạn
  đầu + đo telemetry thực tế 1 tuần.

---

## 6. Rủi ro & cách giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Chế độ 2 bị đẩy lên ranh giới "tư vấn đầu tư" → vi phạm pháp lý/quy định | 🔴 | **Ngăn từ gốc**: framework bank viết cố định đã duyệt pháp lý; LLM chỉ chọn enum + tham số trong khoảng hợp lệ, KHÔNG tự soạn khung; bảng matrix reject output ngoài bank; golden-set lách luật |
| `trade_context` là dữ liệu nhạy cảm; client gửi giả | 🔴 | Client chỉ gửi `selected_symbol`; backend `TradeSnapshotService` **fetch lại từ DB** by `user_id` (JWT); symbol giả bị validate; fetch lỗi → báo, không dùng payload client |
| Chi phí Gemini tăng khi thêm 3 path LLM | 🟡 | Deterministic mặc định & 0 token; rate limit user (P0) + global quota cap cứng; breakdown chi phí theo mode (mục 5); cache (A1.4) |
| Phân loại ý định sai — **quan trọng nhất là ranh giới plan vs câu hỏi mua/bán cụ thể** | 🟡 | Lớp quy tắc cứng ưu tiên; mơ hồ → fallback `socratic`; golden-set `test_intent_confusion.py` (B) đảm bảo câu mua/bán cụ thể không rơi vào plan |
| LLM tự sinh câu chữ khung mới (lách luật) | 🔴 | Kiến trúc khóa cứng bank + bảng matrix so khớp output → test cố tình lách đều bị reject & fallback |
| Schema mới nhiều field → drift YAML/engine | 🟡 | Mở rộng `test_mentor_content_sync.py` cho cả 3 mode |
| Migration làm hỏng dữ liệu cũ | 🟡 | `mode` nullable mặc định 'socratic' (không phá historical rows); test migration up/down; `metadata_json` versioned |
| Audit khó khi regulator hỏi "vì sao Mentor hỏi câu X" | 🟡 | `metadata_json` tuân thủ `MentorMetadata` versioned (mode, prompt_version, model, focus, trade_snapshot, used_layers) — decode lỗi version thì báo rõ |

---

## 7. Quyết định cần xác nhận

> **Quyết định 7.1 là GATE bắt buộc trước khi bắt đầu Giai đoạn 4 (Chế độ 2).**

1. **Chế độ 2 ngữ nghĩa (GATE)**: Có đồng ý "đề xuất hướng đầu tư" = ĐỀ XUẤT KHUNG CHIẾN LƯỢC
   (không nêu mã cụ thể, nội dung framework cố định đã duyệt, LLM không tự soạn khung) không?
   — Đây là giới hạn bắt buộc để giữ an toàn & hợp quy. **Chưa được xác nhận → chưa triển khai
   Chế độ 2; có thể làm các Giai đoạn 1-3 trước.**
2. **Bật LLM mặc định?**: Hiện `MENTOR_LLM_MODE=off`. Khuyến nghị giữ `off` đến khi hoàn tất 4
   giai đoạn đầu + đo telemetry 1 tuần (mục 5). Chi phí ~$1-5/ngày khi bật toàn bộ (có breakdown
   theo mode, mục 5).
3. **Phạm vi glossary**: 25-30 khái niệm đủ chưa, hay cần mở rộng theo nhóm
   (định giá/cơ bản/kỹ thuật/quản trị rủi ro)?
4. **Chế độ 3 phạm vi**: Chỉ phản biện ở Page Trade (khi đang chọn cổ), hay cũng muốn ở mọi
   nơi app (news, portfolio)?
5. **Ưu tiên triển khai**: Khuyến nghị **1 → 3 → 2** (chế độ 2 làm sau cùng vì rủi ro pháp lý
   cao nhất + phụ thuộc GATE 7.1). Xác nhận?

---

## 8. Tài liệu tham khảo & file liên quan

### Hiện tại
- `apps/ai_engine/agents/socratic_mentor.py` — brain & schema
- `apps/ai_engine/agents/policy.py` — lớp 3
- `apps/ai_engine/agents/judge.py` — lớp 4
- `apps/ai_engine/prompts/mentor_prompts.yaml` — prompt store v3.2.0
- `apps/ai_engine/integrations/gemini.py` — GPT client
- `apps/backend_gateway/realtime/mentor_ws.py` — WS streaming
- `apps/backend_gateway/realtime/mentor_engine.py` — deterministic engine
- `apps/backend_gateway/services/mentor_history.py` — persistence
- `apps/frontend/src/components/mentor/MentorChat.tsx` — chat UI
- `apps/frontend/src/hooks/useSocraticMentor.ts` — WS hook
- `apps/frontend/src/utils/knowledge_matcher.ts` — glossary demo
- `apps/frontend/src/app/(dashboard)/trade/page.tsx` — trade page (fix nút chết)
- `packages/database/migrations/versions/0008_mentor_messages.py` — bảng gốc
- `docs/improvement_plan.md` — roadmap cũ (A1-A5, G4)

### Cần tạo mới (theo kế hoạch)
- `apps/ai_engine/data/knowledge_base.yaml`
- `apps/ai_engine/agents/intent.py`
- `apps/backend_gateway/services/trade_snapshot.py`
- `apps/backend_gateway/services/mentor_metadata.py` (Pydantic `MentorMetadata` versioned)
- Migration `0014_mentor_mode.py` (`add mode`, `add metadata_json`)
- Tests mới (mục 4.5): `test_intent_confusion.py`, `test_policy_whitelist.py`,
  `test_trade_snapshot.py`, `test_metadata_schema.py` + nâng các test cũ

---

*Hết kế hoạch. Sẵn sàng triển khai theo từng giai đoạn sau khi xác nhận các quyết định ở mục 7.*
