# Tournament simulation

The materialized run contains 50,000 complete 48-team tournaments using
pre-match Elo strength, Poisson group scores, best-third-place qualification,
the official Round-of-32 slot structure, extra time, and strength-adjusted
penalties.

Probability mass reconciles to exactly 32 Round-of-32 teams, 16 Round-of-16
teams, eight quarterfinalists, four semifinalists, two finalists, and one
champion per simulation. Every registered team reached the title in at least
one run; the complete team probabilities are in
`data/predictions/tournament_probabilities.parquet`.
