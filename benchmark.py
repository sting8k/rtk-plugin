#!/usr/bin/env python3
"""
Benchmark RTK filter with realistic outputs based on real session data.
Generates representative outputs matching actual agent usage patterns.
All paths, names, and identifiers are masked.
"""

import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "hooks"))
from importlib import import_module
rtk = import_module("rtk-filter")

random.seed(42)

def approx_tokens(text):
    return len(text) // 4


# ── Generators ───────────────────────────────────────────────────────────────

def gen_tsc_errors(n_errors=30):
    """Real pattern: tsc --noEmit producing many TS2307/TS7006 errors."""
    files = ["src/core/handler.ts", "src/api/client.ts", "src/utils/transform.ts",
             "src/hooks/useAuth.ts", "src/components/Dashboard.tsx"]
    error_types = [
        ("TS2307", "Cannot find module '{mod}' or its corresponding type declarations."),
        ("TS7006", "Parameter '{param}' implicitly has an 'any' type."),
        ("TS2345", "Argument of type 'string' is not assignable to parameter of type 'number'."),
        ("TS2339", "Property '{prop}' does not exist on type '{type}'."),
        ("TS2322", "Type '{a}' is not assignable to type '{b}'."),
    ]
    modules = ["@company/core-sdk", "@company/ui-lib", "@company/api-types", "fs", "path", "os"]
    params = ["event", "ctx", "response", "args", "callback", "config", "options", "data"]
    props = ["status", "metadata", "headers", "payload", "token", "sessionId"]
    types = ["UserConfig", "RequestContext", "ApiResponse", "SessionState"]
    lines = []
    for i in range(n_errors):
        f = files[i % len(files)]
        line_no = 10 + i * 8
        col = 5 + (i % 20)
        code, template = error_types[i % len(error_types)]
        msg = template.format(
            mod=modules[i % len(modules)], param=params[i % len(params)],
            prop=props[i % len(props)], type=types[i % len(types)],
            a="string | null", b="number"
        )
        lines.append(f"{f}({line_no},{col}): error {code}: {msg}")
    lines.append("")
    lines.append(f"Found {n_errors} errors in {len(files)} files.")
    return "\n".join(lines)

def gen_cargo_build(n_units=120, n_errors=3, n_warnings=5):
    """Real pattern: cargo build with Compiling lines + errors + warnings."""
    crates = [f"dep-crate-{i}" for i in range(20)] + ["my-project"]
    lines = []
    for i in range(n_units):
        c = crates[i % len(crates)]
        lines.append(f"   Compiling {c} v0.{i//10}.{i%10} (/workspace/{c})")
    for i in range(n_warnings):
        lines.append(f"warning: unused variable: `temp_{i}`")
        lines.append(f"  --> src/handlers/mod.rs:{50+i*10}:9")
        lines.append(f"   |")
        lines.append(f"{50+i*10} |     let temp_{i} = compute();")
        lines.append(f"   |         ^^^^^^^ help: if this is intentional, prefix it with an underscore: `_temp_{i}`")
        lines.append(f"   |")
        lines.append(f"   = note: `#[warn(unused_variables)]` on by default")
        lines.append("")
    for i in range(n_errors):
        lines.append(f"error[E0308]: mismatched types")
        lines.append(f"   --> src/core/engine.rs:{80+i*20}:17")
        lines.append(f"    |")
        lines.append(f"{80+i*20}  |     let result: Vec<u8> = process_input(data);")
        lines.append(f"    |                 ^^^^^^^^ expected `Vec<u8>`, found `Result<Vec<u8>, Error>`")
        lines.append(f"    |")
        lines.append(f"    = note: expected type `Vec<u8>`")
        lines.append(f"               found enum `Result<Vec<u8>, Error>`")
        lines.append(f"help: consider using `Result::unwrap`")
        lines.append("")
    lines.append(f"error: could not compile `my-project` (bin \"my-project\") due to {n_errors} previous errors; {n_warnings} warnings emitted")
    return "\n".join(lines)

def gen_vitest_pass(n_suites=13, n_tests=66):
    """Real pattern: vitest run with all passing -- based on actual vitest output."""
    lines = ["\n> project@0.1.0 test", "> vitest run", "",
             f" RUN  v3.2.4 /workspace/project", ""]
    test_names = ["unit/replay.test.ts", "unit/meta.test.ts", "unit/path.test.ts",
                  "unit/store.test.ts", "unit/diff.test.ts", "unit/tool.test.ts",
                  "unit/text.test.ts", "unit/index.test.ts",
                  "integration/restart.test.ts", "integration/refresh.test.ts",
                  "integration/navigation.test.ts", "integration/selective.test.ts",
                  "integration/boundary.test.ts"]
    tests_per = [14, 4, 8, 4, 3, 11, 5, 1, 2, 4, 2, 3, 5]
    total = 0
    for i in range(min(n_suites, len(test_names))):
        t = tests_per[i] if i < len(tests_per) else 3
        total += t
        ms = random.randint(3, 333)
        lines.append(f" \u2713 test/{test_names[i]} ({t} tests) {ms}ms")
    lines.append("")
    lines.append(f" Test Files  {n_suites} passed ({n_suites})")
    lines.append(f"      Tests  {total} passed ({total})")
    lines.append(f"   Start at  10:35:31")
    lines.append(f"   Duration  2.63s (transform 541ms, setup 0ms, collect 10.22s, tests 1.11s, environment 2ms, prepare 1.06s)")
    lines.append("")
    return "\n".join(lines)

def gen_go_test_verbose(n_pass=12, n_fail=2):
    """Real pattern: go test -v with JSON-heavy test output."""
    lines = []
    for i in range(n_pass):
        lines.append(f"=== RUN   TestHandler_Case{i}")
        lines.append(f"--- PASS: TestHandler_Case{i} (0.{random.randint(0,99):02d}s)")
    for i in range(n_fail):
        lines.append(f"=== RUN   TestTransform_Edge{i}")
        lines.append(f"    transform_test.go:{39+i}: expected {i+4} messages, got {i+3}:")
        # Realistic JSON blob in test output
        lines.append(f"        {{")
        lines.append(f'          "messages": [')
        lines.append(f"            {{")
        lines.append(f'              "content": "System prompt with instructions that span multiple lines and contain escaped characters like \\n and \\"quotes\\"...",')
        lines.append(f'              "role": "system"')
        lines.append(f"            }},")
        lines.append(f"            {{")
        lines.append(f'              "content": "User request here",')
        lines.append(f'              "role": "user"')
        lines.append(f"            }},")
        lines.append(f"            {{")
        lines.append(f'              "content": "Tool result content",')
        lines.append(f'              "role": "tool",')
        lines.append(f'              "tool_call_id": "call_abc_{i:03d}"')
        lines.append(f"            }}")
        lines.append(f"          ],")
        lines.append(f'          "model": "gpt-4",')
        lines.append(f'          "tools": [')
        lines.append(f"            {{")
        lines.append(f'              "function": {{')
        lines.append(f'                "description": "Request input from the user. Call this tool whenever you need clarification or confirmation before proceeding.",')
        lines.append(f'                "name": "user_input",')
        lines.append(f'                "parameters": {{')
        lines.append(f'                  "properties": {{')
        lines.append(f'                    "prompt": {{')
        lines.append(f'                      "description": "The question or prompt to present",')
        lines.append(f'                      "type": "string"')
        lines.append(f"                    }}")
        lines.append(f"                  }},")
        lines.append(f'                  "required": ["prompt"],')
        lines.append(f'                  "type": "object"')
        lines.append(f"                }}")
        lines.append(f"              }},")
        lines.append(f'              "type": "function"')
        lines.append(f"            }}")
        lines.append(f"          ]")
        lines.append(f"        }}")
        lines.append(f"--- FAIL: TestTransform_Edge{i} (0.01s)")
    lines.append(f"FAIL")
    lines.append(f"FAIL\tproject/internal/extensions/handler\t0.{random.randint(10,99)}s")
    lines.append(f"FAIL")
    return "\n".join(lines)

def gen_git_status_large(n_untracked=300):
    """Real pattern: git status in a project with many generated/untracked files."""
    lines = ["On branch main", "Your branch is up to date with 'origin/main'.", "",
             "Changes to be committed:", '  (use "git restore --staged <file>..." to unstage)', ""]
    staged = ["src/core/engine.ts", "src/api/routes.ts", "package.json"]
    for f in staged:
        lines.append(f"\tmodified:   {f}")
    lines.append("")
    lines.append("Changes not staged for commit:")
    lines.append('  (use "git add <file>..." to update what will be committed)')
    lines.append("")
    modified = ["README.md", "src/utils/helpers.ts", "tests/integration.test.ts"]
    for f in modified:
        lines.append(f"\tmodified:   {f}")
    lines.append("")
    lines.append("Untracked files:")
    lines.append('  (use "git add <file>..." to include in what will be committed)')
    lines.append("")
    dirs = ["components", "generated", "assets", "types", "screens", "layouts"]
    exts = [".ts", ".tsx", ".d.ts", ".css", ".json"]
    for i in range(n_untracked):
        d = dirs[i % len(dirs)]
        ext = exts[i % len(exts)]
        lines.append(f"\tsrc/{d}/auto_{i}{ext}")
    lines.append("")
    return "\n".join(lines)

def gen_git_log(n=25):
    """Real pattern: git log --oneline with realistic commit messages."""
    msgs = [
        "feat: add WebSocket reconnection with exponential backoff",
        "fix: resolve race condition in message queue processing",
        "refactor: extract shared validation into middleware layer",
        "chore: update dependencies to latest compatible versions",
        "feat(api): implement rate limiting with sliding window",
        "fix(auth): handle expired refresh tokens gracefully",
        "test: add integration tests for payment flow",
        "docs: update API reference with new endpoints",
        "perf: optimize database queries with proper indexing",
        "fix: prevent memory leak in event listener cleanup",
        "feat: add dark mode support with system preference detection",
        "refactor(core): simplify error handling with Result type",
        "ci: add parallel test execution in CI pipeline",
        "fix(ui): correct layout shift on dynamic content load",
        "feat: implement server-sent events for real-time updates",
    ]
    lines = []
    for i in range(n):
        h = f"{random.randint(0, 0xFFFFFFF):07x}"
        lines.append(f"{h} {msgs[i % len(msgs)]}")
    return "\n".join(lines)

def gen_git_diff_real(n_files=6, hunks_per_file=3, ctx_lines=3):
    """Real pattern: git diff with TypeScript/Go code changes."""
    files_content = [
        ("src/core/handler.ts", [
            ("function processRequest(ctx: Context) {", [
                ("-  const timeout = 5000;", "+  const timeout = ctx.config.timeout ?? 10000;"),
                ("-  const retries = 3;", "+  const retries = ctx.config.maxRetries ?? 5;"),
                ("-  logger.info('Processing request');", "+  logger.info('Processing request', { requestId: ctx.id, timeout, retries });"),
            ]),
            ("async function validateInput(data: unknown) {", [
                ("-  if (!data) throw new Error('Missing data');",
                 "+  if (!data) {\n+    throw new ValidationError('Missing required input data', {\n+      code: 'MISSING_DATA',\n+      field: 'root',\n+    });\n+  }"),
            ]),
        ]),
        ("src/api/routes.ts", [
            ("router.post('/webhook', async (req, res) => {", [
                ("-  const payload = req.body;", "+  const payload = parseWebhookPayload(req.body);"),
                ("-  await processWebhook(payload);",
                 "+  try {\n+    await processWebhook(payload);\n+  } catch (err) {\n+    logger.error('Webhook processing failed', { error: err, payload: payload.id });\n+    return res.status(500).json({ error: 'Internal error' });\n+  }"),
                ("-  res.json({ ok: true });", "+  res.json({ ok: true, processedAt: new Date().toISOString() });"),
            ]),
        ]),
        ("internal/runtime/executor.go", [
            ("func (e *Executor) Run(ctx context.Context) error {", [
                ("-\tresult, err := e.process(ctx)",
                 "+\tresult, err := e.process(ctx)\n+\tif err != nil {\n+\t\te.metrics.RecordError(ctx, err)\n+\t\treturn fmt.Errorf(\"executor run failed: %w\", err)\n+\t}"),
            ]),
            ("func (e *Executor) Shutdown() {", [
                ("-\te.cancel()", "+\te.cancel()\n+\te.wg.Wait()\n+\te.logger.Info(\"executor shutdown complete\")"),
            ]),
        ]),
    ]
    lines = []
    for fname, hunks in files_content[:n_files]:
        lines.append(f"diff --git a/{fname} b/{fname}")
        lines.append(f"index abc1234..def5678 100644")
        lines.append(f"--- a/{fname}")
        lines.append(f"+++ b/{fname}")
        for h_idx, (header, changes) in enumerate(hunks[:hunks_per_file]):
            start = 20 + h_idx * 40
            lines.append(f"@@ -{start},{10+len(changes)*3} +{start},{10+len(changes)*5} @@ {header}")
            for i in range(ctx_lines):
                lines.append(f"   // context line {i}")
            for old, new in changes:
                for l in old.split("\n"):
                    lines.append(l)
                for l in new.split("\n"):
                    lines.append(l)
                for i in range(min(2, ctx_lines)):
                    lines.append(f"   // more context")
    return "\n".join(lines)

def gen_eslint_real(n_issues=45, n_files=12):
    """Real pattern: eslint output with various rules."""
    rules = [
        ("@typescript-eslint/no-explicit-any", "Unexpected any. Specify a different type"),
        ("react-hooks/exhaustive-deps", "React Hook useEffect has a missing dependency: 'config'"),
        ("@typescript-eslint/no-unused-vars", "'tempResult' is defined but never used"),
        ("import/order", "Import in wrong order. 'react' should be before './utils'"),
        ("no-console", "Unexpected console statement"),
        ("@typescript-eslint/no-non-null-assertion", "Forbidden non-null assertion"),
        ("prefer-const", "'handler' is never reassigned. Use 'const' instead"),
    ]
    dirs = ["components", "hooks", "utils", "api", "core", "pages"]
    lines = []
    for i in range(n_issues):
        d = dirs[i % len(dirs)]
        f = f"src/{d}/Module{i % n_files}.tsx"
        line = 10 + (i * 7) % 200
        col = 1 + i % 40
        rule_name, msg = rules[i % len(rules)]
        lines.append(f"{f}:{line}:{col}: warning {msg} [{rule_name}]")
    lines.append("")
    lines.append(f"\u2716 {n_issues} problems ({n_issues} warnings)")
    return "\n".join(lines)

def gen_rg_search_real(n_matches=60, n_files=15):
    """Real pattern: rg search with code results across files."""
    dirs = ["src/core", "src/api", "src/utils", "src/hooks", "src/components",
            "internal/runtime", "internal/extensions", "pkg/config"]
    fnames = ["handler", "client", "transform", "validator", "manager",
              "executor", "processor", "factory", "registry", "resolver"]
    exts = [".ts", ".tsx", ".go", ".rs"]
    lines = []
    code_patterns = [
        "export async function processRequest(ctx: RequestContext, options: ProcessOptions = {}) {",
        "  const result = await handler.execute(input, { timeout: config.timeout, retries: 3 });",
        "func (s *Server) HandleRequest(ctx context.Context, req *Request) (*Response, error) {",
        "pub async fn process_batch(items: Vec<WorkItem>, config: &Config) -> Result<BatchResult> {",
        "  return this.registry.resolve(name)?.create(ctx) ?? throwNotFound(name);",
        "  const [state, dispatch] = useReducer(reducer, { loading: true, data: null, error: null });",
        "  if err := s.validator.Validate(ctx, req); err != nil { return nil, fmt.Errorf(\"validation: %w\", err) }",
        "  export type RequestHandler<T = unknown> = (ctx: Context, input: T) => Promise<Result<T>>;",
    ]
    for i in range(n_matches):
        d = dirs[i % len(dirs)]
        f = fnames[i % len(fnames)]
        ext = exts[i % len(exts)]
        line_no = 10 + (i * 13) % 500
        code = code_patterns[i % len(code_patterns)]
        lines.append(f"{d}/{f}{ext}:{line_no}:{code}")
    return "\n".join(lines)

def gen_ls_la_real(n_dirs=6, n_files=18):
    """Real pattern: ls -la with real-looking directory listing."""
    noise_dirs = ["node_modules", ".git", "__pycache__", "dist", ".next", ".cache"]
    real_dirs = ["src", "tests", "scripts", "docs", "configs"]
    lines = [f"total {(n_dirs + n_files) * 8}"]
    lines.append("drwxr-xr-x  24 user  staff    768 Mar 28 14:30 .")
    lines.append("drwxr-xr-x   8 user  staff    256 Mar 20 10:15 ..")
    for d in noise_dirs[:n_dirs // 2]:
        sz = random.randint(128, 4096)
        lines.append(f"drwxr-xr-x  {random.randint(3,20):>2} user  staff  {sz:>5} Mar {random.randint(1,28):>2} {random.randint(8,22):02d}:{random.randint(0,59):02d} {d}")
    for d in real_dirs[:n_dirs - n_dirs // 2]:
        sz = random.randint(96, 512)
        lines.append(f"drwxr-xr-x  {random.randint(3,12):>2} user  staff  {sz:>5} Mar {random.randint(1,28):>2} {random.randint(8,22):02d}:{random.randint(0,59):02d} {d}")
    file_entries = [
        (".eslintrc.json", 342), (".gitignore", 89), (".prettierrc", 156),
        ("README.md", 4521), ("package.json", 2890), ("package-lock.json", 891234),
        ("tsconfig.json", 567), ("vitest.config.ts", 312), ("Cargo.toml", 1243),
        ("Cargo.lock", 45678), ("go.mod", 890), ("go.sum", 34567),
        ("Makefile", 2345), ("Dockerfile", 1567), (".env.example", 234),
        ("LICENSE", 1087), ("CHANGELOG.md", 8901), ("docker-compose.yml", 1456),
    ]
    for name, size in file_entries[:n_files]:
        lines.append(f"-rw-r--r--   1 user  staff  {size:>7} Mar {random.randint(1,28):>2} {random.randint(8,22):02d}:{random.randint(0,59):02d} {name}")
    return "\n".join(lines)

def gen_cat_typescript(n_lines=80):
    """Real pattern: cat of a TypeScript source file with comments and imports."""
    lines = [
        "// Copyright 2024 Project Authors. All rights reserved.",
        "// Licensed under the MIT License. See LICENSE for details.",
        "",
        "/**",
        " * RequestHandler manages incoming API requests with validation,",
        " * rate limiting, authentication, and error handling middleware.",
        " *",
        " * @module core/handler",
        " * @since 1.0.0",
        " */",
        "",
        "import { Context, Next } from '../types/context';",
        "import { Logger } from '../utils/logger';",
        "import { RateLimiter } from '../middleware/rate-limiter';",
        "import { validateSchema } from '../validation/schema';",
        "import { AuthManager } from '../auth/manager';",
        "import { MetricsCollector } from '../telemetry/metrics';",
        "import type { RequestConfig, HandlerOptions } from '../types/config';",
        "",
        "// Default configuration for request handling",
        "const DEFAULT_TIMEOUT = 30000;",
        "const MAX_RETRIES = 3;",
        "const BACKOFF_BASE = 1000;",
        "",
        "/**",
        " * Create a new request handler with the given configuration.",
        " *",
        " * @param config - Handler configuration options",
        " * @param logger - Logger instance for request tracing",
        " * @returns Configured request handler function",
        " *",
        " * @example",
        " * ```typescript",
        " * const handler = createHandler({",
        " *   timeout: 5000,",
        " *   retries: 2,",
        " * }, logger);",
        " * ```",
        " */",
        "export function createHandler(",
        "  config: RequestConfig,",
        "  logger: Logger,",
        "): (ctx: Context, next: Next) => Promise<void> {",
        "  // Initialize rate limiter with configured limits",
        "  const limiter = new RateLimiter({",
        "    windowMs: config.rateLimitWindow ?? 60000,",
        "    maxRequests: config.rateLimitMax ?? 100,",
        "  });",
        "",
        "  // Set up authentication if configured",
        "  const auth = config.authEnabled",
        "    ? new AuthManager(config.authConfig)",
        "    : null;",
        "",
        "  // Create metrics collector for observability",
        "  const metrics = new MetricsCollector('handler');",
        "",
        "  return async (ctx: Context, next: Next) => {",
        "    const startTime = Date.now();",
        "    const requestId = ctx.headers['x-request-id'] ?? generateId();",
        "",
        "    // Log incoming request",
        "    logger.info('Request received', {",
        "      requestId,",
        "      method: ctx.method,",
        "      path: ctx.path,",
        "      userAgent: ctx.headers['user-agent'],",
        "    });",
        "",
        "    try {",
        "      // Check rate limit",
        "      await limiter.check(ctx.ip);",
        "",
        "      // Authenticate if required",
        "      if (auth) {",
        "        const token = ctx.headers.authorization?.replace('Bearer ', '');",
        "        ctx.user = await auth.verify(token);",
        "      }",
        "",
        "      // Validate request body against schema",
        "      if (config.schema) {",
        "        validateSchema(ctx.body, config.schema);",
        "      }",
        "",
        "      // Execute handler with timeout",
        "      await Promise.race([",
        "        next(),",
        "        new Promise((_, reject) =>",
        "          setTimeout(() => reject(new Error('Handler timeout')),",
        "            config.timeout ?? DEFAULT_TIMEOUT)",
        "        ),",
        "      ]);",
        "",
        "      // Record success metrics",
        "      metrics.record('request.success', Date.now() - startTime);",
        "    } catch (error) {",
        "      // Record error metrics",
        "      metrics.record('request.error', Date.now() - startTime);",
        "",
        "      // Log error with context",
        "      logger.error('Request failed', {",
        "        requestId,",
        "        error: error instanceof Error ? error.message : 'Unknown error',",
        "        stack: error instanceof Error ? error.stack : undefined,",
        "      });",
        "",
        "      throw error;",
        "    }",
        "  };",
        "}",
    ]
    return "\n".join(lines[:n_lines])

def gen_npm_install():
    """Real pattern: npm install with many packages."""
    lines = []
    pkgs = ["@types/node", "typescript", "vitest", "eslint", "@typescript-eslint/parser",
            "prettier", "react", "react-dom", "@types/react", "next",
            "tailwindcss", "postcss", "autoprefixer", "zod", "drizzle-orm",
            "pg", "redis", "ioredis", "express", "@types/express",
            "winston", "pino", "jose", "bcryptjs", "dotenv"]
    for p in pkgs:
        v = f"{random.randint(1,18)}.{random.randint(0,30)}.{random.randint(0,15)}"
        lines.append(f"added {p}@{v}")
    lines.append("")
    lines.append(f"added {len(pkgs)} packages, and audited {len(pkgs) + random.randint(200,800)} packages in {random.randint(5,30)}s")
    lines.append("")
    lines.append(f"{random.randint(0,5)} vulnerabilities found")
    return "\n".join(lines)


# ── Benchmark ────────────────────────────────────────────────────────────────

BENCHMARKS = [
    ("tsc --noEmit (30 errors)", "npx tsc --noEmit", gen_tsc_errors),
    ("cargo build (120 units, 3 err, 5 warn)", "cargo build", gen_cargo_build),
    ("vitest (13 suites, 66 pass)", "npm test", gen_vitest_pass),
    ("go test -v (12 pass, 2 fail)", "go test ./... -v", gen_go_test_verbose),
    ("git status (300 untracked)", "git status", gen_git_status_large),
    ("git log --oneline (25)", "git log --oneline -25", gen_git_log),
    ("git diff (6 files, multi-hunk)", "git diff", gen_git_diff_real),
    ("eslint (45 issues, 12 files)", "npx eslint src/", gen_eslint_real),
    ("rg search (60 matches, 15 files)", "rg processRequest src/", gen_rg_search_real),
    ("ls -la (24 entries)", "ls -la", gen_ls_la_real),
    ("cat source.ts (80 lines)", "cat src/core/handler.ts", gen_cat_typescript),
    ("npm install (25 packages)", "npm install", gen_npm_install),
]

def main():
    print(f"{'Category':<42} {'Original':>10} {'Filtered':>10} {'Saved':>8} {'Reduction':>10}")
    print("-" * 85)

    total_orig = 0
    total_filt = 0

    for label, cmd, gen_fn in BENCHMARKS:
        raw = gen_fn()
        filtered = rtk.filter_output(raw, cmd)
        orig_tok = approx_tokens(raw)
        filt_tok = approx_tokens(filtered)
        saved = orig_tok - filt_tok
        pct = (saved / orig_tok * 100) if orig_tok > 0 else 0
        total_orig += orig_tok
        total_filt += filt_tok
        print(f"{label:<42} {orig_tok:>8}tk {filt_tok:>8}tk {saved:>6}tk {pct:>8.1f}%")

    total_saved = total_orig - total_filt
    total_pct = (total_saved / total_orig * 100) if total_orig > 0 else 0
    print("-" * 85)
    print(f"{'TOTAL':<42} {total_orig:>8}tk {total_filt:>8}tk {total_saved:>6}tk {total_pct:>8.1f}%")

if __name__ == "__main__":
    main()
