# Mutation Authoring

Per-attempt files: `logical/mutations/attempt_N.py` or `physical/mutations/attempt_N.py`.

```python
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
    tgraph.ensure_direct_link("SW_DMZ", "R_CORE")
    return tgraph
```

Runtime executes the script against a graph copy and applies operations transactionally.
By default `execute_mutation_file` does not run checkpoint validation; the validator node does.
On failure the graph is unchanged and the agent corrects the mutation file using editor docs.
