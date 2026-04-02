# rtk-plugin

A Droid plugin that reduces token consumption by intelligently filtering and compacting tool output before it reaches the model's context window.

## Features

- Filters build output (cargo, npm, tsc, make, go, gradle) down to errors and warnings
- Aggregates test results (jest, pytest, vitest, cargo test) into pass/fail summaries
- Compacts git output (status, log, commit, push, pull, fetch)
- Summarizes linter output (eslint, ruff, pylint, mypy, clippy) by rule and file
- Groups search results (grep, rg, find) by file
- Compacts `ls -la` and `tree` output, filtering noise directories
- Deduplicates consecutive similar lines
- Strips ANSI escape codes
- Trims long lines and truncates excessive output

## Installation

```sh
droid plugin marketplace add https://github.com/sting8k/rtk-plugin
droid plugin install rtk-plugin@rtk-plugin
```

Restart Droid for the hook to take effect.

To update later:

```sh
droid plugin update rtk-plugin@rtk-plugin
```

## How It Works

The plugin registers a `PreToolUse` hook on the `Execute` tool. When Droid runs a shell command, the hook wraps the command's stdout/stderr through `rtk-filter.py`, which detects the command type and applies the appropriate filter before the output enters the context window.

For example, a `cargo build` with 200 lines of "Compiling..." messages and 2 errors becomes:

```
2 error(s):
error[E0308]: mismatched types
  --> src/main.rs:42:5
  ...
```

A `git status` with 30 files becomes:

```
main
Staged: 3 files
  src/lib.rs
  src/main.rs
  Cargo.toml
Modified: 2 files
  README.md
  tests/test.rs
```

## Supported Commands

| Category | Commands |
|----------|----------|
| Build | `cargo build`, `npm run build`, `tsc`, `make`, `go build`, `gradle`, `mvn` |
| Test | `jest`, `pytest`, `vitest`, `cargo test`, `go test`, `mocha` |
| Git | `git status`, `git log`, `git diff`, `git commit`, `git push`, `git pull` |
| Lint | `eslint`, `ruff`, `pylint`, `mypy`, `clippy`, `golangci-lint` |
| Search | `grep`, `rg`, `find`, `ack`, `ag` |
| Files | `ls -l`, `tree` |

Commands not matching any category still get generic filtering: ANSI stripping, line dedup, column/row trimming, and middle truncation.

## Benchmark

Token savings measured with realistic outputs modeled on real agent sessions (`python3 benchmark.py`):

| Command | Original | Filtered | Saved | Reduction |
|---------|----------|----------|-------|-----------|
| `tsc --noEmit` (30 errors) | 805 tk | 141 tk | 664 tk | 82.5% |
| `cargo build` (120 units, 3 err, 5 warn) | 2,335 tk | 84 tk | 2,251 tk | 96.4% |
| `go test -v` (12 pass, 2 fail) | 874 tk | 23 tk | 851 tk | 97.4% |
| `vitest` (13 suites, 66 pass) | 214 tk | 214 tk | 0 tk | 0.0% |
| `git status` (300 untracked) | 2,088 tk | 17 tk | 2,071 tk | 99.2% |
| `git log` (25 commits) | 384 tk | 318 tk | 66 tk | 17.2% |
| `git diff` (6 files, multi-hunk) | 636 tk | 374 tk | 262 tk | 41.2% |
| `eslint` (45 issues, 12 files) | 1,228 tk | 156 tk | 1,072 tk | 87.3% |
| `rg` search (60 matches, 15 files) | 1,770 tk | 1,344 tk | 426 tk | 24.1% |
| `ls -la` (24 entries) | 384 tk | 116 tk | 268 tk | 69.8% |
| `cat` source.ts (80 lines) | 581 tk | 478 tk | 103 tk | 17.7% |
| **Total** | **11,299 tk** | **3,265 tk** | **8,034 tk** | **70.1%** |

Token count approximated as `len(text) / 4`. Compact outputs (e.g. vitest with only summary lines) are passed through unchanged.

## License

MIT
