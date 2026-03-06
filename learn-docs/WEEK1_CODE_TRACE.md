# 第 1 周深度钻研：代码追踪示例

## 🎬 场景
用户在 Telegram 中发送："今天天气怎么样？"

## 🔍 追踪路径

### 第 0 步：消息到达 MessageBus（外部系统）

```python
# 假如这是 Telegram 集成的代码（nanobot/channels/telegram.py）
# 伪代码，实际可能更复杂

incoming_text = "今天天气怎么样？"
user_id = "123456789"
chat_id = "987654321"

# 创建 InboundMessage
message = InboundMessage(
    channel="telegram",
    sender_id="123456789",
    chat_id="987654321",
    content="今天天气怎么样？",
    timestamp=datetime.now(),
)

# 发布到 MessageBus
await bus.publish_inbound(message)
```

**关键概念**：
- `channel="telegram"` → 消息来自 Telegram
- `session_key = "telegram:987654321"` → 这个聊天 ID 对应的会话

---

### 第 1 步：AgentLoop 接收消息

```python
# AgentLoop 实现的伪代码（简化）
# 实际代码在 nanobot/agent/loop.py

class AgentLoop:
    async def process(self, inbound_msg: InboundMessage):
        """处理一条入站消息"""
        
        # 1.1 确定会话 ID
        session_key = inbound_msg.session_key
        # session_key = "telegram:987654321"
        
        # 1.2 恢复或创建会话
        session = await self.sessions.get_or_create(session_key)
        # session 包含历史消息列表
        
        # 1.3 添加新消息到会话
        session.messages.append({
            "role": "user",
            "content": "今天天气怎么样？"
        })
        
        print(f"[Session {session_key}] 已添加用户消息")
        print(f"历史消息数: {len(session.messages)}")
```

**关键点**：
- `SessionManager` 通过 `session_key` 维护消息历史
- 同一个聊天不会混淆（不同 `session_key` = 不同会话）

---

### 第 2 步：ContextBuilder 构建提示词

```python
# ContextBuilder 的伪代码
class ContextBuilder:
    def build_system_prompt(self, skill_names=None) -> str:
        """组装完整的系统提示"""
        
        parts = []
        
        # 2.1 身份部分
        identity = self._get_identity()
        # 返回：
        """
# nanobot 🐈

You are nanobot, a helpful AI assistant.

## Runtime
macOS arm64, Python 3.10.0

## Workspace
Your workspace is at: /Users/lihaizhong/Documents/Project/ForkSource/nanobot
"""
        parts.append(identity)
        
        # 2.2 引导文件
        bootstrap = self._load_bootstrap_files()
        # 返回 AGENTS.md + SOUL.md + USER.md + TOOLS.md 的内容
        """
## Scheduled Reminders
...（AGENTS.md 内容）

## Soul
I am nanobot 🐈, a personal AI assistant.
Personality:
- Helpful and friendly
- Concise and to the point
...（SOUL.md 内容）
"""
        parts.append(bootstrap)
        
        # 2.3 记忆
        memory = self.memory.get_memory_context()
        # 如果 memory/MEMORY.md 存在，返回它的内容
        # 格式：
        """
## Long-term Memory
- 用户名：张三
- 工作领域：数据科学
- 偏好语言：中文
"""
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # 2.4 Active Skills
        always_skills = self.skills.get_always_skills()
        # 返回始终可用的 Skills 的实现代码
        # 例如 code execution, memory saving 等
        
        # 2.5 Skills 摘要
        skills_summary = self.skills.build_skills_summary()
        # 返回：
        """
The following skills extend your capabilities:
- memory/SKILL.md - 记忆管理
- cron/SKILL.md - 定时任务
- github/SKILL.md - GitHub 集成
- weather/SKILL.md - 天气查询
"""
        parts.append(f"# Skills\n\n{skills_summary}")
        
        # 最后，用 --- 分隔符连接所有部分
        system_prompt = "\n\n---\n\n".join(parts)
        return system_prompt
```

**输出示例**（这是一个巨大的文本块）：

```markdown
# nanobot 🐈

You are nanobot, a helpful AI assistant.

## Runtime
macOS arm64, Python 3.10.0

## Workspace
Your workspace is at: /Users/lihaizhong/Documents/Project/ForkSource/nanobot

---

# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Scheduled Reminders
...

---

# Soul

I am nanobot 🐈, a personal AI assistant.

## Personality
- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

---

# Memory

## Long-term Memory
[用户之前学到的东西]

---

# Skills

The following skills extend your capabilities:
- memory/SKILL.md
- cron/SKILL.md
- github/SKILL.md

You can use these skills by reading their SKILL.md file.
```

---

### 第 3 步：准备对 LLM 的请求

```python
# AgentLoop._run_agent_loop() 的伪代码
class AgentLoop:
    async def _run_agent_loop(self, initial_messages):
        """运行 Agent 迭代循环"""
        
        messages = [
            # 3.1 系统提示（上面构建的那个巨大字符串）
            {
                "role": "system",
                "content": system_prompt  # 刚才构建的完整提示词
            },
            # 3.2 通过 memory_window（默认 100）选择最近的消息
            {
                "role": "user",
                "content": "[历史消息 1]"
            },
            {
                "role": "assistant",
                "content": "[历史响应 1]"
            },
            # ... 中间消息 ...
            {
                "role": "user",
                "content": "今天天气怎么样？"  # 当前用户消息
            }
        ]
        
        iteration = 0
        max_iterations = 40
        
        while iteration < max_iterations:
            iteration += 1
            print(f"[迭代 {iteration}] 调用 LLM...")
            
            # 3.3 调用 LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),  # 可用工具列表
                model=self.model,  # "gpt-4-turbo" 或其他
                temperature=self.temperature,  # 0.1（确定性）
                max_tokens=self.max_tokens,  # 4096
            )
            
            # response 格式：
            # {
            #     "content": "我来帮你查询天气...",
            #     "tool_calls": [
            #         {
            #             "id": "call_abc123",
            #             "name": "web_search",
            #             "arguments": {"query": "今日北京天气"}
            #         }
            #     ]
            # }
            
            tools_used = []
            
            # 3.4 检查是否有工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.name
                    tools_used.append(tool_name)
                    print(f"  → 执行工具: {tool_name}({tool_call.arguments})")
                    
                    # 3.5 执行工具
                    try:
                        tool_result = await self.tools.execute(tool_call)
                        # tool_result 可能是："晴天，最高 15°C，最低 5°C"
                        
                        # 3.6 添加工具结果到消息历史
                        messages.append({
                            "role": "assistant",
                            "content": response.content
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        })
                        
                        print(f"  ← 工具返回: {tool_result[:100]}...")
                    
                    except Exception as e:
                        print(f"  ✗ 工具执行失败: {e}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"错误: {e}"
                        })
                
                # 3.7 继续迭代（LLM 再次调用，处理工具结果）
                print(f"[迭代 {iteration}] 有工具调用，继续...")
                continue
            
            else:
                # 3.8 没有工具调用 → Agent 已经给出最终答案
                final_content = response.content
                print(f"[迭代 {iteration}] Agent 给出最终答案")
                break
        
        return final_content, tools_used, messages
```

**关键概念**：
- `memory_window=100` → 最多发送最近 100 条消息给 LLM
- 每次 LLM 调用后，如果有 `tool_calls`，就执行工具，然后继续循环
- 直到 LLM 不再请求工具调用，或达到 `max_iterations=40`

---

### 第 4 步：保存会话和整合记忆

```python
# AgentLoop.process() 的后半部分伪代码
class AgentLoop:
    async def process(self, inbound_msg: InboundMessage):
        # ... 前面的步骤 ...
        
        final_content, tools_used, messages = await self._run_agent_loop(...)
        
        # 4.1 保存会话
        session.messages = messages  # 更新消息历史
        await session.save()  # 持久化到磁盘（通常是 JSON 文件）
        print(f"会话已保存: {len(messages)} 条消息")
        
        # 4.2 整合记忆（如果需要）
        should_consolidate = len(session.messages) > 100
        if should_consolidate:
            print("📚 消息足够多，开始整合记忆...")
            success = await self.memory.consolidate(
                session=session,
                provider=self.provider,
                model=self.model,
            )
            if success:
                print("✓ 记忆已整合到 MEMORY.md 和 HISTORY.md")
        
        # 4.3 创建出站消息
        outbound_msg = OutboundMessage(
            channel="telegram",
            chat_id="987654321",
            content=final_content,
            # content 可能是：
            # "根据天气 API，今天北京晴天，最高 15°C，最低 5°C。"
        )
        
        # 4.4 发送回 MessageBus
        await self.bus.publish_outbound(outbound_msg)
        print(f"✓ 消息已发送到 {outbound_msg.channel}")
```

**关键概念**：
- `Session.save()` → 存入磁盘，这样下次恢复会话时能读回消息
- `consolidate()` → 如果消息太多，用 LLM 提炼要点，保存到 `MEMORY.md` 和 `HISTORY.md`

---

### 第 5 步：消息回到用户

```
Telegram 频道接收到 OutboundMessage
   ↓
检查 channel="telegram" 和 chat_id
   ↓
通过 Telegram API 发送消息
   ↓
用户看到回复：
   "根据天气 API，今天北京晴天，最高 15°C，最低 5°C。"
```

---

## 📊 完整的数据流图

```
用户输入：
"今天天气怎么样？"
    ↓
InboundMessage(
  channel="telegram",
  chat_id="987654321",
  content="今天天气怎么样？"
)
    ↓
session_key = "telegram:987654321"
    ↓
SessionManager.get_or_create(session_key)
    ↓
Session {
  messages: [
    {"role": "user", "content": "...历史消息..."},
    {"role": "assistant", "content": "...历史回复..."},
    {"role": "user", "content": "今天天气怎么样？"}
  ]
}
    ↓
ContextBuilder.build_system_prompt()
    ↓
system_prompt = """
# nanobot 🐈

You are nanobot...

...（身份、记忆、Skills等）
"""
    ↓
messages = [
  {"role": "system", "content": system_prompt},
  ...session.messages...
]
    ↓
LLMProvider.chat(
  messages=messages,
  tools=[web_search, read_file, exec, ...],
  model="gpt-4-turbo"
)
    ↓
provider.chat() 返回：
response = {
  "content": "我来帮你查询天气...",
  "tool_calls": [
    {
      "name": "web_search",
      "arguments": {"query": "今日北京天气"}
    }
  ]
}
    ↓
执行 web_search 工具：
tool_result = "晴天，15°C..."
    ↓
添加工具结果到 messages：
messages.append({
  "role": "tool",
  "content": "晴天，15°C..."
})
    ↓
再次调用 LLM 处理工具结果
    ↓
provider.chat() 返回：
{
  "content": "根据天气数据，今天北京晴天，最高 15°C...",
  "tool_calls": []  # 没有更多工具调用
}
    ↓
保存会话：
session.messages = messages
session.save()
    ↓
发送出站消息：
OutboundMessage(
  channel="telegram",
  chat_id="987654321",
  content="根据天气数据，今天北京晴天..."
)
    ↓
bus.publish_outbound(msg)
    ↓
Telegram 渠道发送消息给用户
    ↓
用户接收到回复 ✓
```

---

## 🧪 自己试试看

### 练习 1：参数追踪
> 如果你把 `memory_window` 从 100 改成 10，会发生什么？

<details>
<summary>答案</summary>

AgentLoop 只会把最近 10 条消息发给 LLM，而不是 100 条。

**影响**：
- 优点：快更便宜，LLM 调用更快
- 缺点：Agent 不知道很久之前的上下文

例如，10 条前讲过"我是数据科学家"，Agent 会忘记。

</details>

### 练习 2：工具调用追踪
> 为什么 `_tool_result_max_chars = 500`？

<details>
<summary>答案</summary>

工具的输出可能非常长（例如读取一个 10MB 的文件）。

如果不截断，会导致：
1. 发给 LLM 的消息太大，超过 token 限制
2. LLM 调用费用增加

所以只取前 500 个字符，告诉 LLM"太长了，看不完"。

</details>

### 练习 3：迭代循环
> 如果 Agent 请求 50 个工具调用，会怎样？

<details>
<summary>答案</summary>

只执行前 40 个（因为 `max_iterations=40`）。

第 40 个迭代后，即使 Agent 还要请求工具，也会停止，返回当前的 `final_content`。

这个保护机制防止 Agent 陷入无限循环。

</details>

---

## 🎓 总结

通过这个追踪，你现在应该理解：

1. **InboundMessage** 是整个流程的起点
2. **SessionManager** 维护对话的上下文
3. **ContextBuilder** 定制化地构建 LLM 提示词
4. **AgentLoop** 是主控制器，协调 LLM 和工具
5. **OutboundMessage** 是最后的输出

下一步，打开 VSCode，看真实代码！

