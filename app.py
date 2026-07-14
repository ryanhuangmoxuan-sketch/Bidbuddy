"""
BidBuddy — 招投标AI助手
Apple风格极简界面 · 多模型智能支持 · 一句话触发检索

启动方式：python app.py
访问地址：http://localhost:8080
"""
import os
import sys
import json
import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

# ─── 路径配置 ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio as aio

from core import Engine, get_default_sites
from storage import Storage
from llm_client import LLMClient, get_model_list, MODEL_REGISTRY
from scheduler import TaskScheduler

# ─── 日志 ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BidBuddy")

# ─── 全局状态 ───────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.engine = Engine(log_callback=self._on_log)
        self.storage = self.engine.storage
        self.scheduler: Optional[TaskScheduler] = None
        self.is_running = False
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.logs: List[str] = []
        self.today_rounds = 0
        self.today_date = datetime.now().strftime('%Y-%m-%d')

        # SSE 事件队列
        self._sse_queues: List[asyncio.Queue] = []

    def _on_log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self.logs.append(entry)
        if len(self.logs) > 300:
            self.logs = self.logs[-300:]
        logger.info(message)
        # 推送到 SSE 客户端
        for q in self._sse_queues:
            try:
                q.put_nowait(entry)
            except Exception:
                pass

    def add_sse_queue(self, q: asyncio.Queue):
        self._sse_queues.append(q)

    def remove_sse_queue(self, q: asyncio.Queue):
        try:
            self._sse_queues.remove(q)
        except ValueError:
            pass

    def check_today(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self.today_date:
            self.today_date = today
            self.today_rounds = 0


state = AppState()

# ─── FastAPI 应用 ───────────────────────────────────────────
app = FastAPI(
    title="BidBuddy",
    description="招投标AI助手 — 智能聚合招标信息",
    version="2.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 静态文件 ───────────────────────────────────────────────
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """主页面"""
    index_path = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>BidBuddy</h1><p>静态文件缺失</p>")


# ─── Pydantic 模型 ──────────────────────────────────────────

class SearchInput(BaseModel):
    query: str = ""                    # 自然语言输入
    keywords: str = ""                 # 或直接指定关键词
    exclude: str = ""
    must_contain: str = ""


class ConfigUpdate(BaseModel):
    keywords: Optional[str] = None
    exclude: Optional[str] = None
    must_contain: Optional[str] = None
    interval: Optional[int] = None
    enabled_sites: Optional[List[str]] = None
    use_selenium: Optional[bool] = None
    ai_enabled: Optional[bool] = None
    ai_model: Optional[str] = None
    ai_key: Optional[str] = None
    ai_custom_url: Optional[str] = None


# ─── SSE 实时推送 ───────────────────────────────────────────

@app.get("/api/stream")
async def event_stream(request: Request):
    """Server-Sent Events 实时日志流"""
    queue: asyncio.Queue = asyncio.Queue()
    state.add_sse_queue(queue)

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            state.remove_sse_queue(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── API 路由 ───────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """获取运行状态"""
    state.check_today()
    all_bids = state.storage.get_all()
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_new = sum(1 for b in all_bids if b.publish_date and b.publish_date.startswith(today_str))

    return {
        "is_running": state.is_running,
        "last_run": state.last_run.strftime("%H:%M:%S") if state.last_run else None,
        "next_run": state.next_run.strftime("%H:%M:%S") if state.next_run else None,
        "total_bids": len(all_bids),
        "today_new": today_new,
        "today_rounds": state.today_rounds,
        "interval": state.engine.config.get('interval', 20),
        "progress_current": state.engine.progress_current,
        "progress_total": state.engine.progress_total,
        "progress_site": state.engine.progress_site,
        "is_crawling": state.engine.progress_current > 0 and \
                       state.engine.progress_current < state.engine.progress_total,
    }


@app.get("/api/results")
async def get_results(limit: int = 50, offset: int = 0):
    """获取招标结果列表"""
    all_bids = state.storage.get_all()
    all_bids.sort(key=lambda b: b.publish_date or "", reverse=True)
    total = len(all_bids)
    items = all_bids[offset:offset + limit]

    return {
        "total": total,
        "items": [
            {
                "title": b.title,
                "url": b.url,
                "source": b.source,
                "pub_date": b.publish_date or "未知",
                "notified": b.notified,
                "created_at": b.created_at,
            }
            for b in items
        ]
    }


@app.get("/api/logs")
async def get_logs(limit: int = 80):
    """获取日志"""
    return {"logs": state.logs[-limit:]}


@app.delete("/api/logs")
async def clear_logs():
    state.logs.clear()
    return {"success": True}


@app.delete("/api/history")
async def clear_history():
    state.storage.clear_all()
    state.engine.log("🗑️ 历史数据已清空")
    return {"success": True}


@app.post("/api/search")
async def search(input_data: SearchInput, background_tasks: BackgroundTasks):
    """
    核心接口：接收自然语言或关键词，触发检索
    """
    query = input_data.query.strip()
    keywords = input_data.keywords.strip()

    if not query and not keywords:
        raise HTTPException(status_code=400, detail="请输入搜索内容")

    # 如果有自然语言输入且有AI配置，先解析意图
    if query and state.engine.config.get('ai_enabled') and state.engine.config.get('ai_key'):
        intent = state.engine.parse_intent(query)
        keywords = intent.get('keywords', query)
        state.engine.log(f"💡 {intent.get('summary', '')}")
    elif query:
        keywords = query

    state.engine.config['keywords'] = keywords
    if input_data.exclude:
        state.engine.config['exclude'] = input_data.exclude
    if input_data.must_contain:
        state.engine.config['must_contain'] = input_data.must_contain

    # 后台执行检索
    async def do_search():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: state.engine.run_once(
                keywords=keywords,
                exclude=input_data.exclude,
                must_contain=input_data.must_contain,
                progress_cb=lambda c, t, s: None
            )
        )

    background_tasks.add_task(do_search)
    return {
        "success": True,
        "message": f"开始搜索：{keywords[:50]}",
        "keywords": keywords,
    }


@app.post("/api/start")
async def start_monitor(background_tasks: BackgroundTasks):
    """启动定时监控"""
    if state.is_running:
        return {"success": False, "message": "监控已在运行中"}

    state.is_running = True
    interval = state.engine.config.get('interval', 20)

    def run_task():
        state.check_today()
        keywords = state.engine.config.get('keywords', '')
        if not keywords:
            state.engine.log("⚠️ 未设置关键词，跳过本轮")
            return
        state.engine.run_once(keywords=keywords)
        state.last_run = datetime.now()
        state.today_rounds += 1

    state.scheduler = TaskScheduler(interval_minutes=interval)
    state.scheduler.start(run_task, run_immediately=True)
    state.engine.log(f"✅ 定时监控已启动，间隔 {interval} 分钟")

    return {"success": True, "message": f"监控已启动，每 {interval} 分钟执行一次"}


@app.post("/api/stop")
async def stop_monitor():
    """停止定时监控"""
    if not state.is_running:
        return {"success": False, "message": "监控未在运行"}

    if state.scheduler:
        state.scheduler.stop()
        state.scheduler = None
    state.is_running = False
    state.next_run = None
    state.engine.log("⏹️ 定时监控已停止")
    return {"success": True}


@app.post("/api/run-once")
async def run_once(background_tasks: BackgroundTasks):
    """立即执行一次检索（不改变运行状态）"""
    keywords = state.engine.config.get('keywords', '')
    if not keywords:
        raise HTTPException(status_code=400, detail="请先在设置中配置关键词")

    async def do_search():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: state.engine.run_once(keywords=keywords))
        state.last_run = datetime.now()
        state.today_rounds += 1

    background_tasks.add_task(do_search)
    state.engine.log("🔍 手动触发检索...")
    return {"success": True, "message": "检索已开始"}


# ─── 配置接口 ───────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    """获取完整配置"""
    cfg = state.engine.config.copy()
    # 隐藏敏感信息
    if cfg.get('ai_key'):
        cfg['ai_key'] = cfg['ai_key'][:4] + '****' + cfg['ai_key'][-4:] if len(cfg['ai_key']) > 8 else '****'
    return cfg


@app.post("/api/config")
async def update_config(data: ConfigUpdate):
    """更新配置"""
    updates = data.dict(exclude_unset=True)

    # 特殊处理：如果 ai_key 包含 **** 说明是前端脱敏值，不更新
    if 'ai_key' in updates and updates['ai_key'] and '****' in str(updates['ai_key']):
        del updates['ai_key']

    state.engine.config.update(updates)
    state.engine.log("⚙️ 配置已更新")
    return {"success": True}


@app.get("/api/sites")
async def get_sites():
    """获取网站列表"""
    sites = get_default_sites()
    enabled = state.engine.config.get('enabled_sites', [])
    result = []
    for key, info in sites.items():
        result.append({
            "key": key,
            "name": info['name'],
            "url": info['url'],
            "enabled": key in enabled,
        })
    return result


@app.post("/api/sites")
async def update_sites(data: List[str]):
    """更新启用的网站"""
    state.engine.config['enabled_sites'] = data
    state.engine.log(f"📋 网站配置已更新，启用 {len(data)} 个")
    return {"success": True}


# ─── 模型接口 ───────────────────────────────────────────────

@app.get("/api/models")
async def list_models():
    """获取可用模型列表"""
    return get_model_list()


@app.post("/api/models/test")
async def test_model(data: Dict[str, Any]):
    """测试模型连接"""
    model_id = data.get('model', 'deepseek-chat')
    api_key = data.get('api_key', '')
    custom_url = data.get('custom_url', '')

    if not api_key:
        raise HTTPException(status_code=400, detail="请提供 API Key")

    client = LLMClient(
        model_id=model_id,
        api_key=api_key,
        custom_url=custom_url,
    )
    result = client.test_connection()
    return result


# ─── 启动入口 ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print(r"""
    ╔══════════════════════════════════════╗
    ║       BidBuddy — 招投标AI助手        ║
    ║       极简 · 智能 · 高效              ║
    ║    http://localhost:8080             ║
    ╚══════════════════════════════════════╝
    """)

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
