# 第 2 周学习指南：Skills 和 Tools 系统

## 🎯 本周目标

掌握 nanobot 的扩展系统，学会：
1. **区分** Skill vs Tool 的概念
2. **理解** Tools 注册机制和执行流程
3. **分析** 现有 Skills 的实现模式
4. **创建** 你第一个自定义 Skill

---

## 🏗️ 核心架构

```
┌─────────────────────────────────┐
│  Agent 的能力系统                 │
├─────────────────────────────────┤
│                                  │
│  高层能力（Skill）               │
│  ├─ memory/SKILL.md             │
│  ├─ cron/SKILL.md               │
│  └─ github/SKILL.md             │
│                                  │
│  ↓ 由 Skill 调用 ↓              │
│                                  │
│  原子工具（Tool）                 │
│  ├─ read_file                   │
│  ├─ write_file                  │
│  ├─ exec (shell)                │
│  ├─ web_search                  │
│  └─ web_fetch                   │
│                                  │
└─────────────────────────────────┘
```

---

## 📖 Part 1: Skill vs Tool（概念澄清）

### Skill

**定义**：高级能力模块，通常包含完整的解决方案

**特点**：
- 针对特定**领域或场景**（例如：记忆管理、GitHub 操作、天气查询）
- 包含**完整实现**（不仅是 SKILL.md 说明，还有其他脚本、参考资料）
- LLM **选择性使用**（Agent 决定是否读取该 Skill）
- 可能需要**用户主动激活**（例如授权令牌、配置项）

**目录结构示例**：
```
nanobot/skills/memory/
├── SKILL.md           # 使用说明和能力说明
├── scripts/           # 辅助脚本
│   └── consolidate.py
└── references/        # 参考资料
    └── memory-design.md
```

### Tool

**定义**：原子级操作，是最小的可执行单元

**特点**：
- **通用基础操作**（文件、Shell、网页等）
- 由 Agent 在**执行 Skill 时调用**
- LLM **直接可见**（工具定义在系统提示中）
- **无状态**（无需配置，调用即可）

**例子**：
```python
# Tool 是这样的：
{
    "name": "read_file",
    "description": "Read a file from disk",
    "parameters": { "filePath": "..." }
}
```

### 🔄 Skill 和 Tool 的交互

```
用户消息："帮我保存一个重要的事情"
   ↓
Agent 思考："这需要用 memory Skill"
   ↓
LLM 读取：nanobot/skills/memory/SKILL.md
   ↓
SKILL.md 告诉 LLM："你可以调用 save_memory()"
   ↓
Agent 执行：save_memory(history_entry="...", memory_update="...")
   ↓
save_memory 内部使用多个 Tool：
   ├─ read_file("memory/MEMORY.md")    ← Tool
   ├─ write_file("memory/MEMORY.md")   ← Tool
   └─ exec("git add memory/")          ← Tool
   ↓
结果保存到 MEMORY.md
```

---

## 🔧 Part 2: Tools 系统详解

### 代码位置

[nanobot/agent/tools/](nanobot/agent/tools/)

```
nanobot/agent/tools/
├── __init__.py
├── base.py          # Tool 基类
├── registry.py      # Tool 注册表
├── cron.py          # Cron Tool
├── filesystem.py    # 文件操作 Tools
├── mcp.py           # MCP 集成
├── message.py       # 消息 Tool
├── shell.py         # Shell 执行 Tool
├── spawn.py         # 子 Agent Tool
└── web.py           # 网页 Tools
```

### 基类：Tool

让我们看看 Tool 的基类结构：

```python
# nanobot/agent/tools/base.py 中的伪代码

class Tool:
    """All tools inherit from this base class"""
    
    def get_definition(self) -> dict:
        """Return JSON Schema definition for LLM"""
        # 返回工具的 OpenAI function schema
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": { ... }
            }
        }
    
    async def execute(self, arguments: dict) -> str:
        """Execute the tool and return result as string"""
        # 实际执行逻辑
        pass
```

### Tool 注册表：ToolRegistry

```python
# nanobot/agent/tools/registry.py 中的伪代码

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """注册一个工具"""
        self.tools[tool.name] = tool
    
    def get_definitions(self) -> list[dict]:
        """获取所有工具的 JSON Schema（发给 LLM）"""
        return [tool.get_definition() for tool in self.tools.values()]
    
    async def execute(self, tool_name: str, arguments: dict) -> str:
        """执行指定的工具"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        return await self.tools[tool_name].execute(arguments)
```

### 🎯 思考题 1
> 为什么需要 `get_definitions()` 这个方法？这个方法的返回值会被用在哪里？

<details>
<summary>答案</summary>

`get_definitions()` 返回所有工具的 JSON Schema 格式定义。

**用在**：`AgentLoop._run_agent_loop()` 中，每次调用 LLM 时：
```python
response = await self.provider.chat(
    messages=messages,
    tools=self.tools.get_definitions(),  # ← 这里！
    model=self.model,
)
```

LLM 需要知道"有哪些工具可用"，才能决定是否调用某个工具。

</details>

---

## 🎨 Part 3: 现有 Tools 的实现模式

### Tool 例子 1：ReadFileTool

```python
# nanobot/agent/tools/filesystem.py

class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file from disk"
    
    def __init__(self, workspace: Path, allowed_dir: Path | None = None):
        self.workspace = workspace
        self.allowed_dir = allowed_dir or workspace  # 防止读取工作目录外的文件
    
    async def execute(self, arguments: dict) -> str:
        """
        Arguments:
            filePath: Relative path to file
            startLine: Optional start line (1-indexed)
            endLine: Optional end line (1-indexed, inclusive)
        
        Returns:
            File content as string
        """
        file_path = Path(arguments["filePath"])
        
        # 安全检查：确保路径在 allowed_dir 内
        resolved = (self.allowed_dir / file_path).resolve()
        if not str(resolved).startswith(str(self.allowed_dir.resolve())):
            return f"Error: Access denied. Cannot read outside workspace."
        
        # 读取文件
        content = resolved.read_text(encoding="utf-8")
        
        # 可选的行范围截断
        if "startLine" in arguments:
            lines = content.split('\n')
            start = arguments["startLine"] - 1  # 转换为 0-indexed
            end = arguments.get("endLine", len(lines))
            content = '\n'.join(lines[start:end])
        
        return content
```

**关键安全特性**：
- `allowed_dir` 防止越界访问
- 路径规范化和验证

### Tool 例子 2：ExecTool（Shell）

```python
# nanobot/agent/tools/shell.py

class ExecTool(Tool):
    name = "exec"
    description = "Execute a shell command"
    
    def __init__(self, working_dir: str, timeout: int = 60, restrict_to_workspace: bool = False):
        self.working_dir = working_dir
        self.timeout = timeout  # 防止无限运行
        self.restrict_to_workspace = restrict_to_workspace
    
    async def execute(self, arguments: dict) -> str:
        """
        Arguments:
            command: Shell command to run
        
        Returns:
            Command output (truncated to 10KB)
        """
        command = arguments["command"]
        
        # 危险命令检查
        BLOCKED_COMMANDS = ["rm -rf", "shutdown", "dd", "format", "reboot"]
        if any(cmd in command for cmd in BLOCKED_COMMANDS):
            return "Error: This command is blocked for safety reasons."
        
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_shell(command, ...),
                timeout=self.timeout
            )
            output = result.stdout.read()
            
            # 截断超长输出
            if len(output) > 10000:
                output = output[:10000] + b"\n... (truncated)"
            
            return output.decode()
        
        except asyncio.TimeoutError:
            return f"Command timed out after {self.timeout}s"
```

**关键安全特性**：
- 危险命令黑名单
- 超时控制
- 输出截断

### 🎯 思考题 2
> 为什么 Tools 需要这么多安全检查？如果 LLM 试图读取 `/etc/passwd` 或执行 `rm -rf /`，会发生什么？

<details>
<summary>答案</summary>

因为 LLM 是自主的——它无法被完全控制。如果没有安全检查：

1. **恶意请求**：用户可能试图欺骗 Agent 删除文件
2. **LLM 误判**：模型可能 hallucinate（幻想出）不应该执行的命令
3. **权限提升**：如果 Agent 在高权限下运行，破坏力更大

**带安全检查后**：
```python
# 获得一些保护
user_message: "请删除所有文件"
     ↓
LLM: "执行 exec('rm -rf /')"
     ↓
ExecTool: "Warning: blocked command 'rm -rf'"
     ↓
保护成功！
```

虽然不是完美防护，但大大降低了风险。

</details>

---

## 🎯 进阶理解

### Tool 的通用模式

所有 Tool 都遵循这个模式：

```
1. 定义（get_definition）
   ├─ 工具名称
   ├─ 描述
   └─ 参数 Schema（JSON Schema 格式）

2. 验证（execute 开始）
   ├─ 输入参数检查
   └─ 权限/安全性检查

3. 执行（execute 主要逻辑）
   └─ 真实操作

4. 格式化（return）
   ├─ 结果转为字符串
   └─ 截断超长结果
```

### ToolRegistry 的作用

ToolRegistry 是 Agent 和工具之间的**中间件**：

```
┌──────────────┐
│    Agent     │
└──────────────┘
       ↓
[Agent 决定调用 tool_name="read_file"]
       ↓
┌──────────────────────────────┐
│   ToolRegistry.execute(...)  │
│   1. 查找工具                 │
│   2. 验证权限                 │
│   3. 调用工具                 │
│   4. 返回结果                 │
└──────────────────────────────┘
       ↓
返回结果给 Agent
```

---

## 📋 学习任务清单

### 代码探索（30 分钟）
- [ ] 打开 [tools/base.py](nanobot/agent/tools/base.py)，看 Tool 基类的完整实现
- [ ] 打开 [tools/registry.py](nanobot/agent/tools/registry.py)，看 ToolRegistry 的完整实现
- [ ] 打开 [tools/filesystem.py](nanobot/agent/tools/filesystem.py#L1-L100)，研究 ReadFileTool 的具体 execute() 方法
- [ ] 打开 [tools/shell.py](nanobot/agent/tools/shell.py#L1-L100)，研究 ExecTool 的安全检查

### 理论问题（20 分钟）
- [ ] **问题 1**：为什么 Tool 的 `execute()` 方法返回值必须是字符串？
- [ ] **问题 2**：如果一个 Tool 没有注册到 ToolRegistry 中，LLM 能否调用它？为什么？
- [ ] **问题 3**：`get_definition()` 返回的 JSON Schema 中，参数部分应该包含什么信息？

### 动手实验（20 分钟）
- [ ] 在终端中运行：`uv run python -c "from nanobot.agent.tools.registry import ToolRegistry; from nanobot.agent.tools.filesystem import ReadFileTool; from pathlib import Path; r = ToolRegistry(); r.register(ReadFileTool(Path('.'))); import json; print(json.dumps(r.get_definitions(), indent=2))"`
- [ ] 查看输出，理解一个 Tool 的完整 JSON Schema 格式

---

## 🚀 下一步

完成上面的学习和实验后，我们进入 **Part 4：理解现有 Skills**，这是为创建自定义 Skill 做准备。

准备好继续吗？告诉我你对上面哪个部分感兴趣！ 🎯

