FROM python:3.12-slim

WORKDIR /app

# Copy source data
COPY "AI工具场景速查表.md" .

# Copy backend code and frontend
COPY backend/ backend/
COPY frontend/ frontend/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ENV LLM_API_BASE=https://coding.dashscope.aliyuncs.com/v1
ENV LLM_MODEL=qwen3.6-plus
# LLM_API_KEY should be passed at runtime via -e

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
