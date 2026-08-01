"""Tool demo Socratic Mentor — chạy thử đầu ra của Agent từ dòng lệnh.

Cách dùng (từ thư mục gốc repo):
    .venv\\Scripts\\python apps/ai_engine/tools/mentor_demo.py
    .venv\\Scripts\\python apps/ai_engine/tools/mentor_demo.py -m "Thấy ai cũng mua mã này, tôi sắp vào theo"
    .venv\\Scripts\\python apps/ai_engine/tools/mentor_demo.py -m "..." -c ACB --context "MXH sôi sục"

Khi chưa có GEMINI_API_KEY, Agent chạy fallback deterministic (0 token).
Khi có key trong .env, Agent gọi Gemini thật có ép JSON schema.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.socratic_mentor import MentorContext, SocraticMentorAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo Socratic Mentor")
    parser.add_argument("-m", "--message", default="", help="Tin nhắn người chơi")
    parser.add_argument("-c", "--company", default=None, help="Công ty đang thảo luận")
    parser.add_argument("--context", default="", help="Bối cảnh thị trường")
    parser.add_argument("--debug", action="store_true", help="Bật log debug")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    agent = SocraticMentorAgent()
    print(f"Gemini available: {agent.gemini.available}")
    print("─" * 60)

    message = args.message or input("Tin nhắn của bạn: ").strip()
    while message:
        ctx = MentorContext(company=args.company, market_context=args.context)
        reply = agent.generate(message, ctx)
        print(f"[focus: {reply.focus.value}]")
        for question in reply.questions:
            print(f"  ? {question}")
        print(f"  Bài tập: {reply.coaching_tip}")
        print(f"  Kiến thức: {', '.join(reply.concepts)}")
        print(f"  {reply.disclaimer}")
        print("─" * 60)
        try:
            message = input("Tin nhắn của bạn (Ctrl+C để thoát): ").strip()
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    main()
