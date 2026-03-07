#!/usr/bin/env python3
"""Test script for CountLinesTool."""

import asyncio
import tempfile
from pathlib import Path

from nanobot.agent.tools.filesystem import CountLinesTool
from nanobot.agent.tools.registry import ToolRegistry


async def test_count_lines_tool():
    """Test the CountLinesTool with a temporary file."""
    # Create a temporary file with known content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("line 1\n")
        f.write("line 2\n")
        f.write("line 3\n")
        f.write("line 4\n")
        temp_file_path = Path(f.name)

    try:
        # Initialize tool registry and register CountLinesTool
        registry = ToolRegistry()
        tool = CountLinesTool(workspace=temp_file_path.parent, allowed_dir=temp_file_path.parent)
        registry.register(tool)

        # Test valid call
        result = await registry.execute("count_lines", {"path": str(temp_file_path)})
        print(f"Result for valid file: {result}")
        assert "4 lines in" in result, f"Expected '4 lines in...', got '{result}'"

        # Test invalid parameter (missing path)
        result = await registry.execute("count_lines", {})
        print(f"Result for missing path: {result}")
        assert "Invalid parameters" in result, f"Expected validation error, got '{result}'"

        # Test invalid parameter (wrong type)
        result = await registry.execute("count_lines", {"path": 123})
        print(f"Result for wrong type: {result}")
        assert "Invalid parameters" in result, f"Expected validation error, got '{result}'"

        # Test non-existent file (within allowed dir)
        nonexistent_path = temp_file_path.parent / "nonexistent.txt"
        result = await registry.execute("count_lines", {"path": str(nonexistent_path)})
        print(f"Result for non-existent file: {result}")
        assert "File not found" in result, f"Expected file not found error, got '{result}'"

        print("✅ All tests passed!")

    finally:
        # Clean up
        temp_file_path.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_count_lines_tool())