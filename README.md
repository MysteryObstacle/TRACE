# TRACE

TRACE is a staged agent runtime for turning user intent into topology artifacts. The current `v0` focus is not full IaC generation yet. It is a runnable, testable control plane for:

- `ground -> logical -> physical -> translate_stub`
- explicit artifact passing between stages
- validator-driven retries in `logical` and `physical`
- LangChain-backed execution by default, with explicit fake mode still available for tests and controlled runs
- LangSmith-backed tracing across root runs, stage runs, agent calls, patch application, and validation

## Current Status

What is working now:

- CLI entrypoints: `run` and `resume`
- three-stage pipeline with stage ordering and stage-local contracts
- artifact persistence with versioned writes and latest-version selector reads
- `ground` node pattern expansion such as `PLC[1..3] -> PLC1, PLC2, PLC3`
- `logical` and `physical` checkpoint execution
- built-in validator dispatch plus loading generated Python validator scripts
- repair retry loop with attempt counting
- minimal resume state loading from saved run state
- thin tool registry and stage allowlist scaffolding
- config loading from `configs/`
- real LangSmith trace emission through the recorder abstraction

What is intentionally still stubbed:

- real translate step
- production-grade validator sandboxing
- rich tool implementations

## Quickstart

```bash
conda activate Trace
pip install -e .[dev]
pytest
python main.py run "Construct a typical industrial control network with a node scale of 10, and OpenPLC will be used." --debug --stream
python main.py run experiments/demo/demo.md --debug --stream
python main.py resume <run_id> --output-root runs/default --session-layout sessioned
```

Recommended `.env` for official LangSmith cloud plus DashScope/Qwen:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=trace-iac

OPENAI_API_KEY=your_dashscope_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
TRACE_MODEL_NAME=qwen-plus-0112
```

Equivalent shell exports:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=...
export LANGSMITH_PROJECT=trace-iac
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export TRACE_MODEL_NAME=qwen-plus-0112
```

Optional runtime-specific overrides:

```bash
export TRACE_LANGSMITH_ENABLED=true
export TRACE_LANGSMITH_PROJECT=trace-iac-debug
```

Leave `LANGSMITH_ENDPOINT` and `TRACE_LANGSMITH_ENDPOINT` unset for official LangSmith cloud. They are only needed for self-hosted LangSmith.

Example:

```bash
python main.py run "Construct a typical industrial control network with a node scale of 10, and OpenPLC will be used." --debug --output-root runs/default --session-layout sessioned
python main.py run experiments/demo/demo.md --debug --stream --output-root runs/default --session-layout sessioned
```

Expected output:

```text
session:<run_id>
artifacts:runs/default/<run_id>
stage:ground:started
stage:ground:completed attempts=1
stage:logical:started
...
completed:<run_id>
artifacts:runs/default/<run_id>
```

Run artifacts can now be written in two layouts:

- `--session-layout sessioned`: write under `<output-root>/<run_id>/`
- `--session-layout direct`: write directly under `<output-root>/`

Common examples:

```bash
# default practical mode: one session directory per run
python main.py run "..." --output-root runs/default --session-layout sessioned

# write directly into a target directory
python main.py run "..." --output-root runs/manual-demo --session-layout direct

# resume from a sessioned run
python main.py resume <run_id> --output-root runs/default --session-layout sessioned
```

`--debug` enables stage-level console progress, including stage start/completion and repair rounds.

`--stream` enables raw model text streaming for the LangChain backend. This is most useful when a stage is generating or repairing large JSON outputs. The fake backend does not emit streaming tokens.

`run <input>` accepts either:

- a plain natural-language intent string
- a path to an existing `.md` file, in which case the file contents are used as the intent

If the argument points to an existing file that is not `.md`, the CLI rejects it.

When LangSmith tracing is enabled, one run is organized roughly as:

- `trace.run`
- `stage.ground`, `stage.logical`, `stage.physical`
- `agent.<stage>`
- `patch.<stage>`
- `validation.<stage>`

## Architecture

The codebase is organized around an artifact-first runtime.

### Top-level flow

- [main.py](/d:/Paper/10.Domain%20Agent/Trace/main.py): CLI entrypoint for `run` and `resume`, including `--debug`, `--stream`, `--output-root`, and `--session-layout`
- [app/container.py](/d:/Paper/10.Domain%20Agent/Trace/app/container.py): builds the runtime container, loads config, creates the LangSmith client, installs tracer, and selects fake or LangChain execution
- [app/tplan_runner.py](/d:/Paper/10.Domain%20Agent/Trace/app/tplan_runner.py): executes `ground -> logical -> physical -> translate_stub`, manages per-run session roots, and writes run state
- [app/stage_runtime.py](/d:/Paper/10.Domain%20Agent/Trace/app/stage_runtime.py): resolves declared inputs, calls the agent, persists outputs, runs validation, retries repairable stages, and emits repair progress
- [app/progress.py](/d:/Paper/10.Domain%20Agent/Trace/app/progress.py): lightweight console progress reporter used by `--debug` and model streaming output used by `--stream`

### Contracts and state

- [app/contracts.py](/d:/Paper/10.Domain%20Agent/Trace/app/contracts.py): shared runtime contracts such as `StageSpec`, `ArtifactRef`, `ValidationReport`, and `RunState`
- [app/checkpoints.py](/d:/Paper/10.Domain%20Agent/Trace/app/checkpoints.py): checkpoint file writing
- [app/errors.py](/d:/Paper/10.Domain%20Agent/Trace/app/errors.py): runtime error types

### Stage definitions

- [stages/registry.py](/d:/Paper/10.Domain%20Agent/Trace/stages/registry.py): canonical stage order and registry
- [stages/ground/spec.py](/d:/Paper/10.Domain%20Agent/Trace/stages/ground/spec.py): `ground` stage contract
- [stages/logical/spec.py](/d:/Paper/10.Domain%20Agent/Trace/stages/logical/spec.py): `logical` stage contract
- [stages/physical/spec.py](/d:/Paper/10.Domain%20Agent/Trace/stages/physical/spec.py): `physical` stage contract
- [stages/ground/normalize.py](/d:/Paper/10.Domain%20Agent/Trace/stages/ground/normalize.py): compact node-pattern expansion

### Agent layer

- [agent/facade.py](/d:/Paper/10.Domain%20Agent/Trace/agent/facade.py): fake facade and LangChain-backed facade
- [agent/types.py](/d:/Paper/10.Domain%20Agent/Trace/agent/types.py): agent request and result payloads
- [agent/langchain/message_codec.py](/d:/Paper/10.Domain%20Agent/Trace/agent/langchain/message_codec.py): converts stage requests to LangChain messages
- [agent/langchain/engine.py](/d:/Paper/10.Domain%20Agent/Trace/agent/langchain/engine.py): thin model invocation wrapper
- [agent/langchain/tracing.py](/d:/Paper/10.Domain%20Agent/Trace/agent/langchain/tracing.py): LangSmith-backed trace recorder for root, stage, patch, validation, and agent spans

### Artifact and validation layer

- [artifacts/store.py](/d:/Paper/10.Domain%20Agent/Trace/artifacts/store.py): versioned artifact persistence
- [artifacts/selectors.py](/d:/Paper/10.Domain%20Agent/Trace/artifacts/selectors.py): declared artifact input resolution
- [artifacts/summarizer.py](/d:/Paper/10.Domain%20Agent/Trace/artifacts/summarizer.py): repair-context extraction
- [app/checkpoint_runner.py](/d:/Paper/10.Domain%20Agent/Trace/app/checkpoint_runner.py): stage-facing checkpoint execution entrypoint
- [validators/tgraph_runner.py](/d:/Paper/10.Domain%20Agent/Trace/validators/tgraph_runner.py): built-in and script-based validator execution
- [validators/patching.py](/d:/Paper/10.Domain%20Agent/Trace/validators/patching.py): graph patch helpers

### Tools and prompts

- [tools/registry.py](/d:/Paper/10.Domain%20Agent/Trace/tools/registry.py): global tool registry
- [tools/policy.py](/d:/Paper/10.Domain%20Agent/Trace/tools/policy.py): stage allowlist policy
- [prompts/ground.md](/d:/Paper/10.Domain%20Agent/Trace/prompts/ground.md), [prompts/logical.md](/d:/Paper/10.Domain%20Agent/Trace/prompts/logical.md), [prompts/physical.md](/d:/Paper/10.Domain%20Agent/Trace/prompts/physical.md): stage prompt guidance for grounding, logical author/build, and physical author/build

### Tests

- `tests/unit/`: contracts, artifact store, checkpoint runner, patching, stage runtime, tool policy
- `tests/integration/`: retry behavior and cross-stage artifact flow
- `tests/e2e/`: CLI smoke coverage

## Runtime Shape

At the moment, the runtime behaves like this:

1. `ground`
- outputs `node_patterns`, `expanded_node_ids`, `logical_constraints`, `physical_constraints`

2. `logical`
- reads `ground.expanded_node_ids` and `ground.logical_constraints`
- authors `logical_checkpoints`, then builds `tgraph_logical` through patch-first round outputs
- runs validator checkpoints and retries on failure

3. `physical`
- reads `ground.expanded_node_ids`, `ground.physical_constraints`, `logical.logical_checkpoints`, and `logical.tgraph_logical`
- authors `physical_checkpoints`, then builds `tgraph_physical` through patch-first round outputs
- runs validator checkpoints and retries on failure

4. `translate_stub`
- currently a no-op placeholder
