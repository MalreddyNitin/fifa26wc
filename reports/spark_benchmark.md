# Spark benchmark

The canonical pandas implementation is the reference for the current 9,709
match workload and is faster for single-machine iteration because the dataset
fits in memory. The Spark jobs preserve the same `event_id` and
`event_id + side` grains and become useful when raw event/stat partitions or
simulation outputs exceed local memory. Run them with:

```powershell
docker compose run --rm spark-master spark-submit /workspace/spark/batch/build_matches.py
```

Parity is asserted on row grain, side values, goals, and opponent joins in the
integration suite.
