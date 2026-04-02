#!/usr/bin/env python3
"""
Tilth nudge hook for Droid.
Appends a hint to tool results when the user is doing code reading/searching
through Execute shell commands or Droid's Read/Grep tools.

PostToolUse hook: reads JSON from stdin, exits 0 with stdout for transcript,
or exits 2 with stderr to feed back to Droid.
"""

import json
import re
import sys

NUDGE_CMD = re.compile(r"(?:^|\|)\s*(rg|ripgrep|grep|egrep|fgrep|cat|head|tail|less|find|fd|locate)\s")
REMOTE_CMD = re.compile(r"(?:^|\s)(ssh|sshpass|scp|rsync|docker\s+exec|kubectl\s+exec|nohup\s+ssh)\s")

HINT = "\n\n[tilth] Hint: consider using the `tilth` skill instead of raw shell commands for code reading/searching — it provides AST-aware results with better context."

def should_nudge_execute(tool_input):
    command = tool_input.get("command", "")
    if not isinstance(command, str):
        return False
    if not NUDGE_CMD.search(command):
        return False
    if REMOTE_CMD.search(command):
        return False
    return True

def should_nudge_read(tool_input):
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    return isinstance(file_path, str) and bool(file_path.strip())

def should_nudge_grep(tool_input):
    pattern = tool_input.get("pattern", "")
    return isinstance(pattern, str) and bool(pattern.strip())

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    should_nudge = False
    if tool_name == "Execute":
        should_nudge = should_nudge_execute(tool_input)
    elif tool_name == "Read":
        should_nudge = should_nudge_read(tool_input)
    elif tool_name == "Grep":
        should_nudge = should_nudge_grep(tool_input)

    if not should_nudge:
        sys.exit(0)

    print(HINT.strip(), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
