# Mutation Authoring

Per-attempt files: `logical/mutations/attempt_N.py` or `physical/mutations/attempt_N.py`.

```python
def mutate(tgraph):
    tgraph.ensure_direct_link("WEB", "SW_DMZ")
    tgraph.ensure_direct_link("SW_DMZ", "R_CORE")
    return tgraph
```

Runtime executes the script against a graph copy and commits only if validation passes.
On failure the original graph is unchanged and repair receives structured issues.
