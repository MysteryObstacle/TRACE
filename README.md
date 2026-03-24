# TRACE

TRACE is a staged agent runtime for turning user intent into topology artifacts. The current `v0` focus is not full IaC generation yet. It is a runnable, testable control plane for:

- `ground -> logical -> physical -> translate_stub`
- explicit artifact passing between stages
- validator-driven retries in `logical` and `physical`
- LangChain-backed execution by default, with explicit fake mode still available for tests and controlled runs
- LangSmith-ready tracing hooks behind a lightweight recorder abstraction

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

What is intentionally still stubbed:

- real translate step
- production-grade validator sandboxing
- rich tool implementations
- real LangSmith client wiring beyond the current trace abstraction

## Quickstart

```bash
conda activate Trace
pip install -e .[dev]
pytest
python main.py run "PLC[1..2] with HMI1"
python main.py resume <run_id>
```

Example:

```bash
python main.py run "PLC[1..2] with HMI1"
```

Expected output:

```text
completed:<run_id>
```

Run artifacts are written under `runs/default/`.

## Architecture

The codebase is organized around an artifact-first runtime.

### Top-level flow

- [main.py](/d:/Paper/10.Domain%20Agent/Trace/main.py): CLI entrypoint for `run` and `resume`
- [app/container.py](/d:/Paper/10.Domain%20Agent/Trace/app/container.py): builds the runtime container, loads config, installs tracer, and selects fake or LangChain execution
- [app/tplan_runner.py](/d:/Paper/10.Domain%20Agent/Trace/app/tplan_runner.py): executes `ground -> logical -> physical -> translate_stub`
- [app/stage_runtime.py](/d:/Paper/10.Domain%20Agent/Trace/app/stage_runtime.py): resolves declared inputs, calls the agent, persists outputs, runs validation, and retries repairable stages

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
- [agent/langchain/tracing.py](/d:/Paper/10.Domain%20Agent/Trace/agent/langchain/tracing.py): trace recorder abstraction

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

## TODO

### Capability layer

- [ ] Make `.env` model settings actually drive default model invocation so `qwen-plus-1220` can call DashScope in the normal execution path.
- [ ] Replace `translate_stub()` in [app/tplan_runner.py](/d:/Paper/10.Domain%20Agent/Trace/app/tplan_runner.py) with a real translation stage, including post-`physical` artifact output strategy.
- [ ] Implement full checkpoint-level `resume` semantics instead of the current minimal state reload.
- [ ] Replace the current tracing shell with a complete LangSmith-backed implementation.
- [ ] Flesh out `tools/knowledge/*` and `tools/tgraph/*` so stages can use real retrieval and graph manipulation helpers.
- [ ] Expand patch and repair support beyond the current minimal graph operations to a full repair system.
- [ ] Move generated Python validator execution toward a stronger sandbox or isolation model.

### Runtime and quality

- [ ] Persist richer run metadata such as timeline events, per-attempt validation reports, and patch histories.
- [ ] Add more realistic integration tests that run the real LangChain facade against controlled stubs or fixtures.
