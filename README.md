# ⚡ BidBuddy — 招投标AI助手

> 一句话触发 · 智能抓取 · 多模型驱动  
> Apple 极简风界面 · 超聚变赛题作品

---

## 📸 预览

![BidBuddy Screenshot](screenshot.png)

## 🎯 项目简介

BidBuddy 是一个面向**超聚变**命题的招投标信息智能聚合工具。用户输入自然语言，系统自动解析意图、抓取 37 个招标网站、AI 智能过滤，生成结构化结果。

### 核心能力

| 功能 | 说明 |
|------|------|
| 🧠 **自然语言理解** | "每天上午9点查光伏巡检招标" → 自动解析意图 |
| 🌐 **多站并发抓取** | 37 个主流招标网站，支持 Selenium 浏览器模式 |
| 🤖 **多模型 AI 过滤** | 5 大提供商 13+ 模型可选，智能筛选相关招标 |
| ⏰ **定时任务** | 支持 NLP 智能频率解析 + APScheduler 定时调度 |
| 📊 **实时监控** | SSE 实时日志推送，可视化进度跟踪 |

## 🤖 多模型支持

| 提供商 | 模型 |
|--------|------|
| 🐋 DeepSeek | deepseek-chat · deepseek-v4-pro |
| 🧠 OpenAI | gpt-4o · gpt-4 · gpt-3.5-turbo |
| 🏮 智谱AI | GLM-4 · GLM-4 Flash |
| 🌙 月之暗面 | moonshot-v1-8k · moonshot-v1-32k |
| ☁️ 阿里云 | qwen-turbo · qwen-plus · qwen-max |
| 🔧 自定义 | 任意 OpenAI 兼容 API |

## 🚀 一键启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python app.py

# 3. 浏览器打开
# http://localhost:8080
```

## 🏗️ 技术架构

```
bidbuddy/
├── app.py                    # FastAPI 主入口，一键启动
├── requirements.txt          # Python 依赖
├── start.bat                 # Windows 一键启动脚本
├── src/
│   ├── core.py               # 核心引擎（爬虫调度 + 匹配 + AI 过滤）
│   ├── llm_client.py         # 统一多模型 LLM 客户端
│   ├── storage.py            # JSON 文件存储引擎
│   ├── matcher.py            # AND/OR/NOT 关键词匹配器
│   ├── scheduler.py          # APScheduler 定时任务封装
│   └── crawler/              # 17 个招标网站爬虫模块
├── static/
│   ├── index.html            # Apple 极简风主页面
│   ├── css/style.css         # 毛玻璃 · 大圆角 · SF字体
│   └── js/app.js             # SSE 实时日志 · 多模型切换
└── data/                     # 运行时数据目录
```

### 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + Uvicorn |
| 前端 | 原生 HTML/CSS/JS（Apple 极简设计系统） |
| 爬虫 | requests + BeautifulSoup4 + Selenium |
| 定时任务 | APScheduler |
| 实时推送 | Server-Sent Events (SSE) |
| AI 集成 | 统一 LLM Client（5 厂商 13+ 模型） |
| 数据存储 | JSON 文件存储 |

## 🎨 设计亮点

- **毛玻璃侧边栏**：`backdrop-filter: blur(30px)` 深色毛玻璃
- **Apple 风格**：SF 字体 · 大圆角卡片 · 胶囊按钮 · 弹性动效
- **Spotlight 搜索**：居中大输入框，focus 蓝色光环
- **实时体验**：SSE 秒级日志推送 + 进度条可视化
- **响应式**：桌面优先，侧边栏自动折叠适配小屏

## 📋 比赛信息

| 项目 | 内容 |
|------|------|
| 组名 | Synapse |
| 赛题 | 飞书AI先锋未来人才大赛 |
| 目标企业 | 超聚变数字技术股份有限公司 |
| 命题 | 招投标信息智能聚合工具 |

## 📄 License

MIT

---

*Made with ❤️ for 飞书AI先锋未来人才大赛 · Synapse Team*
