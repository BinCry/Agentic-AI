# Official Coding-Agent Capability Study

## Decision

Reference mature agents for behavior and safety invariants, not source layout or feature count. Preserve Agentic-AI's durable Python state, repository grounding, approval records, checkpoints, and D-drive workspace policy. The shortest viable route to a useful coding agent is: project instructions, policy-governed execution, an iterative action loop, visible/resumable sessions, then real task evaluation.

## Current Baseline

Agentic-AI already has a durable workflow state machine, validated structured decisions, external skill catalogs, repository retrieval, a read-only analysis path, allowlisted repository/test/Git tools, approval records, checkpoint recovery, JSONL traces, OpenAI-compatible providers, an MCP server, and 150 passing tests at the latest verified baseline.

Verified gaps:

| Capability | Current evidence | Consequence |
|---|---|---|
| General command execution | Only fixed Python test profiles; no generic command tool | Cannot install, lint, build, or run project-native workflows |
| Project instructions | External skill root only; no hierarchical AGENTS/CLAUDE discovery | Agent misses repository-specific constraints |
| Iterative action loop | Rigid decision-per-state orchestration | Weak adaptation to tool observations and long tasks |
| Context accounting | Character truncation; provider usage discarded | No token/cost budget or durable observation references |
| Session UX | Terminal result JSON only | Long runs look stalled; cancellation/progress are poor |
| MCP consumption | MCP server exists; no client/discovery | Cannot safely use external tools |
| Git delivery | Status/diff/changed-files are read-only | Cannot branch, commit, or prepare delivery under approval |
| Real issue evaluation | Retrieval metrics and stored-state aggregates | Cannot measure whether code tasks are actually solved |
| Language coverage | Python AST symbol search and Python test detection | Node and other common repositories get shallow support |

## Adapted Lessons From Official Sources

| Source | Proven idea | Adaptation here | Explicit non-goal |
|---|---|---|---|
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | Plan/read-only mode, hierarchical policy, sessions, MCP, telemetry | Layered instructions, approval modes, command-prefix policy, session events, stdio MCP | Rebuilding its TypeScript UI or provider stack |
| [Gemini policy engine](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/policy-engine.md) | Rules match tool, arguments, environment, and mode with allow/deny/ask | Typed local rules compiled into deterministic decisions | Free-form executable policy code |
| [Gemini shell tool](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/shell.md) | Prefix allowlisting and sandbox guidance | Tokenized argv, executable resolution, deny metacharacters, optional sandbox backend | Arbitrary shell strings in the first release |
| [Gemini sessions](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md) | Resume/checkpoint lifecycle | Durable event cursor, cancel intent, resume/report commands | Rich interactive TUI |
| [OpenAI Codex](https://github.com/openai/codex) | Streaming exec, approvals, config layers, MCP, Windows sandbox | Process events, layered policy, explicit remote-effect approvals | Rust rewrite or broad computer-use tools |
| [Codex security](https://developers.openai.com/codex/security) | Separate sandbox reach from approval authority | Independent execution boundary and human approval decision | Treating approval as a sandbox replacement |
| [Codex exec policy](https://developers.openai.com/codex/exec-policy) | Command policy is inspectable and testable | `policy check` CLI and rule fixtures | Hidden model-only policy decisions |
| [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk) | Workspace, event, tool, and conversation boundaries | Small repository-native protocols for workspaces/events/tools | Agent Canvas, cloud control plane, or Kubernetes runtime |
| [OpenClaw](https://github.com/openclaw/openclaw) | Capability manifests and plugin/skill boundaries | Declarative extension metadata plus least-privilege registration | Messaging gateway, channels, or personal-assistant scope |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | Agent-computer interface quality matters more than framework size | Keep tools few, typed, and feedback-rich | Huge tool catalog without benchmark evidence |
| [SWE-bench](https://github.com/SWE-bench/SWE-bench) | Reproducible issue-to-patch evaluation | Optional verified subset after local golden tasks | Mandatory Docker use on a C-filled Windows machine |
| [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) | End-to-end terminal task measurement | Late optional compatibility lane | Running before sandbox and D-drive cache verification |

## Scope Challenge

The assumption that a coding agent becomes "perfect" by matching every competitor feature is rejected. Feature parity would increase attack surface, context cost, and maintenance before proving task success. A safe execution interface plus realistic evaluation has higher leverage than multi-channel gateways, multi-agent coordination, browser automation, or a polished TUI.

Three approaches were considered:

| Approach | Complexity | Time to useful capability | Safety/maintenance | Decision |
|---|---:|---:|---:|---|
| Copy a mature architecture | Very high | Slow | High migration and compatibility risk | Reject |
| Add isolated missing features | Medium | Fast initially | Fragmented contracts and weak evaluation | Reject as primary strategy |
| Evolve the existing core through measured capability slices | Medium | Fast per slice | Lowest migration risk; every slice benchmarked | Select |

Second-order effects: general execution makes every later integration more powerful and more dangerous, so policy and observability precede it. MCP expands trust boundaries, so it follows typed events and command safety. Git write operations create external/reputation impact, so they remain a separate late phase. External benchmarks can fill disks and run untrusted containers, so local golden tasks come first and all caches must resolve to D.

## Capability Gates

1. No command capability without deterministic policy tests.
2. No new durable field without schema migration and round-trip fixtures.
3. No context compaction change without citation/observation retention tests.
4. No long-running feature without progress, timeout, cancellation, and recovery tests.
5. No MCP or Git write tool without explicit trust/approval boundaries.
6. No "complete" claim without issue-to-patch golden-task results.

## Success Metrics

- Safety: 100% denial for path escape, unapproved writes, shell metacharacter injection, secret-bearing environment forwarding, and remote Git operations in negative fixtures.
- Reliability: deterministic resume after interruption at every mutating boundary; no duplicate side effects.
- Usefulness: local golden Python and Node tasks reach expected patch and test result under fixed budgets.
- Observability: every model call, policy decision, command lifecycle, approval, and state transition has a correlated event.
- Efficiency: context and command output stay within configured byte/token budgets and preserve cited evidence.

## Unresolved Questions

None required to begin. Remote MCP transports, container sandbox provider, and broader benchmark sets are conditional decisions made only after local phase metrics.
