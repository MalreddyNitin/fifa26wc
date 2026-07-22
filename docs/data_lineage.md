# Data lineage

| Layer | Dataset | Grain | Derived from |
|---|---|---|---|
| Bronze | SofaScore event/stat JSON | one immutable payload | source endpoint |
| Silver | `fct_matches` | `event_id` | event list + event details |
| Silver | `fct_team_matches` | `event_id, side` | `fct_matches` |
| Silver | `fct_team_match_stats` | `event_id, side` | statistics payload |
| Gold | feature marts | `event_id, side` | facts + prior matches only |
| Models | outcome/scoreline/count artifacts | dataset version | Gold |
| Predictions | match and market forecasts | fixture/model version | models |
| Predictions | tournament probabilities | team/simulation version | simulator |

Every rolling statistic ends at the prior row. The actual opponent row is
joined only to create historical conceded measurements; those measurements are
then shifted before entering a pre-match feature.
