#!/usr/bin/env python3
"""
RTK (Result Token Killer) filter for Droid hooks.
Ported from pi-ctx-kit/rtk — reduces token consumption by filtering tool output.

Usage as Droid PreToolUse hook:
  Wraps Execute commands so their stdout/stderr passes through this filter.
  The hook JSON output uses updatedInput to rewrite the command.

Usage standalone (for testing):
  echo "some output" | python3 rtk-filter.py "the-original-command"
"""

import sys
import re
import os
import json

# ── Config ────────────────────────────────────────────────────────────────────

MAX_LINE_LENGTH = 180
TRIMMED_LINE_LENGTH = 150
HEAD_RATIO = 0.8
MAX_TOTAL_LINES = 2000
MIN_LINES_TO_TRIM = 20
MIN_DEDUP_LINES = 50
MIDDLE_TRUNCATE_MAX_CHARS = 40000

# ── ANSI stripping ───────────────────────────────────────────────────────────

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]"
    r"|\x1b[()#][A-B0-2]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[@-Z\\^_`a-z{|}~]"
)

def strip_ansi(text):
    if "\x1b" not in text:
        return text
    return _ANSI_RE.sub("", text)

# ── Command detection ────────────────────────────────────────────────────────

RUNNER_PREFIXES = {"npx", "bunx", "pnpx", "sudo", "env", "time", "nice", "nohup", "xargs", "exec", "command"}

def parse_segments(command):
    parts = re.split(r"&&|\|\||;", command)
    return [p.strip() for p in parts if p.strip()]

def parse_pipeline(segment):
    parts = re.split(r"(?<!\|)\|(?!\|)", segment)
    return [p.strip() for p in parts if p.strip()]

def get_command_name(segment):
    tokens = segment.split()
    i = 0
    while i < len(tokens):
        t = tokens[i].lower()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
            i += 1
            continue
        if t in RUNNER_PREFIXES:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
            continue
        break
    if i >= len(tokens):
        return ""
    return os.path.basename(tokens[i]).lower()

def command_matches(command, patterns):
    if not command:
        return False
    segments = parse_segments(command)
    for seg in segments:
        for pipe_seg in parse_pipeline(seg):
            tokens = pipe_seg.split()
            i = 0
            while i < len(tokens):
                t = tokens[i].lower()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
                    i += 1; continue
                if t in RUNNER_PREFIXES:
                    i += 1
                    while i < len(tokens) and tokens[i].startswith("-"):
                        i += 1
                    continue
                break
            if i >= len(tokens):
                continue
            cmd_name = os.path.basename(tokens[i]).lower()
            cmd_with_arg = f"{cmd_name} {tokens[i+1]}" if i + 1 < len(tokens) else cmd_name
            for pat in patterns:
                pat_lower = pat.lower()
                if " " in pat_lower:
                    if cmd_with_arg.lower() == pat_lower:
                        return True
                else:
                    if cmd_name == pat_lower:
                        return True
    return False

# ── Build output filtering ───────────────────────────────────────────────────

BUILD_COMMANDS = [
    "cargo build", "cargo check", "bun build", "npm run build",
    "yarn build", "pnpm build", "tsc", "make", "cmake",
    "gradle", "mvn", "go build", "go install",
]

SKIP_PATTERNS = [
    re.compile(r"^\s*(Compiling|Checking|Downloading|Downloaded|Fetching|Fetched|Updating|Updated|Building|Generated|Creating|Running)\s+"),
]
ERROR_START = [re.compile(r"^error\["), re.compile(r"^error:"), re.compile(r"^\[ERROR\]"), re.compile(r"^FAIL")]
WARNING_PAT = [re.compile(r"^warning:"), re.compile(r"^\[WARNING\]"), re.compile(r"^warn:")]

def is_build_command(cmd):
    return command_matches(cmd, BUILD_COMMANDS)

def filter_build_output(output, cmd):
    lines = output.split("\n")
    compiled = 0
    errors = []
    warnings = []
    in_error = False
    current_error = []
    blank_count = 0

    for line in lines:
        if re.match(r"^\s*(Compiling|Checking|Building)\s+", line):
            compiled += 1; continue
        if any(p.match(line) for p in SKIP_PATTERNS):
            continue
        if any(p.match(line) for p in ERROR_START):
            if in_error and current_error:
                errors.append(current_error[:])
            in_error = True
            current_error = [line]
            blank_count = 0
            continue
        if any(p.match(line) for p in WARNING_PAT):
            warnings.append(line); continue
        if in_error:
            if not line.strip():
                blank_count += 1
                if blank_count >= 2 and len(current_error) > 3:
                    errors.append(current_error[:])
                    in_error = False; current_error = []
                else:
                    current_error.append(line)
            elif re.match(r"^\s", line) or line.startswith("-->"):
                current_error.append(line); blank_count = 0
            else:
                errors.append(current_error[:])
                in_error = False; current_error = []

    if in_error and current_error:
        errors.append(current_error)

    if not errors and not warnings:
        return f"Build OK ({compiled} units compiled)"

    result = []
    if errors:
        result.append(f"{len(errors)} error(s):")
        for err in errors[:5]:
            result.extend(err[:10])
            if len(err) > 10:
                result.append("  ...")
        if len(errors) > 5:
            result.append(f"... and {len(errors) - 5} more errors")
    if warnings:
        result.append(f"\n{len(warnings)} warning(s)")
    return "\n".join(result)

# ── Test output aggregation ──────────────────────────────────────────────────

TEST_COMMANDS = ["test", "jest", "vitest", "pytest", "cargo test", "bun test", "go test", "mocha", "ava", "tap"]

TEST_RESULT_PATTERNS = [
    re.compile(r"test result:\s*(?:\w+)\.\s*(\d+)\s*passed;\s*(\d+)\s*failed;"),
    re.compile(r"(\d+)\s*passed(?:,\s*(\d+)\s*failed)?(?:,\s*(\d+)\s*skipped)?", re.I),
    re.compile(r"(\d+)\s*pass(?:,\s*(\d+)\s*fail)?(?:,\s*(\d+)\s*skip)?", re.I),
    re.compile(r"tests?:\s*(\d+)\s*passed(?:,\s*(\d+)\s*failed)?(?:,\s*(\d+)\s*skipped)?", re.I),
]

FAILURE_START = [
    re.compile(r"^FAIL\s+"), re.compile(r"^FAILED\s+"),
    re.compile(r"^\s*[●]\s+"), re.compile(r"^\s*[✕]\s+"),
    re.compile(r"test\s+\w+\s+\.\.\.\s*FAILED"),
    re.compile(r"thread\s+'\w+'\s+panicked"),
]

def is_test_command(cmd):
    return command_matches(cmd, TEST_COMMANDS)

def aggregate_test_output(output, cmd):
    passed = failed = skipped = 0
    for pat in TEST_RESULT_PATTERNS:
        m = pat.search(output)
        if m:
            passed = int(m.group(1) or 0)
            failed = int(m.group(2) or 0) if m.lastindex >= 2 and m.group(2) else 0
            skipped = int(m.group(3) or 0) if m.lastindex >= 3 and m.group(3) else 0
            break

    if passed == 0 and failed == 0:
        for line in output.split("\n"):
            if re.search(r"\b(ok|PASS|✓|✔)\b", line):
                passed += 1
            if re.search(r"\b(FAIL|fail|✗|✕)\b", line):
                failed += 1

    if passed == 0 and failed == 0 and skipped == 0:
        return None

    failures = []
    if failed > 0:
        in_failure = False
        current = []
        blank_count = 0
        for line in output.split("\n"):
            if any(p.match(line) for p in FAILURE_START):
                if in_failure and current:
                    failures.append("\n".join(current))
                in_failure = True
                current = [line]; blank_count = 0; continue
            if in_failure:
                if not line.strip():
                    blank_count += 1
                    if blank_count >= 2 and len(current) > 3:
                        failures.append("\n".join(current))
                        in_failure = False; current = []
                    else:
                        current.append(line)
                elif re.match(r"^\s", line) or line.startswith("-"):
                    current.append(line); blank_count = 0
                else:
                    failures.append("\n".join(current))
                    in_failure = False; current = []
        if in_failure and current:
            failures.append("\n".join(current))

    result = [f"Test Results: {passed} passed"]
    if failed > 0:
        result[0] += f", {failed} failed"
    if skipped > 0:
        result[0] += f", {skipped} skipped"

    if failed > 0 and failures:
        result.append("\nFailures:")
        for f in failures[:5]:
            lines = f.split("\n")
            result.append(f"  - {lines[0][:70]}{'...' if len(lines[0]) > 70 else ''}")
            for l in lines[1:4]:
                if l.strip():
                    result.append(f"    {l[:65]}{'...' if len(l) > 65 else ''}")
            if len(lines) > 4:
                result.append(f"    ... ({len(lines) - 4} more lines)")
        if len(failures) > 5:
            result.append(f"  ... and {len(failures) - 5} more failures")

    return "\n".join(result)

# ── Git compaction ───────────────────────────────────────────────────────────

GIT_COMMANDS = [
    "git diff", "git status", "git log", "git show", "git stash",
    "git add", "git commit", "git push", "git pull", "git fetch", "git branch",
]

def is_git_command(cmd):
    return command_matches(cmd, GIT_COMMANDS)

def is_git_patch_command(cmd):
    return command_matches(cmd, ["git diff", "git show"])

def compact_status(output):
    lines = output.split("\n")
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        return "Clean working tree"
    staged_files = []
    modified_files = []
    untracked_files = []
    branch = ""
    for line in lines:
        if line.startswith("##"):
            m = re.match(r"## (.+)", line)
            if m:
                branch = m.group(1).split("...")[0]
            continue
        if len(line) < 3:
            continue
        status = line[:2]
        fname = line[3:]
        if status[0] in "MADRC":
            staged_files.append(fname)
        if status[1] in "MD":
            modified_files.append(fname)
        if status == "??":
            untracked_files.append(fname)

    result = f"{branch}\n"
    if staged_files:
        result += f"Staged: {len(staged_files)} files\n"
        for f in staged_files[:5]:
            result += f"  {f}\n"
        if len(staged_files) > 5:
            result += f"  ... +{len(staged_files) - 5} more\n"
    if modified_files:
        result += f"Modified: {len(modified_files)} files\n"
        for f in modified_files[:5]:
            result += f"  {f}\n"
        if len(modified_files) > 5:
            result += f"  ... +{len(modified_files) - 5} more\n"
    if untracked_files:
        result += f"Untracked: {len(untracked_files)} files\n"
        for f in untracked_files[:3]:
            result += f"  {f}\n"
        if len(untracked_files) > 3:
            result += f"  ... +{len(untracked_files) - 3} more\n"
    return result.strip()

def compact_log(output, limit=20):
    lines = output.split("\n")
    result = []
    for line in lines[:limit]:
        result.append(line[:77] + "..." if len(line) > 80 else line)
    if len(lines) > limit:
        result.append(f"... and {len(lines) - limit} more commits")
    return "\n".join(result)

def compact_add(output):
    t = output.strip()
    if not t or "nothing specified" in t:
        return "ok"
    return t

def compact_commit(output):
    for line in output.split("\n"):
        m = re.match(r"^\[[\w/.-]+\s+([a-f0-9]{7,})\]\s+(.+)", line)
        if m:
            return f"ok {m.group(1)} {m.group(2)}"
    if "nothing to commit" in output:
        return "ok (nothing to commit)"
    return output.strip()

def compact_push(output):
    if "Everything up-to-date" in output:
        return "ok (up-to-date)"
    for line in output.split("\n"):
        m = re.search(r"\s+(\S+)\s*->\s*(\S+)", line)
        if m:
            return f"ok {m.group(2)}"
    if any(w in output for w in ("error", "rejected", "failed")):
        return output.strip()
    return output.strip() or "ok"

def compact_pull(output):
    if "Already up to date" in output or "Already up-to-date" in output:
        return "ok (up-to-date)"
    m = re.search(r"(\d+)\s+files?\s+changed(?:,\s*(\d+)\s+insertions?\(\+\))?(?:,\s*(\d+)\s+deletions?\(-\))?", output)
    if m:
        return f"ok {m.group(1)} files +{m.group(2) or '0'} -{m.group(3) or '0'}"
    if any(w in output for w in ("CONFLICT", "error", "fatal")):
        return output.strip()
    return output.strip() or "ok"

def compact_fetch(output):
    new_refs = sum(1 for l in output.split("\n") if "->" in l or "[new" in l)
    if new_refs > 0:
        return f"ok fetched ({new_refs} new refs)"
    return "ok fetched"

def compact_git_output(output, cmd):
    cl = cmd.lower()
    if "git status" in cl:
        return compact_status(output)
    if "git log" in cl:
        return compact_log(output)
    if "git add" in cl:
        return compact_add(output)
    if "git commit" in cl:
        return compact_commit(output)
    if "git push" in cl:
        return compact_push(output)
    if "git pull" in cl:
        return compact_pull(output)
    if "git fetch" in cl:
        return compact_fetch(output)
    return None

# ── Linter aggregation ───────────────────────────────────────────────────────

LINTER_COMMANDS = ["eslint", "prettier", "ruff", "pylint", "mypy", "flake8", "black", "clippy", "golangci-lint"]

def is_linter_command(cmd):
    return command_matches(cmd, LINTER_COMMANDS)

def aggregate_linter_output(output, cmd):
    issues = []
    for line in output.split("\n"):
        m = re.match(r"^(.+):(\d+):(\d+):\s*(.+)$", line)
        if m:
            rule_m = re.search(r"\[(.+?)\]$", m.group(4))
            issues.append({
                "file": m.group(1), "line": int(m.group(2)),
                "message": m.group(4), "rule": rule_m.group(1) if rule_m else "unknown",
            })

    if not issues:
        cl = cmd.lower()
        linter = "Linter"
        for name in ("eslint", "ruff", "pylint", "mypy", "flake8", "clippy", "golangci", "prettier"):
            if name in cl:
                linter = name.capitalize(); break
        return f"{linter}: No issues found"

    by_file = {}
    by_rule = {}
    for iss in issues:
        by_file.setdefault(iss["file"], []).append(iss)
        by_rule[iss["rule"]] = by_rule.get(iss["rule"], 0) + 1

    result = f"{len(issues)} issues in {len(by_file)} files\n"
    top_rules = sorted(by_rule.items(), key=lambda x: -x[1])[:10]
    result += "Top rules:\n"
    for rule, count in top_rules:
        result += f"  {rule} ({count}x)\n"
    result += "\nTop files:\n"
    top_files = sorted(by_file.items(), key=lambda x: -len(x[1]))[:10]
    for f, file_issues in top_files:
        result += f"  {f} ({len(file_issues)} issues)\n"
    return result

# ── Search result grouping ───────────────────────────────────────────────────

SEARCH_COMMANDS = ["grep", "rg", "find", "ack", "ag"]

def is_search_command(cmd):
    return command_matches(cmd, SEARCH_COMMANDS)

def group_search_results(output, max_results=50):
    results = []
    for line in output.split("\n"):
        if not line.strip():
            continue
        m = re.match(r"^(.+?):(\d+)?:(.+)$", line)
        if m:
            results.append({"file": m.group(1), "line": m.group(2) or "?", "content": m.group(3)})
    if not results:
        return None

    by_file = {}
    for r in results:
        by_file.setdefault(r["file"], []).append(r)

    out = f"{len(results)} matches in {len(by_file)} files:\n\n"
    shown = 0
    for f in sorted(by_file.keys()):
        if shown >= max_results:
            break
        matches = by_file[f]
        out += f"{f} ({len(matches)} matches):\n"
        for match in matches[:10]:
            content = match["content"].strip()[:70]
            out += f"    {match['line']}: {content}\n"
            shown += 1
        if len(matches) > 10:
            out += f"  +{len(matches) - 10} more\n"
        out += "\n"
    if len(results) > shown:
        out += f"... +{len(results) - shown} more\n"
    return out

# ── ls/tree compaction ───────────────────────────────────────────────────────

NOISE_DIRS = {
    "node_modules", ".git", "target", "__pycache__", ".next", "dist", "build",
    ".cache", ".turbo", ".vercel", ".pytest_cache", ".mypy_cache", ".tox",
    ".venv", "venv", "env", ".env", "coverage", ".nyc_output",
    ".DS_Store", "Thumbs.db", ".idea", ".vscode", ".vs", ".eggs",
}
MONTHS = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}

def is_ls_command(cmd):
    if not cmd:
        return False
    for seg in re.split(r"&&|\|\||;", cmd):
        parts = seg.strip().split()
        if not parts:
            continue
        c = os.path.basename(parts[0]).lower()
        if c == "ls" and any(p.startswith("-") and "l" in p for p in parts):
            return True
    return False

def has_show_all_flag(cmd):
    for seg in re.split(r"&&|\|\||;", cmd):
        parts = seg.strip().split()
        if not parts:
            continue
        c = os.path.basename(parts[0]).lower()
        if c == "ls":
            return any((p.startswith("-") and not p.startswith("--") and "a" in p) or p == "--all" for p in parts)
    return False

def human_size(b):
    if b >= 1048576:
        return f"{b/1048576:.1f}M"
    if b >= 1024:
        return f"{b/1024:.1f}K"
    return f"{b}B"

def parse_size(field):
    suffixes = {"K": 1024, "M": 1048576, "G": 1073741824}
    if field and field[-1].upper() in suffixes:
        try:
            return round(float(field[:-1]) * suffixes[field[-1].upper()])
        except ValueError:
            return 0
    try:
        return int(field)
    except (ValueError, TypeError):
        return 0

def compact_ls(raw, show_all=False):
    dirs = []
    files = []
    by_ext = {}
    for line in raw.split("\n"):
        if line.startswith("total ") or not line.strip():
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        month_idx = -1
        for i in range(3, len(parts) - 3):
            if parts[i] in MONTHS:
                month_idx = i; break
        if month_idx < 1:
            continue
        size_field = parts[month_idx - 1]
        name = " ".join(parts[month_idx + 3:])
        if not name or name in (".", ".."):
            continue
        if not show_all and name in NOISE_DIRS:
            continue
        if parts[0].startswith("d"):
            dirs.append(name)
        elif parts[0].startswith("-") or parts[0].startswith("l"):
            b = parse_size(size_field)
            ext = name[name.rfind("."):] if "." in name else "no ext"
            by_ext[ext] = by_ext.get(ext, 0) + 1
            files.append({"name": name, "size": human_size(b)})

    if not dirs and not files:
        return "(empty)\n"

    out = ""
    for d in dirs:
        out += f"{d}/\n"
    for f in files:
        out += f"{f['name']}  {f['size']}\n"
    ext_counts = sorted(by_ext.items(), key=lambda x: -x[1])
    ext_parts = [f"{c} {e}" for e, c in ext_counts[:5]]
    summary = f"{len(files)} files, {len(dirs)} dirs"
    if ext_parts:
        summary += f" ({', '.join(ext_parts)}"
        if len(ext_counts) > 5:
            summary += f", +{len(ext_counts) - 5} more"
        summary += ")"
    out += f"\n{summary}\n"
    return out

def is_tree_command(cmd):
    if not cmd:
        return False
    for seg in re.split(r"&&|\|\||;", cmd):
        parts = seg.strip().split()
        if parts and os.path.basename(parts[0]).lower() == "tree":
            return True
    return False

def filter_tree(raw):
    lines = []
    for line in raw.split("\n"):
        if "director" in line and "file" in line:
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"

# ── Dedup consecutive similar lines ──────────────────────────────────────────

MIN_MATCH_CHARS = 15
MIN_MATCH_RATIO = 0.7
MAX_LENGTH_RATIO = 1.5

def extract_pattern(a, b):
    if not a and not b:
        return None
    max_len = max(len(a), len(b))
    min_len = min(len(a), len(b))
    if min_len > 0 and max_len / min_len > MAX_LENGTH_RATIO:
        return None
    prefix_len = 0
    min_total = min(len(a), len(b))
    while prefix_len < min_total and a[prefix_len] == b[prefix_len]:
        prefix_len += 1
    suffix_len = 0
    while suffix_len < min_total - prefix_len and a[-(suffix_len+1)] == b[-(suffix_len+1)]:
        suffix_len += 1
    fixed_chars = prefix_len + suffix_len
    if fixed_chars < MIN_MATCH_CHARS:
        return None
    if max_len > 0 and fixed_chars / max_len < MIN_MATCH_RATIO:
        return None
    return {"prefix": a[:prefix_len], "suffix": a[-suffix_len:] if suffix_len > 0 else "", "fixed_chars": fixed_chars}

def matches_pattern(line, pattern):
    return line.startswith(pattern["prefix"]) and (not pattern["suffix"] or line.endswith(pattern["suffix"]))

def dedup_consecutive(lines, min_run):
    if len(lines) < min_run:
        return lines, 0
    result = []
    deduped = 0
    i = 0
    while i < len(lines):
        pattern = None
        if i + 1 < len(lines):
            pattern = extract_pattern(lines[i], lines[i+1])
        if not pattern:
            result.append(lines[i]); i += 1; continue
        run_end = i + 2
        while run_end < len(lines) and matches_pattern(lines[run_end], pattern):
            run_end += 1
        run_len = run_end - i
        if run_len < min_run:
            for j in range(i, run_end):
                result.append(lines[j])
            i = run_end; continue
        result.append(lines[i])
        pat_display = pattern["prefix"] + "*" + pattern["suffix"]
        result.append(f"[x {run_len - 1} similar: {pat_display}]")
        deduped += run_len - 1
        i = run_end
    return result, deduped

# ── Middle truncation ────────────────────────────────────────────────────────

def middle_truncate(text, max_chars, head_ratio=0.75):
    if len(text) <= max_chars:
        return text
    head_chars = int(max_chars * head_ratio)
    tail_chars = max_chars - head_chars
    head = text[:head_chars]
    tail = text[-tail_chars:]
    removed = len(text) - max_chars
    return f"{head}\n[... truncated {removed} chars from middle ...]\n{tail}"

# ── Column trimming ─────────────────────────────────────────────────────────

def col_trim_lines(lines, max_line_length, trimmed_line_length, head_ratio):
    result = []
    trimmed_count = 0
    for line in lines:
        if len(line) <= max_line_length:
            result.append(line); continue
        head_keep = round(trimmed_line_length * head_ratio)
        tail_keep = round(trimmed_line_length * (1 - head_ratio))
        head = line[:head_keep]
        tail = line[-tail_keep:] if tail_keep > 0 else ""
        result.append(f"{head} [...] {tail}")
        trimmed_count += 1
    return result, trimmed_count

# ── Row trimming ─────────────────────────────────────────────────────────────

def trim_rows(lines, max_lines, head_ratio=0.8):
    if len(lines) <= max_lines:
        return lines, 0
    head_count = int(max_lines * head_ratio)
    tail_count = max_lines - head_count
    omitted = len(lines) - head_count - tail_count
    return (
        lines[:head_count] + [f"[... {omitted} lines omitted ...]"] + lines[-tail_count:],
        omitted,
    )

# ── Diff detection ───────────────────────────────────────────────────────────

def looks_like_diff(lines):
    markers = 0
    for line in lines[:40]:
        if any(line.startswith(p) for p in ("diff --git ", "--- a/", "+++ b/", "@@ ")):
            markers += 1
            if markers >= 2:
                return True
    return False

# ── Main filter pipeline ────────────────────────────────────────────────────

def filter_output(text, command):
    if not text:
        return text
    original = text
    techniques = []

    # 1. ANSI stripping
    stripped = strip_ansi(text)
    if stripped != text:
        text = stripped
        techniques.append("ansi")

    # 2. Semantic filters based on command type
    if is_build_command(command):
        out = filter_build_output(text, command)
        if out and out != text:
            text = out
            techniques.append("build")

    elif is_test_command(command):
        out = aggregate_test_output(text, command)
        if out and out != text:
            text = out
            techniques.append("test")

    elif is_git_command(command) and not is_git_patch_command(command):
        out = compact_git_output(text, command)
        if out and out != text:
            text = out
            techniques.append("git")

    elif is_linter_command(command):
        out = aggregate_linter_output(text, command)
        if out and out != text:
            text = out
            techniques.append("linter")

    elif is_search_command(command):
        out = group_search_results(text)
        if out and out != text:
            text = out
            techniques.append("search")

    elif is_ls_command(command):
        show_all = has_show_all_flag(command)
        out = compact_ls(text, show_all)
        if out != text:
            text = out
            techniques.append("ls")

    elif is_tree_command(command):
        out = filter_tree(text)
        if out != text:
            text = out
            techniques.append("tree")

    # 3. Generic pipeline: column trim -> dedup -> row trim
    lines = text.split("\n")

    if not looks_like_diff(lines):
        lines, col_trimmed = col_trim_lines(lines, MAX_LINE_LENGTH, TRIMMED_LINE_LENGTH, HEAD_RATIO)
        if col_trimmed > 0:
            techniques.append("col-trim")

        lines, deduped = dedup_consecutive(lines, MIN_DEDUP_LINES)
        if deduped > 0:
            techniques.append("dedup")

    lines, omitted = trim_rows(lines, MAX_TOTAL_LINES, HEAD_RATIO)
    if omitted > 0:
        techniques.append("row-trim")

    text = "\n".join(lines)

    # 4. Safety net: middle truncation
    if len(text) > MIDDLE_TRUNCATE_MAX_CHARS:
        text = middle_truncate(text, MIDDLE_TRUNCATE_MAX_CHARS)
        techniques.append("truncate")

    return text

# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        # Standalone mode: just filter stdin
        text = sys.stdin.read()
        sys.stdout.write(filter_output(text, ""))
        return

    mode = sys.argv[1]

    if mode == "hook":
        # Droid hook mode: read JSON from stdin, output JSON to stdout
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)

        tool_name = input_data.get("tool_name", "")
        if tool_name != "Execute":
            sys.exit(0)

        tool_input = input_data.get("tool_input", {})
        command = tool_input.get("command", "")

        if not command:
            sys.exit(0)

        script_path = os.path.abspath(__file__)
        # Pass the original command via env var to avoid shell injection.
        # The filter reads RTK_ORIG_CMD from env instead of argv.
        # Save fd2 to fd3 so filter's stderr goes to real stderr, not through pipe.
        import shlex
        quoted_script = shlex.quote(script_path)
        wrapped = f'exec 3>&2; export RTK_ORIG_CMD={shlex.quote(command)}; {{ {command} ; }} 2>&1 | python3 {quoted_script} filter-env 2>&3; exec 3>&-'

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "RTK: wrapping command output through filter",
                "updatedInput": {
                    "command": wrapped,
                },
            }
        }
        json.dump(output, sys.stdout)

    elif mode == "filter-env":
        # Filter mode (safe): read command from env var, output from stdin
        command = os.environ.get("RTK_ORIG_CMD", "")
        text = sys.stdin.read()
        sys.stdout.write(filter_output(text, command))

    elif mode == "filter":
        # Filter mode (legacy/testing): read command from argv, output from stdin
        raw_cmd = sys.argv[2] if len(sys.argv) > 2 else ""
        try:
            command = json.loads(raw_cmd)
        except (json.JSONDecodeError, ValueError):
            command = raw_cmd
        text = sys.stdin.read()
        sys.stdout.write(filter_output(text, command))

    else:
        # Treat argv[1] as command for standalone testing
        text = sys.stdin.read()
        sys.stdout.write(filter_output(text, mode))


if __name__ == "__main__":
    main()
