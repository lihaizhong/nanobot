# 第 1 周学习指南：Agent 基础框架

## 🎯 今天的学习目标
- 理解 Agent 的完整执行流程
- 掌握三个核心模块的职责
- 追踪一条消息的完整旅程

---

## 📍 Part 1: 消息流入口 - InboundMessage

### 代码位置
[nanobot/bus/events.py](nanobot/bus/events.py)

### 关键数据结构

```python
@dataclass
class InboundMessage:
    channel: str        # 消息来自哪个渠道（telegram, discord, slack）
    sender_id: str      # 谁发送的消息（用户 ID）
    chat_id: str        # 在哪个聊天/频道中（群组 ID）
    content: str        # 消息内容（用户的实际输入）
    timestamp: datetime # 何时发送
    
    @property
    def session_key(self) -> str:  # 会话标识（用于恢复对话历史）
        return f"{self.channel}:{self.chat_id}"
```

### 🤔 思考题 1
> 如果用户在 Discord 的 #general 频道中说"你好"，这三个字段会是什么？
> 
> - `channel` = ?
> - `chat_id` = ?
> - `session_key` = ?

<details>
<summary>点击查看答案</summary>

```python
channel = "discord"
chat_id = "general"  # Discord 频道 ID
session_key = "discord:general"  # 用来跟踪这个频道的历史消息
```

亮点：**同一个频道的不同消息会复用同一个 session_key**，这样可以保持对话上下文！

</details>

---

## 📍 Part 2: 核心处理 - AgentLoop

### 代码位置
[nanobot/agent/loop.py](nanobot/agent/loop.py#L1-L200)

### AgentLoop 初始化时做了什么？

```python
def __init__(self, bus, provider, workspace, ...):
    # 1️⃣ 保存依赖
    self.bus = bus                    # 消息总线
    self.provider = provider          # LLM 提供商（OpenAI/Claude）
    self.workspace = workspace        # 工作目录
    
    # 2️⃣ 初始化关键组件
    self.context = ContextBuilder(workspace)    # 构建提示词的工具
    self.sessions = SessionManager(workspace)   # 恢复/保存会话
    self.tools = ToolRegistry()                 # 注册所有可用工具
    self.subagents = SubagentManager(...)       # 管理子 Agent
    
    # 3️⃣ 注册默认工具
    self._register_default_tools()  # 文件、Shell、网页、消息等
```

### 关键问题：**"工具"是什么？**

工具是 Agent 可以调用的原子操作：

| 工具名 | 类名 | 职责 |
|------|------|------|
| `read_file` | ReadFileTool | 读取文件内容 |
| `write_file` | WriteFileTool | 创建/覆盖文件 |
| `exec` | ExecTool | 执行 Shell 命令 |
| `web_search` | WebSearchTool | 搜索网页（Brave API） |
| `web_fetch` | WebFetchTool | 获取网页内容 |
| `message` | MessageTool | 发送消息到渠道 |

### 🤔 思考题 2
> 为什么 AgentLoop 要在初始化时就注册所有工具？
> 
> 提示：想想如果用户的消息要求 Agent 读取文件，Agent 如何知道有这个工具？

<details>
<summary>点击查看答案</summary>

当 Agent 调用 LLM 时，必须告诉 LLM"你可以使用这些工具"。

工具列表通过 `self.tools.get_definitions()` 以 JSON Schema 格式发送给 LLM。LLM 根据这个列表决定是否调用某个工具。

所以必须提前注册，LLM 才能看到。

</details>

---

## 📍 Part 3: 提示词构建 - ContextBuilder

### 代码位置
[nanobot/agent/context.py](nanobot/agent/context.py#L1-L100)

### build_system_prompt() 做什么？

这个方法组装一个**完整的系统提示**，包含 5 个部分：

```
1. 身份信息（Identity）
   └─ "你是 nanobot，一个有帮助的 AI 助手"
   └─ 当前 OS、Python 版本、工作目录
   
2. 引导文件（Bootstrap）
   └─ AGENTS.md - Agent 的能力说明
   └─ SOUL.md - 个性和行为指南
   └─ USER.md - 用户的自定义说明
   
3. 记忆（Memory）
   └─ MEMORY.md 中的长期事实
   
4. Active Skills
   └─ 始终可用的 Skills（例如代码执行）
   
5. Skills 摘要
   └─ 所有可用 Skills 的列表
```

### 代码演示

```python
system_prompt = context.build_system_prompt()
# 返回值是一个巨大的字符串，结构如：

"""
# nanobot 🐈

You are nanobot, a helpful AI assistant.

## Runtime
macOS arm64, Python 3.10.0

## Workspace
Your workspace is at: /Users/lihaizhong/Documents/Project/ForkSource/nanobot

---

# AGENTS.md

[AGENTS.md 文件的内容]

---

# Memory

## Long-term Memory
[MEMORY.md 的内容，如果存在]

---

# Active Skills

[经常使用的 Skills 的内容]

---

# Skills

The following skills extend your capabilities:
- memory/SKILL.md - Memory management
- cron/SKILL.md - Cron tasks
"""
```

### 🤔 思考题 3
> 为什么系统提示中要包含 Skills 摘要？
> 
> 提示：想想 Agent 如何决定"我应该使用哪个 Skill"。

<details>
<summary>点击查看答案</summary>

LLM 是一个文本处理器，它只能看到**提示词中明确出现的内容**。

如果系统提示中没有列出可用 Skills，LLM 就不知道这些 Skills 存在，无法使用。

所以必须在系统提示中列出所有可用的 Skills，LLM 才能在需要时说"我要调用 xxx Skill"。

</details>

---

## 📍 Part 4: 消息总线 - MessageBus 和会话恢复

### 代码位置
[nanobot/session/manager.py](nanobot/session/manager.py)

### 会话的概念

```
MessageBus（消息队列）
    ↓
AgentLoop 接收 InboundMessage
    ↓
从 SessionManager 恢复这个 session_key 的历史消息
    ↓
构建提示词并调用 LLM
    ↓
LLM 返回响应
    ↓
保存到 Session 的消息历史
    ↓
发送 OutboundMessage 回 MessageBus
```

### 🤔 思考题 4
> 如果用户在两个不同的 Discord 频道中同时和 Agent 聊天，
> 两个对话会互相影响吗？为什么？

<details>
<summary>点击查看答案</summary>

不会。因为每个频道有不同的 `session_key`：
- 频道 A: `session_key = "discord:channel_a"`
- 频道 B: `session_key = "discord:channel_b"`

SessionManager 为每个 session_key 维护独立的消息历史，所以两个对话完全隔离。

</details>

---

## 🔄 Part 5: 完整流程图

### 图示：消息从进入到发出

```
┌─────────────────────────────────────────────────────────────────┐
│ 用户在 Discord 中：你好！今天天气如何？❄️                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
            ┌─── InboundMessage 被发送到 MessageBus ───┐
            │ channel: "discord"                        │
            │ chat_id: "general"                        │
            │ content: "你好！今天天气如何？"           │
            │ sender_id: "user_123"                     │
            └───────────────────────────────────────────┘
                              ↓
            AgentLoop.process() 被调用
                              ↓
        ┌──────── 步骤 1: 恢复或创建 Session ────────┐
        │  session_key = "discord:general"            │
        │  已知历史: [消息1, 消息2, ...]              │
        └──────────────────────────────────────────┘
                              ↓
        ┌──────── 步骤 2: 构建完整提示词 ────────┐
        │  system_prompt = context.build_system_prompt() │
        │  ├─ 身份: "你是 nanobot..."              │
        │  ├─ 记忆: 长期知识                     │
        │  ├─ 可用工具列表                       │
        │  └─ 可用 Skills 列表                    │
        └──────────────────────────────────────────┘
                              ↓
        ┌──────── 步骤 3: 准备消息历史 ────────┐
        │  messages = [                           │
        │    {"role": "system", "content": system_prompt},
        │    {"role": "user", "content": "你好！..."},
        │    {"role": "assistant", "content": "你好！..."},
        │    ...历史消息...
        │    {"role": "user", "content": "今天天气..."}
        │  ]                                      │
        └──────────────────────────────────────────┘
                              ↓
        ┌──────── 步骤 4: 调用 LLM ────────┐
        │  response = provider.chat(       │
        │    messages=messages,            │
        │    tools=self.tools.get_definitions(),
        │    model="gpt-4-turbo"           │
        │  )                               │
        └──────────────────────────────────────────┘
                              ↓
        LLM 返回: {
          "content": "我来帮你查询天气...",
          "tool_calls": [
            {
              "name": "web_search",
              "arguments": {"query": "today weather"}
            }
          ]
        }
                              ↓
        ┌──────── 步骤 5: 执行工具 ────────┐
        │  for tool_call in response.tool_calls:
        │    result = execute_tool(tool_call)
        │    # 添加工具结果到消息历史
        │    messages.append({
        │      "role": "tool",
        │      "content": "云多，温度 5°C..."
        │    })
        │  再次调用 LLM（直到不再请求工具）
        └──────────────────────────────────────────┘
                              ↓
        ┌──────── 步骤 6: 保存会话 ────────┐
        │  session.messages.append(new_messages)
        │  session.save()  # 持久化到磁盘
        └──────────────────────────────────────────┘
                              ↓
        ┌──────── 步骤 7: 优化记忆 ────────┐
        │  memory.consolidate()
        │  # 如果消息足够多，用 LLM 提炼要点
        │  # 存到 MEMORY.md 和 HISTORY.md
        └──────────────────────────────────────────┘
                              ↓
        ┌──────── 步骤 8: 发送响应 ────────┐
        │  OutboundMessage(                   │
        │    channel="discord",               │
        │    chat_id="general",               │
        │    content="今天是晴天，温度..."   │
        │  )                                  │
        │  bus.publish_outbound(msg)          │
        └──────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Agent 在 Discord 中回复：今天是晴天，温度 5°C... ☀️              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Part 6: 核心概念速记表

| 概念 | 定义 | 例子 |
|------|------|------|
| **InboundMessage** | 用户输入的消息 | "你好！天气如何？" |
| **OutboundMessage** | Agent 输出的消息 | "今天晴天，5°C" |
| **session_key** | 会话标识（渠道+聊天ID） | "discord:general" |
| **Session** | 一个会话的消息历史 | [msg1, msg2, ...] |
| **system_prompt** | 告诉 LLM 如何行动的指令 | "你是 nanobot..." |
| **Tool** | Agent 可调用的操作 | read_file, web_search |
| **Skill** | 高级功能模块 | weather, github, memory |

---

## 📝 任务清单（完成即为掌握）

### 理论题
- [ ] 你能用一句话解释 `session_key` 的作用吗？
- [ ] `ContextBuilder` 为什么有 5 个部分？少一个会怎样？
- [ ] `AgentLoop` 的 `max_iterations=40` 是干什么用的？

### 代码追踪
- [ ] 打开 VSCode，在 [AgentLoop.__init__](nanobot/agent/loop.py#L50) 处设置断点
- [ ] 找到调用 `context.build_system_prompt()` 的那一行
- [ ] 观察 `tools.get_definitions()` 返回什么格式

### 动手实验
- [ ] 查看项目的 `memory/` 目录（如果存在）
  ```bash
  ls -la memory/
  cat memory/MEMORY.md    # 查看长期知识
  grep "2026-03" memory/HISTORY.md  # 查看历史日志
  ```
- [ ] 找到一个 Skill 文件（例如 [nanobot/skills/memory/SKILL.md](nanobot/skills/memory/SKILL.md)）
- [ ] 找到 AGENTS.md 或 SOUL.md，理解其内容

---

## 🚀 下一步
完成上面的任务后，发送消息"我完成了第 1 周的理论部分"，我们继续深入**实际代码调试**。

