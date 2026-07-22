# Data artifact policy

This directory is populated by the ingestion and feature pipelines. Generated
raw payloads, canonical Parquet facts, feature matrices, predictions, and
checkpoints are intentionally excluded from Git because they are reproducible
and can be large.

The repository versions only small input templates under `samples/`. To build
the local data products, run:

```powershell
python scripts/run_batch_pipeline.py
python scripts/run_statistics_pipeline.py
python scripts/build_canonical_and_features.py
python scripts/materialize_lake.py
```

See [`../docs/data_lineage.md`](../docs/data_lineage.md) and
[`../docs/canonical_data_dictionary.md`](../docs/canonical_data_dictionary.md)
for lineage, grain, and field definitions.
