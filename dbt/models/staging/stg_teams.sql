select * from {{ source('raw_canonical', 'dim_teams') }}
