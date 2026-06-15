SELECT
    fact_streams.*
FROM {{ ref('fact_streams') }} AS fact_streams
LEFT JOIN {{ ref('dim_users') }} AS dim_users
    ON fact_streams.userKey = dim_users.userKey
LEFT JOIN {{ ref('dim_artists') }} AS dim_artists
    ON fact_streams.artistKey = dim_artists.artistKey
LEFT JOIN {{ ref('dim_songs') }} AS dim_songs
    ON fact_streams.songKey = dim_songs.songKey
LEFT JOIN {{ ref('dim_datetime') }} AS dim_datetime
    ON fact_streams.dateKey = dim_datetime.dateKey
LEFT JOIN {{ ref('dim_location') }} AS dim_location
    ON fact_streams.locationKey = dim_location.locationKey
WHERE dim_users.userKey IS NULL
   OR dim_artists.artistKey IS NULL
   OR dim_songs.songKey IS NULL
   OR dim_datetime.dateKey IS NULL
   OR dim_location.locationKey IS NULL
