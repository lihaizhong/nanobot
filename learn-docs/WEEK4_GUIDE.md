# 第 4 周学习指南：综合项目实战

## 🎯 本周目标

将前 3 周学到的知识融会贯通，完成一个**完整的 Agent 功能模块**：
1. **整合** Agent Loop、Skills、Tools、MessageBus、Session
2. **实现** 一个端到端的工作流
3. **掌握** 调试和测试 Agent 的方法
4. **产出** 可运行的完整功能

---

## 📊 前三周回顾

| 周次 | 主题 | 核心收获 |
|------|------|----------|
| Week 1 | Agent 基础框架 | AgentLoop 执行流程、Context 管理、Memory 系统 |
| Week 2 | Skills & Tools | Skill 加载机制、Tool 注册与执行、自定义 Skill 创建 |
| Week 3 | MessageBus & Session | 消息生命周期、会话隔离与持久化、多通道架构 |

---

## 🏗️ 综合项目：智能任务助手

### 项目目标

创建一个**任务管理 Skill**，用户可以通过对话：
- ✅ 添加任务（带优先级、截止日期）
- 📋 列出任务（按优先级/日期排序）
- ✔️ 完成任务
- 🔔 设置提醒（结合 cron）

### 架构设计

```
用户消息 → Channel → InboundMessage
                ↓
           MessageBus.publish_inbound()
                ↓
           AgentLoop 处理
                ↓
           TaskSkill 被激活 → TaskTool 执行
                ↓
           OutboundMessage → 用户收到响应
                ↓
           Session 持久化（任务数据）
```

---

## 📖 Part 1: 项目规划（2小时）

### 1.1 需求分析

**核心功能**：
```
用户: "添加一个任务：明天下午3点开会"
Agent: ✅ 已添加任务：
       - 内容：开会
       - 时间：明天 15:00
       - 优先级：普通

用户: "列出我的任务"
Agent: 📋 你的任务列表：
       1. [高] 完成报告 (今天 18:00)
       2. [中] 开会 (明天 15:00)
       3. [低] 买牛奶

用户: "完成任务1"
Agent: ✔️ 已完成「完成报告」
```

### 1.2 文件结构规划

```
nanobot/
├── skills/
│   └── task-manager/
│       ├── SKILL.md          # Skill 定义
│       └── task_store.py      # 任务存储逻辑
└── agent/tools/
    └── task.py               # TaskTool 实现
```

---

## 📖 Part 2: 实现 TaskTool（3小时）

### 2.1 Tool 基类回顾

```python
# nanobot/agent/tools/base.py
class Tool:
    """Base class for agent tools."""
    
    name: str           # 工具名称
    description: str    # 工具描述（LLM 使用）
    parameters: dict    # JSON Schema 参数定义
    
    async def execute(self, **params) -> str:
        """执行工具，返回结果字符串"""
        raise NotImplementedError
    
    def to_schema(self) -> dict:
        """生成 OpenAI 格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
```

### 2.2 TaskTool 实现

创建 `nanobot/agent/tools/task.py`：

```python
"""Task management tool for the agent."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from nanobot.agent.tools.base import Tool


class TaskTool(Tool):
    """Tool for managing tasks with priority and due dates."""
    
    name = "task"
    description = "管理用户任务：添加、列出、完成、删除任务"
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "complete", "delete"],
                "description": "要执行的操作"
            },
            "content": {
                "type": "string",
                "description": "任务内容（add 时必填）"
            },
            "priority": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "default": "medium",
                "description": "任务优先级"
            },
            "due_date": {
                "type": "string",
                "description": "截止日期，格式：YYYY-MM-DD HH:MM"
            },
            "task_id": {
                "type": "integer",
                "description": "任务ID（complete/delete 时必填）"
            }
        },
        "required": ["action"]
    }
    
    def __init__(self, session_id: str, storage_dir: Path | None = None):
        self.session_id = session_id
        self.storage_dir = storage_dir or Path.home() / ".nanobot" / "tasks"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_file = self.storage_dir / f"{session_id}.json"
    
    def _load_tasks(self) -> list[dict[str, Any]]:
        """从文件加载任务列表"""
        if not self._tasks_file.exists():
            return []
        return json.loads(self._tasks_file.read_text(encoding="utf-8"))
    
    def _save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        """保存任务列表到文件"""
        self._tasks_file.write_text(
            json.dumps(tasks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    async def execute(self, **params) -> str:
        """执行任务操作"""
        action = params.get("action")
        
        if action == "add":
            return self._add_task(params)
        elif action == "list":
            return self._list_tasks(params)
        elif action == "complete":
            return self._complete_task(params)
        elif action == "delete":
            return self._delete_task(params)
        else:
            return f"Error: 未知操作 '{action}'"
    
    def _add_task(self, params: dict) -> str:
        """添加新任务"""
        content = params.get("content")
        if not content:
            return "Error: 任务内容不能为空"
        
        tasks = self._load_tasks()
        
        # 生成新 ID
        new_id = max([t["id"] for t in tasks], default=0) + 1
        
        task = {
            "id": new_id,
            "content": content,
            "priority": params.get("priority", "medium"),
            "due_date": params.get("due_date"),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        tasks.append(task)
        self._save_tasks(tasks)
        
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        return f"✅ 已添加任务 #{new_id}:\n" \
               f"   - 内容：{content}\n" \
               f"   - 优先级：{priority_emoji.get(task['priority'], '🟡')} {task['priority']}\n" \
               f"   - 截止：{task['due_date'] or '未设置'}"
    
    def _list_tasks(self, params: dict) -> str:
        """列出所有任务"""
        tasks = self._load_tasks()
        
        if not tasks:
            return "📋 暂无任务"
        
        # 按优先级和日期排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tasks.sort(key=lambda t: (
            priority_order.get(t["priority"], 1),
            t.get("due_date") or "9999-99-99"
        ))
        
        lines = ["📋 你的任务列表：\n"]
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        
        for task in tasks:
            status = "✅" if task["status"] == "completed" else "⏳"
            emoji = priority_emoji.get(task["priority"], "🟡")
            due = f" ({task['due_date']})" if task.get("due_date") else ""
            lines.append(f"  {status} [{emoji}] #{task['id']}: {task['content']}{due}")
        
        return "\n".join(lines)
    
    def _complete_task(self, params: dict) -> str:
        """完成任务"""
        task_id = params.get("task_id")
        if task_id is None:
            return "Error: 请指定任务ID"
        
        tasks = self._load_tasks()
        
        for task in tasks:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                self._save_tasks(tasks)
                return f"✔️ 已完成任务 #{task_id}: {task['content']}"
        
        return f"Error: 未找到任务 #{task_id}"
    
    def _delete_task(self, params: dict) -> str:
        """删除任务"""
        task_id = params.get("task_id")
        if task_id is None:
            return "Error: 请指定任务ID"
        
        tasks = self._load_tasks()
        
        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                deleted = tasks.pop(i)
                self._save_tasks(tasks)
                return f"🗑️ 已删除任务 #{task_id}: {deleted['content']}"
        
        return f"Error: 未找到任务 #{task_id}"
```

---

## 📖 Part 3: 实现 TaskSkill（2小时）

### 3.1 Skill 格式回顾

Skill 是一个包含 `SKILL.md` 的目录，告诉 Agent 如何使用特定功能：

```markdown
---
name: skill-name
description: 简短描述
---

# Skill 标题

详细的使用说明...

## 使用场景
- 场景1
- 场景2

## 工具列表
- tool1: 说明
- tool2: 说明
```

### 3.2 创建 TaskSkill

创建 `nanobot/skills/task-manager/SKILL.md`：

```markdown
---
name: task-manager
description: 任务管理助手，帮助用户添加、查看、完成和删除任务
version: 1.0.0
author: learner
---

# 任务管理助手

你是一个任务管理助手，帮助用户管理日常待办事项。

## 功能

### 添加任务
当用户说类似以下内容时，使用 `task` 工具添加任务：
- "添加一个任务：..."
- "提醒我明天..."
- "我需要记住..."

参数：
- `action`: "add"
- `content`: 任务内容（必填）
- `priority`: "high" / "medium" / "low"（默认 medium）
- `due_date`: 截止日期，格式 YYYY-MM-DD HH:MM

### 列出任务
当用户问"我的任务"、"有什么待办"时，使用：
- `action`: "list"

### 完成任务
当用户说"完成任务X"、"做完了第X项"时，使用：
- `action`: "complete"
- `task_id`: 任务编号

### 删除任务
当用户说"删除任务X"、"取消第X项"时，使用：
- `action`: "delete"
- `task_id`: 任务编号

## 优先级处理

根据用户描述自动判断优先级：
- "紧急"、"重要"、"马上" → high
- "有空"、"不急" → low
- 其他 → medium

## 示例对话

用户: "添加一个任务：明天下午3点开会"
助手: [调用 task(action="add", content="开会", due_date="2024-01-15 15:00")]

用户: "列出我的任务"
助手: [调用 task(action="list")]

用户: "完成任务1"
助手: [调用 task(action="complete", task_id=1)]
```

---

## 📖 Part 4: 集成与测试（3小时）

### 4.1 注册 Tool

在 `nanobot/agent/tools/__init__.py` 中添加：

```python
from nanobot.agent.tools.task import TaskTool

__all__ = ["Tool", "ToolRegistry", "TaskTool"]
```

### 4.2 在 AgentLoop 中使用

```python
# 在 AgentLoop 初始化时注册 TaskTool
from nanobot.agent.tools import TaskTool

# 创建工具实例（需要 session_id）
task_tool = TaskTool(session_id=self.session_id)
self.tool_registry.register(task_tool)
```

### 4.3 测试脚本

创建 `learn-docs/week4_test.py`：

```python
"""Week 4 综合测试：TaskSkill 端到端测试"""

import asyncio
from pathlib import Path
from nanobot.agent.tools.task import TaskTool


async def test_task_tool():
    """测试 TaskTool 的基本功能"""
    
    # 使用测试 session
    session_id = "test-session-001"
    storage_dir = Path(__file__).parent / "test_tasks"
    
    tool = TaskTool(session_id=session_id, storage_dir=storage_dir)
    
    print("=" * 50)
    print("测试 1: 添加任务")
    print("=" * 50)
    
    result = await tool.execute(
        action="add",
        content="完成 Week 4 学习",
        priority="high",
        due_date="2024-01-20 18:00"
    )
    print(result)
    
    result = await tool.execute(
        action="add",
        content="复习 Week 1-3 内容",
        priority="medium"
    )
    print(result)
    
    result = await tool.execute(
        action="add",
        content="写学习笔记",
        priority="low"
    )
    print(result)
    
    print("\n" + "=" * 50)
    print("测试 2: 列出任务")
    print("=" * 50)
    
    result = await tool.execute(action="list")
    print(result)
    
    print("\n" + "=" * 50)
    print("测试 3: 完成任务")
    print("=" * 50)
    
    result = await tool.execute(action="complete", task_id=1)
    print(result)
    
    print("\n" + "=" * 50)
    print("测试 4: 再次列出任务")
    print("=" * 50)
    
    result = await tool.execute(action="list")
    print(result)
    
    print("\n" + "=" * 50)
    print("测试 5: 删除任务")
    print("=" * 50)
    
    result = await tool.execute(action="delete", task_id=3)
    print(result)
    
    print("\n" + "=" * 50)
    print("最终任务列表")
    print("=" * 50)
    
    result = await tool.execute(action="list")
    print(result)
    
    # 清理测试数据
    import shutil
    if storage_dir.exists():
        shutil.rmtree(storage_dir)
    print("\n✅ 测试完成，已清理测试数据")


if __name__ == "__main__":
    asyncio.run(test_task_tool())
```

---

## 📖 Part 5: 进阶功能（可选，2小时）

### 5.1 添加提醒功能

结合 `nanobot/cron/` 模块，实现定时提醒：

```python
# 在 TaskTool 中添加提醒功能
async def _schedule_reminder(self, task_id: int, remind_at: str) -> str:
    """安排任务提醒"""
    # 调用 cron 服务
    # ...
```

### 5.2 多 Session 支持

确保不同用户的任务隔离：

```python
# 每个 session 有独立的任务存储
self._tasks_file = self.storage_dir / f"{session_id}.json"
```

### 5.3 数据同步

添加导入/导出功能：

```python
def export_tasks(self) -> str:
    """导出任务为 JSON"""
    return json.dumps(self._load_tasks(), ensure_ascii=False, indent=2)

def import_tasks(self, data: str) -> str:
    """从 JSON 导入任务"""
    tasks = json.loads(data)
    self._save_tasks(tasks)
    return f"✅ 已导入 {len(tasks)} 个任务"
```

---

## ✅ 本周检查清单

### 理论理解
- [ ] 能解释 Tool 和 Skill 的关系
- [ ] 理解 ToolRegistry 的注册机制
- [ ] 掌握 JSON Schema 参数定义
- [ ] 理解 Session 与 Tool 的关联

### 代码实现
- [ ] TaskTool 类完整实现
- [ ] SKILL.md 文件编写
- [ ] 测试脚本运行成功
- [ ] 错误处理完善

### 集成测试
- [ ] Tool 成功注册到 Registry
- [ ] Agent 能正确调用 Tool
- [ ] 任务数据正确持久化
- [ ] 多 Session 隔离正常

---

## 🎓 学习成果

完成本周学习后，你将：

1. **掌握** nanobot 的完整开发流程
2. **能够** 独立创建新的 Tool 和 Skill
3. **理解** Agent 系统的端到端工作流
4. **具备** 扩展 nanobot 功能的能力

---

## 📚 扩展阅读

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [JSON Schema](https://json-schema.org/)
- nanobot 源码中的其他 Skill 实现

---

## 🚀 下一步

恭喜完成 4 周学习！你现在可以：

1. **深入源码**：阅读更多 nanobot 模块
2. **贡献代码**：为 nanobot 项目提交 PR
3. **创建项目**：基于 nanobot 构建自己的 Agent 应用
4. **探索生态**：学习更多 LLM 框架（LangChain、AutoGPT 等）

祝你在 AI Agent 开发的道路上越走越远！🎉