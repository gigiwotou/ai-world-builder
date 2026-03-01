# AI World Builder

基于 OpenClaw 原理的 AI 驱动虚拟世界游戏。

## 功能特点

- 🌍 **AI 管理世界** - 由大语言模型驱动世界的发展和演化
- 🎮 **自然语言指令** - 用日常语言创造和管理世界
- 🔄 **实时推进** - 世界自动按规则推进，生物会移动，植物会生长
- 🎨 **像素风格** - 彩色方块展示世界万物
- 🔌 **可扩展** - 支持本地 Ollama 或云端 API

## 快速开始

### 1. 安装依赖

```bash
cd ai-world-builder
pip install -r requirements.txt
```

### 2. 启动 Ollama（本地模型）

如果你使用本地模型，需要先安装并启动 Ollama：

```bash
# 安装 Ollama (Linux/Mac)
curl -fsSL https://ollama.com/install.sh | sh

# 启动 Ollama
ollama serve

# 下载模型
ollama pull qwen2.5:7b
```

### 3. 启动游戏

```bash
python -m backend.main
```

或直接运行：

```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. 打开浏览器

访问 http://localhost:8000

## 使用方法

1. **创造世界** - 输入指令如 "创造一个森林" 或 "创建一个有河流的村庄"
2. **添加实体** - "在(10,5)放置一棵树"
3. **设置规则** - "让生物每天移动一次"
4. **自动模式** - 点击"自动: 关"开启世界自动推进

## 配置

修改 `config/settings.json` 调整：

```json
{
  "provider": "ollama",      // ollama, openai, anthropic
  "model": "qwen2.5:7b",    // 模型名称
  "base_url": "http://localhost:11434",
  "tick_interval": 5        // 自动推进间隔(秒)
}
```

## 项目结构

```
ai-world-builder/
├── backend/
│   ├── main.py           # FastAPI 服务入口
│   ├── agent.py          # AI 代理引擎
│   ├── llm_adapter.py    # LLM 适配器
│   ├── world_manager.py  # 世界状态管理
│   └── tools.py          # 工具定义
├── frontend/
│   └── index.html        # 前端页面
├── config/
│   └── settings.json     # 配置文件
├── data/
│   └── world.json        # 世界状态存储
└── requirements.txt
```

## 实体类型

| 类型 | 颜色 | 说明 |
|------|------|------|
| land | 棕色 | 基础地形 |
| plant | 绿色 | 植物，会生长 |
| creature | 红色 | 生物，会移动 |
| building | 蓝色 | 建筑 |
| resource | 金色 | 资源 |
| water | 蓝色 | 水 |
| fire | 橙色 | 火 |

## 技术栈

- 后端: Python + FastAPI + WebSocket
- 前端: 原生 HTML5 + Canvas
- LLM: Ollama / OpenAI / Anthropic
