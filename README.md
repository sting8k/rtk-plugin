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

## License

MIT
