import os
import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = Path(__file__).parent.parent / "AI工具场景速查表.md"
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://coding.dashscope.aliyuncs.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-plus")

markdown_content = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global markdown_content
    markdown_content = DATA_FILE.read_text(encoding="utf-8")
    print(f"[startup] Loaded {len(markdown_content)} chars from {DATA_FILE.name}")
    yield


app = FastAPI(title="AI Tool Finder", lifespan=lifespan)

SYSTEM_PROMPT = (
    "你是一个 AI 工具场景检索助手。用户会描述一个工作场景、痛点或需求，"
    "你需要根据提供的《AI工具场景速查表》内容，为用户推荐最匹配的工具组合。\n\n"
    "请严格按照以下 JSON 格式返回结果（不要输出 JSON 之外的任何内容）：\n"
    "{\n"
    '  "scene_match": "匹配到的场景分类名称",\n'
    '  "pain_points": ["识别到的用户痛点1", "痛点2"],\n'
    '  "tools": [\n'
    "    {\n"
    '      "name": "工具名称",\n'
    '      "core_ability": "该工具的核心能力描述",\n'
    '      "why_recommended": "为什么推荐这个工具给用户的具体原因",\n'
    '      "match_score": 90\n'
    "    }\n"
    "  ],\n"
    '  "combination_advice": "关于这些工具如何组合使用的建议",\n'
    '  "extra_tips": ["额外的使用建议或注意事项1", "建议2"]\n'
    "}\n\n"
    "match_score 为 0-100 的匹配度分数。推荐 2-5 个工具。"
    "如果速查表中没有直接匹配的工具，也要尽力推荐最接近的选项，并说明局限性。"
)


@app.get("/")
async def index():
    html_file = Path(__file__).parent.parent / "frontend" / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": LLM_MODEL, "data_loaded": len(markdown_content) > 0}


@app.post("/api/query")
async def query(query: dict):
    user_input = query.get("query", "").strip()
    if not user_input:
        return {"error": "query is empty"}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n以下是速查表完整内容：\n\n" + markdown_content},
        {"role": "user", "content": user_input},
    ]

    async def event_stream():
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{LLM_API_BASE.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": messages,
                        "stream": True,
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"},
                    },
                ) as response:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            text = chunk.decode("utf-8")
                            for line in text.split("\n"):
                                if line.startswith("data: "):
                                    payload = line[6:]
                                    if payload.strip() == "[DONE]":
                                        continue
                                    try:
                                        data = json.loads(payload)
                                        delta = data["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield f"data: {json.dumps({'text': content})}\n\n"
                                    except (json.JSONDecodeError, KeyError, IndexError):
                                        pass
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
