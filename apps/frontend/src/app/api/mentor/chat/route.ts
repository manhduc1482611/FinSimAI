import { NextRequest, NextResponse } from "next/server";

const DISCLAIMER =
  "Capia là môi trường mô phỏng. Tôi không đưa ra lời khuyên mua bán — tôi chỉ giúp bạn phản biện quyết định của chính mình.";

const SYSTEM_INSTRUCTION = `Bạn là "Socratic Mentor" của Capia — nền tảng mô phỏng thị trường chứng khoán và tài chính dành cho người mới và nhà đầu tư.

PHƯƠNG CHÂM & VĂN PHONG:
- Thân thiện, tôn trọng, mang tính sư phạm và truyền cảm hứng tư duy độc lập.
- Sử dụng tiếng Việt chuẩn xác, mạch lạc, dễ hiểu, có bố cục gạch đầu dòng rõ ràng.

NGUYÊN TẮC CỐT LÕI (BẮT BUỘC):
1. TUYỆT ĐỐI KHÔNG đưa ra lời khuyên MUA/BÁN trực tiếp hay gián tiếp (cấm dùng: "nên mua", "nên bán", "hãy mua", "hãy bán", "múc", "bắt đáy", "thoát hàng", "giá mục tiêu", "tín hiệu mua").
2. TUYỆT ĐỐI KHÔNG phán xét quyết định đúng/sai tuyệt đối hay khẳng định tương lai giá ("chắc chắn tăng", "sẽ giảm").
3. Chào hỏi tự nhiên: Nếu người dùng chào hỏi (ví dụ: "alo", "hi", "xin chào", "bạn là ai"), hãy đáp lại thân thiện, giới thiệu bạn là Capia AI Mentor, và gợi mở các chủ đề họ có thể hỏi (giải thích thuật ngữ tài chính, gợi ý chiến lược đầu tư, hay phản biện một quyết định giao dịch).
4. Định hướng học đầu tư: Nếu người dùng muốn học đầu tư ("dạy tôi đầu tư", "bắt đầu từ đâu", "người mới nên làm gì"), hãy vạch ra lộ trình học 3 trụ cột cơ bản:
   - Trụ cột 1: Đọc hiểu báo cáo tài chính & doanh nghiệp (Doanh thu, Lợi nhuận, P/E, ROE).
   - Trụ cột 2: Quản trị rủi ro & phân bổ vốn (Kế hoạch cắt lỗ, không dồn trứng vào một giỏ).
   - Trụ cột 3: Kiểm soát tâm lý giao dịch (Tránh bẫy FOMO, bầy đàn).
   Sau đó đặt câu hỏi gợi ý để biết mục tiêu và thời gian rảnh của người học.
5. Giải thích thuật ngữ (Concept Mode): Cung cấp định nghĩa, công thức tính (nếu có), ví dụ thực tế và 1 câu hỏi phản biện Socratic.
6. Phản biện giao dịch (Trade Mode): Đặt 2-3 câu hỏi phản biện sắc bén về tỷ trọng vốn, điểm cắt lỗ, và lý do vào lệnh.
7. LUÔN kết thúc câu trả lời bằng tuyên bố miễn trừ:
"${DISCLAIMER}"`;

interface RequestPayload {
  message?: string;
  mode?: "concept" | "plan" | "trade_now" | "socratic";
  selectedSymbol?: string;
  history?: Array<{ role: string; content: string }>;
}

async function callGemini(
  apiKey: string,
  userPrompt: string,
  modelName = "gemini-3.5-flash-lite",
): Promise<string | null> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        systemInstruction: {
          parts: [{ text: SYSTEM_INSTRUCTION }],
        },
        contents: [
          {
            role: "user",
            parts: [{ text: userPrompt }],
          },
        ],
        generationConfig: {
          temperature: 0.3,
          maxOutputTokens: 1024,
        },
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      console.error(`[callGemini] HTTP ${res.status}:`, errBody);
      return null;
    }

    const data = await res.json();
    const candidate = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    return typeof candidate === "string" ? candidate.trim() : null;
  } catch (err) {
    console.error("[callGemini] Exception:", err);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as RequestPayload;
    const message = (body.message || "").trim();
    const mode = body.mode || "socratic";
    const selectedSymbol = body.selectedSymbol;

    if (!message) {
      return NextResponse.json(
        { error: "Tin nhắn không được để trống" },
        { status: 400 },
      );
    }

    const apiKey =
      process.env.GEMINI_API_KEY ||
      process.env.NEXT_PUBLIC_GEMINI_API_KEY ||
      "";

    console.log(
      "[POST /api/mentor/chat] message:",
      message,
      "apiKey exists:",
      Boolean(apiKey),
      "length:",
      apiKey.length,
    );

    let replyText: string | null = null;

    if (apiKey) {
      let contextNote = `Chế độ hiện tại: ${mode}.`;
      if (selectedSymbol) {
        contextNote += ` Cổ phiếu đang quan tâm: ${selectedSymbol}.`;
      }
      const prompt = `[Ngữ cảnh: ${contextNote}]\nNgười dùng hỏi: "${message}"`;

      // Ưu tiên gemini-3.5-flash-lite, fallback sang gemini-3.8-flash hoặc gemini-flash-latest
      replyText = await callGemini(apiKey, prompt, "gemini-3.5-flash-lite");
      if (!replyText) {
        replyText = await callGemini(apiKey, prompt, "gemini-3.8-flash");
      }
      if (!replyText) {
        replyText = await callGemini(apiKey, prompt, "gemini-flash-latest");
      }
    }

    if (replyText) {
      if (!replyText.includes("Capia là môi trường mô phỏng")) {
        replyText = `${replyText}\n\n${DISCLAIMER}`;
      }
      return NextResponse.json({
        role: "mentor",
        content: replyText,
        source: "gemini",
      });
    }

    // Nếu không có API Key hoặc Gemini tạm thời bận, chuyển sang fallback chất lượng cao
    return NextResponse.json({
      role: "mentor",
      content: generateFallback(message, mode, selectedSymbol),
      source: "fallback",
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Đã xảy ra lỗi khi xử lý tin nhắn" },
      { status: 500 },
    );
  }
}

function generateFallback(
  message: string,
  mode: string,
  selectedSymbol?: string,
): string {
  const lower = message.toLowerCase();

  // 1. Chào hỏi
  if (
    /^(alo|hi|hello|chào|xin chào|hey|hé lô)/i.test(lower) ||
    lower === "alo" ||
    lower === "hi"
  ) {
    return `Chào bạn! Tôi là Capia AI Mentor — trợ lý đồng hành giúp bạn rèn luyện tư duy và kỷ luật đầu tư chứng khoán theo phương pháp phản biện Socratic.

Hôm nay bạn đang muốn tìm hiểu về điều gì:
1. **Giải thích thuật ngữ**: Hỏi tôi về P/E, ROE, Net Margin, Cắt lỗ, Lãi kép, FOMO...
2. **Khung chiến lược**: Hỏi về chiến lược Tích sản (DCA), Đầu tư Tăng trưởng, hay Cổ tức.
3. **Phản biện giao dịch**: Đưa ra quyết định bạn đang dự định vào lệnh để chúng ta cùng mổ xẻ rủi ro.

Hãy nhắn cho tôi bất kỳ câu hỏi nào của bạn nhé!

${DISCLAIMER}`;
  }

  // 2. Yêu cầu dạy đầu tư
  if (
    /dạy.*đầu tư|học.*đầu tư|bắt đầu.*như thế nào|người mới.*làm gì|hướng dẫn.*đầu tư/i.test(
      lower,
    )
  ) {
    return `Chào mừng bạn bắt đầu hành trình tìm hiểu đầu tư tài chính! Để đi đường dài an toàn trên thị trường chứng khoán, Capia đề xuất bạn tiếp cận theo 3 trụ cột cốt lõi:

1. **Hiểu bản chất doanh nghiệp (Cơ bản)**:
   - Học cách đọc báo cáo tài chính đơn giản: Doanh thu, Lợi nhuận sau thuế, P/E, ROE.
   - Tránh mua cổ phiếu chỉ vì thấy người khác hô hào trên mạng xã hội.

2. **Quản trị rủi ro & Bảo toàn vốn (Sống còn)**:
   - Luôn xác định mức cắt lỗ trước khi mua (ví dụ: tối đa lỗ 7% là cắt).
   - Không bao giờ dồn toàn bộ vốn ("all-in") vào một cổ phiếu duy nhất.

3. **Kiểm soát tâm lý (Kỷ luật)**:
   - Nhận diện bẫy tâm lý FOMO (sợ bỏ lỡ cơ hội) và tâm lý gồng lỗ chờ về bờ.

**Câu hỏi dành cho bạn**: Bạn dự định đầu tư với số vốn nhàn rỗi trong bao lâu (dưới 6 tháng, 1 năm hay tích lũy dài hạn)?

${DISCLAIMER}`;
  }

  // 3. Trade / Cổ phiếu cụ thể
  if (mode === "trade_now" || /mua|bán|all-in|vào lệnh/i.test(lower)) {
    const sym = selectedSymbol || "mã này";
    return `Khi cân nhắc quyết định giao dịch với ${sym}, bạn hãy tự trả lời 3 câu hỏi phản biện sau:

1. **Tỷ trọng vốn**: Lệnh này chiếm bao nhiêu phần trăm tổng danh mục của bạn? Bạn có đang đặt cược quá 20% vào một mã duy nhất không?
2. **Kế hoạch cắt lỗ**: Nếu thị trường đi ngược kỳ vọng và giá giảm 5% – 7%, bạn có kế hoạch cắt lỗ tại mức giá nào?
3. **Luận điểm vào lệnh**: Bạn mua vì phân tích chỉ số kinh doanh thực tế hay vì thấy thị trường đang hưng phấn?

**Bài tập quy trình**: Hãy viết ra 3 kịch bản (tăng, đi ngang, giảm mạnh) và hành động tương ứng trước khi nhấn xác nhận đặt lệnh.

${DISCLAIMER}`;
  }

  // 4. Mặc định
  return `Tôi đã ghi nhận câu hỏi của bạn: "${message}".

Để cùng phản biện theo phương pháp Socratic, hãy thử xem xét:
- Mục tiêu và giả định chính của bạn khi đặt câu hỏi này là gì?
- Nguồn thông tin bạn dựa vào đã được kiểm chứng độc lập chưa?
- Nếu giả định của bạn ngược lại với thực tế, phương án dự phòng của bạn là gì?

Bạn có thể hỏi tôi về bất kỳ thuật ngữ tài chính nào (như P/E, ROE, Margin) hoặc chia sẻ kế hoạch đầu tư cụ thể để cùng thảo luận.

${DISCLAIMER}`;
}
