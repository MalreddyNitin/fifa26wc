select * from {{ source('raw_canonical', 'fct_team_matches') }}
