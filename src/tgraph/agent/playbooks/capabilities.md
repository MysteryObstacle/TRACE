# TGraph Capability Contract

TGraph is an IaC graph engine. It can directly express only:

- `graph.stage`
- `nodes`, `ports`, and `links`
- `ip` and `cidr`
- `image` and `flavor`
- inspect, validation, canonical JSON emission
- controlled mutation through `TGraphEditor`

Use the outer stage artifact shape:

- `graph`
- `constraint_files`
- `checkpoint_files`

Validation inputs are not graph fields.

## What TGraph Cannot Do Directly

TGraph cannot directly:

- install software on a node
- run package manager steps
- run shell, cloud-init, or Ansible actions
- look up provider catalogs or image catalogs
- guarantee that an image or flavor exists in a real provider
- represent unsupported IR fields such as `software`, `packages`, `zone`, `firewall_rules`, or provider-specific deployment plans (`segment` is a function parameter pointing to a neighboring node, not an IR field)

If a request depends on knowledge, workflow, catalogs, or provider behavior, the caller must supply that outside TGraph.

## Indirect Translation Rules

If the user says "install software", do not invent a `software` or `packages` field on the graph.

Instead:

1. Resolve an image outside TGraph.
2. Set `node.image` through controlled mutation.
3. If the image choice must be checked, add a checkpoint function in the relevant checkpoint file.

If the user asks for isolation or mandatory hops, do not invent `zone` or `segment` IR fields.

Instead:

1. Model topology with nodes, ports, and links.
2. Express logical intent with checkpoint functions aligned to constraint fact kinds.

If the user asks whether a provider supports an image, flavor, or feature, do not guess inside TGraph.

Instead:

1. Query the caller-owned catalog or provider layer.
2. Translate the chosen result into `graph` fields or validation inputs.

## Decision Ladder

Before writing changes:

1. Can this be represented with `graph` fields only?
2. If not, can it be checked with `checkpoint_files` using `TGraphView` APIs?
3. If it still depends on workflow, knowledge, or catalogs, keep it outside TGraph and ask the caller layer to resolve it.
