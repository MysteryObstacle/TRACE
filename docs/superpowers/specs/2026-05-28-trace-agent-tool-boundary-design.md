# TRACE Agent Tool Boundary Design

Status: approved for implementation

## Context

`demo-008` failed in the physical stage with `ValueError("unknown inspect view: nodes")`. The more important finding is upstream: logical builder and repair agents can currently run full validation inside a single ReAct node. Builder/repair prompts explicitly ask agents to call `validate_graph`, and `execute_mutation_file(validate=true)` also runs full validation including checkpoint files. That lets one agent session loop on validation and repair internally, bypassing the intended LangGraph boundary of `builder -> validator -> repair -> validator`.

This design restores stage ownership:

- builder/repair agents produce one successful artifact change;
- validator nodes run the full F1-F4 validation and decide graph routing;
- repair agents decide when a semantic issue should escalate;
- tool returns stay compact enough to avoid poisoning model context.

## Decisions

### Builder And Repair Boundary

Builder and repair nodes may perform multiple mutation attempts only until one mutation is successfully applied. A failed apply, such as a syntax error, runtime exception, unsafe path, or invalid graph update, remains inside the same node so the agent can correct the mutation file.

Once a mutation successfully applies, the node must stop and return control to LangGraph. Checkpoint-only repair follows the same rule: once `write_checkpoint_file` succeeds, the repair node must stop and return control to the validator.

### Validation Ownership

`execute_mutation_file` defaults to `validate=false` in the agent tool. It executes and applies the mutation transactionally, but does not run checkpoint/F4 validation by default.

Builder and repair agents do not receive the `validate_graph` tool. Full validation is owned by logical/physical validator nodes. This keeps retry limits, stage snapshots, nested checkpoints, and repair memory under LangGraph control.

### Escalation Ownership

Validator nodes do not infer or originate escalation decisions. Validator routing is limited to finalize, repair, and fail-on-attempt-limit. If validation output contains an escalation-shaped issue, repair sees it in `evaluation_report` and decides whether to return an explicit stage escalation.

### Tool Result Shape

Agent-facing mutation execution returns compact payloads:

- success: `ok`, `path`, `applied`, `summary`;
- failure: `ok=false`, `path`, `applied=false`, `issues`, `summary`, and only failed operation details when available;
- full `operations` and full `graph` require explicit debug/include flags.

The ledger stores low-entropy repair history: issue kinds before/after, produced files, mutation summaries, failed actions, and snapshot paths. It is not a conversation memory and should not store complete graph JSON or full operation lists.

### Documentation Access

Do not add a separate `read_agent_doc` tool. `read_support_file` becomes a unified read-only file reader for:

- run support files such as `ground/logical_constraints.json` and `logical/checkpoints.py`;
- agent docs under a `docs/` namespace such as `docs/tgraph_view_api.md`.

`list_support_files` returns both groups. Bare doc names such as `tgraph_view_api.md` may be accepted as aliases for `docs/tgraph_view_api.md` to avoid agent dead ends.

### Error Containment

Stage tools must not raise recoverable user/tool errors into the LangGraph runtime. `inspect_graph(view="nodes")` and other unknown views return `{ok:false, allowed_views:[...]}` or a supported alias response instead of raising `ValueError`.

### API Drift

TGraph docs and checkpoint helper APIs must align. `demo-008` exposed checkpoint code that treated `check_interface(...)` as if it returned a port dict and called non-existent helpers such as `ip_in_subnet`. The docs should steer authors toward supported helpers (`check_interface`, `ports`, `ip_in_cidr`) and valid return shapes.

## Expected Result

After implementation, a demo run should show:

- builder writes and applies at most one successful mutation, then exits;
- validator runs checkpoint files after builder/repair exits;
- repair receives fresh validation reports in a new node invocation;
- physical tool mistakes no longer crash the stage;
- agent traces contain summaries and ledgers, not large operation dumps.
