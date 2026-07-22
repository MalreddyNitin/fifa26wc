# Contributing

Use Python 3.12 and create an isolated environment. Install the development
toolchain with `pip install -e ".[dev]"`, then run:

```powershell
ruff check src scripts tests
ruff format --check src scripts tests
pytest
```

Identifiers use lowercase snake case internally. SofaScore event IDs and team
IDs remain source-native integers; stable platform team IDs are lowercase
strings. Timestamps are UTC and names ending in `_utc` are timezone-aware.
Warehouse tables use `dim_`, `fct_`, `stg_`, `int_`, `feat_`, or `pred_`
prefixes. Pre-match features must explicitly lag current-match observations.

Never commit `.env`, API tokens, credentials, raw payloads, model binaries, or
personally identifiable data. Add new secret names only to `.env.example`.
