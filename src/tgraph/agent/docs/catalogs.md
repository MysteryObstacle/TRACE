# Catalogs

Images and flavors are static knowledge for the first implementation.

Physical agents should:

1. Read available static docs or caller-provided catalogs.
2. Choose concrete `image` and `flavor` values in mutation files.
3. Write physical checkpoint functions that check the chosen values.

TGraph itself does not query provider catalogs and does not infer image capability. If a physical capability fact must be checked, the agent should use the static knowledge source it was given and encode the check explicitly in `physical/checkpoints.py`.
