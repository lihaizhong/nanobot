"""Task management tool for CRUD operations on tasks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class TaskTool(Tool):
    """
    Tool for managing tasks with CRUD operations.
    
    Tasks are stored in a JSON file with the following structure:
    {
        "tasks": [
            {
                "id": "task_1",
                "title": "Task title",
                "description": "Task description",
                "status": "pending|in_progress|completed",
                "priority": "low|medium|high",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        ]
    }
    """

    def __init__(self, workspace: Path | None = None, data_file: str = "tasks.json"):
        """
        Initialize TaskTool.
        
        Args:
            workspace: Workspace directory for storing task data.
            data_file: Name of the JSON file for task storage.
        """
        self._workspace = workspace or Path.cwd()
        self._data_file = self._workspace / data_file
        self._ensure_data_file()

    def _ensure_data_file(self) -> None:
        """Ensure the data file exists with initial structure."""
        if not self._data_file.exists():
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_tasks({"tasks": []})

    def _load_tasks(self) -> dict[str, Any]:
        """Load tasks from JSON file."""
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"tasks": []}

    def _save_tasks(self, data: dict[str, Any]) -> None:
        """Save tasks to JSON file."""
        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _generate_id(self) -> str:
        """Generate a unique task ID."""
        data = self._load_tasks()
        existing_ids = {task["id"] for task in data["tasks"]}
        counter = len(data["tasks"]) + 1
        while f"task_{counter}" in existing_ids:
            counter += 1
        return f"task_{counter}"

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return "Manage tasks with add, list, complete, and delete operations."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "complete", "delete"],
                    "description": "The action to perform on tasks",
                },
                "title": {
                    "type": "string",
                    "description": "Task title (required for 'add' action)",
                },
                "description": {
                    "type": "string",
                    "description": "Task description (optional for 'add' action)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Task priority (default: medium)",
                },
                "task_id": {
                    "type": "string",
                    "description": "Task ID (required for 'complete' and 'delete' actions)",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed"],
                    "description": "Filter tasks by status (optional for 'list' action)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Execute the task action."""
        action = kwargs.get("action")

        if action == "add":
            return self._add_task(kwargs)
        elif action == "list":
            return self._list_tasks(kwargs)
        elif action == "complete":
            return self._complete_task(kwargs)
        elif action == "delete":
            return self._delete_task(kwargs)
        else:
            return f"Error: Unknown action '{action}'"

    def _add_task(self, kwargs: dict[str, Any]) -> str:
        """Add a new task."""
        title = kwargs.get("title")
        if not title:
            return "Error: 'title' is required for adding a task"

        data = self._load_tasks()
        now = datetime.now().isoformat()
        
        task = {
            "id": self._generate_id(),
            "title": title,
            "description": kwargs.get("description", ""),
            "status": "pending",
            "priority": kwargs.get("priority", "medium"),
            "created_at": now,
            "updated_at": now,
        }
        
        data["tasks"].append(task)
        self._save_tasks(data)
        
        priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        emoji = priority_emoji.get(task["priority"], "🟡")
        
        return f"✅ Task created: {emoji} [{task['id']}] {title}\n   Priority: {task['priority']}\n   Status: pending"

    def _list_tasks(self, kwargs: dict[str, Any]) -> str:
        """List all tasks or filter by status."""
        data = self._load_tasks()
        tasks = data["tasks"]
        
        # Filter by status if provided
        status_filter = kwargs.get("status")
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]
        
        if not tasks:
            if status_filter:
                return f"No tasks found with status '{status_filter}'"
            return "No tasks found. Use 'add' action to create a task."
        
        priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}
        
        lines = ["📋 Task List:", ""]
        for task in tasks:
            p_emoji = priority_emoji.get(task["priority"], "🟡")
            s_emoji = status_emoji.get(task["status"], "⏳")
            lines.append(f"  {p_emoji} {s_emoji} [{task['id']}] {task['title']}")
            if task.get("description"):
                lines.append(f"      └─ {task['description']}")
        
        lines.append("")
        lines.append(f"Total: {len(tasks)} task(s)")
        return "\n".join(lines)

    def _complete_task(self, kwargs: dict[str, Any]) -> str:
        """Mark a task as completed."""
        task_id = kwargs.get("task_id")
        if not task_id:
            return "Error: 'task_id' is required for completing a task"

        data = self._load_tasks()
        
        for task in data["tasks"]:
            if task["id"] == task_id:
                if task["status"] == "completed":
                    return f"Task [{task_id}] is already completed"
                task["status"] = "completed"
                task["updated_at"] = datetime.now().isoformat()
                self._save_tasks(data)
                return f"✅ Task [{task_id}] '{task['title']}' marked as completed!"
        
        return f"Error: Task '{task_id}' not found"

    def _delete_task(self, kwargs: dict[str, Any]) -> str:
        """Delete a task."""
        task_id = kwargs.get("task_id")
        if not task_id:
            return "Error: 'task_id' is required for deleting a task"

        data = self._load_tasks()
        
        for i, task in enumerate(data["tasks"]):
            if task["id"] == task_id:
                deleted_title = task["title"]
                del data["tasks"][i]
                self._save_tasks(data)
                return f"🗑️ Task [{task_id}] '{deleted_title}' deleted successfully"
        
        return f"Error: Task '{task_id}' not found"