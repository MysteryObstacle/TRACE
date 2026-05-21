# Ground Grounding Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ground artifact shape with `node_groups + {id, statement}` constraints and tighten prompts so ground emits executable plans instead of loose summaries.

**Architecture:** Update the ground schema first, then thread the new artifact through derive helpers and stage prompts. Use tests to lock the new artifact shape and the downstream consumption points before changing implementation.

**Tech Stack:** Python, Pydantic, pytest, Markdown prompts

---

## Chunk 1: Lock the New Artifact Contract

### Task 1: Update schema-facing tests

**Files:**
- Modify: `d:/Projects/Trace/tests/unit/stages/test_ground_schemas.py`
- Modify: `d:/Projects/Trace/tests/unit/stages/test_ground_evaluator_postprocess.py`
- Modify: `d:/Projects/Trace/tests/unit/config/test_prompts.py`

- [ ] **Step 1: Rewrite the tests to expect `node_groups` and `{id, statement}` constraints**
- [ ] **Step 2: Run the targeted tests and confirm they fail against the old implementation**
- [ ] **Step 3: Update `src/trace/stages/ground/schemas.py` and the ground prompts to satisfy the new tests**
- [ ] **Step 4: Re-run the targeted tests and confirm they pass**

## Chunk 2: Thread the New Artifact Through Logical and Physical Stages

### Task 2: Update helpers and stage consumers

**Files:**
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/derive.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/nodes/prepare.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/author.md`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/builder.md`
- Modify: `d:/Projects/Trace/src/trace/stages/physical/prompts/author.md`
- Modify: `d:/Projects/Trace/src/trace/stages/ground/prompts/author.md`
- Modify: `d:/Projects/Trace/src/trace/stages/ground/prompts/evaluator.md`
- Test: `d:/Projects/Trace/tests/unit/stages/logical/test_author_node.py`
- Test: `d:/Projects/Trace/tests/unit/stages/logical/test_builder_node.py`
- Test: `d:/Projects/Trace/tests/unit/stages/physical/test_physical_author_node.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`

- [ ] **Step 1: Rewrite downstream unit tests to consume `node_groups` and constraint statements**
- [ ] **Step 2: Run the targeted tests and confirm they fail**
- [ ] **Step 3: Update derive helpers and stage prompts/nodes to satisfy the tests**
- [ ] **Step 4: Re-run the targeted tests and confirm they pass**

## Chunk 3: Validate End-to-End Stage Behavior

### Task 3: Refresh integration fixtures and docs

**Files:**
- Modify: `d:/Projects/Trace/tests/integration/test_ground_stage.py`
- Modify: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`
- Modify: `d:/Projects/Trace/docs/architecture/langgraph/ground/README.zh.md`
- Modify: `d:/Projects/Trace/docs/architecture/langgraph/logical/README.zh.md`

- [ ] **Step 1: Update integration tests to emit the new ground artifact shape**
- [ ] **Step 2: Run the integration tests and confirm they fail if any old fields remain**
- [ ] **Step 3: Update docs that still explain the old ground artifact**
- [ ] **Step 4: Re-run unit and integration coverage for the touched areas**

Plan complete and saved to `docs/superpowers/plans/2026-04-11-ground-grounding-redesign.md`. Ready to execute?
