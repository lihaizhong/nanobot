"""Week 4 综合测试：TaskSkill 端到端测试

运行方式：
    cd /Users/lihaizhong/Documents/Project/ForkSource/nanobot
    python -m learn-docs.week4_test

或者：
    python learn-docs/week4_test.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_task_tool():
    """测试 TaskTool 的基本功能"""

    # 导入 TaskTool（如果已实现）
    try:
        from nanobot.agent.tools.task import TaskTool
    except ImportError:
        print("⚠️ TaskTool 尚未实现")
        print("请按照 WEEK4_GUIDE.md 的指引创建 TaskTool")
        return

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


async def test_tool_schema():
    """测试 Tool 的 JSON Schema 生成"""

    try:
        from nanobot.agent.tools.task import TaskTool
    except ImportError:
        print("⚠️ TaskTool 尚未实现")
        return

    tool = TaskTool(session_id="test")

    print("=" * 50)
    print("Tool Schema (OpenAI 格式)")
    print("=" * 50)

    import json
    schema = tool.to_schema()
    print(json.dumps(schema, indent=2, ensure_ascii=False))


async def test_skill_loading():
    """测试 Skill 加载"""

    from nanobot.agent.skills import SkillsLoader

    print("=" * 50)
    print("Skills 加载测试")
    print("=" * 50)

    loader = SkillsLoader(workspace=project_root)
    skills = loader.list_skills()

    print(f"发现 {len(skills)} 个 Skills:\n")
    for skill in skills:
        print(f"  - {skill['name']} ({skill['source']})")

    # 检查 task-manager skill
    task_skill = loader.load_skill("task-manager")
    if task_skill:
        print("\n✅ task-manager Skill 已创建")
        print("\nSkill 内容预览:")
        print("-" * 30)
        print(task_skill[:500] + "..." if len(task_skill) > 500 else task_skill)
    else:
        print("\n⚠️ task-manager Skill 尚未创建")
        print("请按照 WEEK4_GUIDE.md 创建 skills/task-manager/SKILL.md")


async def main():
    """主测试入口"""

    print("🚀 Week 4 综合测试")
    print("=" * 50)
    print()

    # 测试 1: Skill 加载
    await test_skill_loading()
    print()

    # 测试 2: Tool Schema
    await test_tool_schema()
    print()

    # 测试 3: Tool 功能
    await test_task_tool()


if __name__ == "__main__":
    asyncio.run(main())