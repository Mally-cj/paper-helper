from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import dotenv
import os

dotenv.load_dotenv()
from fastapi.staticfiles import StaticFiles
app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount('/static', StaticFiles(directory='static'), name='static')
# 新增导入
from utils.pdf_section_parser import extract_sections
from utils.arxiv_search import search_arxiv
from utils.llm_service import LLMService, RunnablePassthrough
from utils.google_search import google_scholar_search
from utils.arxiv_parser import get_arxiv_sections

# 原有全局变量保持不变
model_settings = {
    "base_url": os.environ.get("OPENAI_API_BASE"),
    "api_key": os.environ.get("OPENAI_API_KEY"),
    "model": os.environ.get("OPENAI_MODEL")
}

model = LLMService(model_settings["base_url"], model_settings["api_key"], model_settings["model"], 1)
SERPAPI_KEY = "ef6533809d34c615ee1b38ab0dd87fe1b09b4d47f667a53aabd2531ef5b45143"
temp_message = ''
messages = [{'role':'system','content':'作为一个ai助手，你必须根据用户的输入进行回答，不可以胡编乱造。'}]

# 定义请求体模型
class SearchRequest(BaseModel):
    keywords: str = ''
    category: str = ''
    dateRange: str = 'all'
    selectivityrule: str = 'date'

class SettingsRequest(BaseModel):
    baseUrl: str
    apiKey: str
    model: str

class MessageRequest(BaseModel):
    message: str

# 首页路由
@app.get("/")
async def index():
    return FileResponse("templates/index.html")

# 论文搜索路由
@app.post("/api/search")
async def search_papers(request: SearchRequest):
    results = search_arxiv(
        query=request.keywords,
        category=request.category,
        date=request.dateRange,
        selectivityrule=request.selectivityrule
    )
    return JSONResponse(content=results)

# Google学术搜索路由
@app.post("/api/google_scholar_search")
async def google_scholar_search_route(request: SearchRequest):
    results = google_scholar_search(request.keywords, SERPAPI_KEY, 10)
    return JSONResponse(content=results or [])

# 设置保存路由
@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    global model_settings, model
    model_settings.update(request.dict())
    model = LLMService(
        model_settings["base_url"],
        model_settings["api_key"],
        model_settings["model"],
        0.5
    )
    return {"message": "设置���保存"}

# 流式响应生成器
async def generate_stream(chain : RunnablePassthrough, message):
    try:
        response_chunks = []
        for chunk in chain.stream({"message":message}):
            response_chunks.append(chunk)
            yield chunk
    except Exception as e:
        yield f"data:[Error]{str(e)}\n\n"
    finally:
        # global temp_message
        if response_chunks:
            response_chunks = ''.join(response_chunks)
            # temp_message=response_chunks.split('</think>')[1]
# 翻译/总结/解释路由（示例处理翻译路由）
@app.post("/api/translate")
async def translate(request: MessageRequest):
    if not all(model_settings.values()):
        raise HTTPException(status_code=400, detail="请先配置模型设置")
    
    prompt_template = """请将以下提供的英文论文段落翻译成中文。你的回答需要满足以下要求：
        准确性：确保翻译忠实于原文含义，不遗漏关键信息，不添加未提及的内容。
        学术规范：采用符合中文学术写作的正式语言，避免口语化表达，正确翻译专业术语。
        流畅性：翻译后的中文文本语法正确、自然通顺，适合中文母语读者阅读。
        术语处理：识别并准确翻译专业术语，若术语有特定含义，可在括号中保留英文原文或添加简短解释。
        格式清晰：直接输出中文翻译内容，不需要其他解释。
        上下文感知：根据段落内容推测可能的学术背景（如学科或研究主题），确保翻译符合相关领域惯例。
        以下是待翻译的英文论文段落：{message} 请基于上述要求进行翻译。"""
    
    chain = model.generate_response(prompt_template, {"message"})
    return StreamingResponse(
        generate_stream(chain, request.message),
        media_type="text/event-stream"
    )

# 多轮对话路由
@app.post("/api/multichat")
async def multichat(request: MessageRequest):
    global messages, temp_message
    message = request.message
    conversation_length = 5
    if message=='clear':
        messages = [{'role':'system','content':'作为一个ai助手，你必须根据用户的输入进行回答，不可以胡编乱造。'}]
        return "**论文助手**: 已经清空对话记录"
    if temp_message:
        messages.append({'role':'assistant','content':temp_message})
        temp_message = ''
    message = {'role': 'user', 'content': message}
    messages.append(message)
    chain = model.generate_multi_round(messages)
    return StreamingResponse(
        generate_stream(chain, request.message),
        media_type="text/event-stream"
    )

# 新增PDF章节解析路由
# 修正参数匹配问题
@app.post("/api/pdf/sections")
async def get_pdf_sections(data: dict = Body(...)):
    try:
        title = data.get('title')
        sections = await get_arxiv_sections(title)
        
        # 获取匹配的PDF链接
        search_url = f"http://export.arxiv.org/api/query?search_all={urllib.parse.quote(title)}"
        response = requests.get(search_url)
        soup = BeautifulSoup(response.content, 'xml')
        entry = soup.find('entry')
        pdf_url = entry.link.find('title', text='pdf').parent['href'] if entry else None

        return JSONResponse(content={
            "sections": sections,
            "matched_pdf": pdf_url
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1999)
