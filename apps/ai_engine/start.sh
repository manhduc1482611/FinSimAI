#!/bin/sh
# FinSimAI AI Engine — khởi động đồng thời FastAPI web API + ARQ task worker
# trong một container (free tier Render chỉ hỗ trợ web services).
python -m main_ai &
python -m tasks.worker &
wait
