select * from {{ source('raw_canonical', 'fct_matches') }}
