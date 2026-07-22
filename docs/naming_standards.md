# Naming standards

- Platform team IDs: lowercase snake case; external source IDs retain their
  numeric type and source prefix in the column name.
- Event ID: SofaScore integer `event_id`.
- Time: timezone-aware UTC, named `*_utc`; source dates are preserved.
- Tables: `dim_`, `fct_`, `stg_`, `int_`, `feat_`, and `pred_`.
- Pre-match feature: explicit `rolling_`, `ewm_`, or `trend_` prefix and a
  window suffix where applicable.
- Opponent perspective: `opponent_`; historical conceded measurement:
  `against_`.
