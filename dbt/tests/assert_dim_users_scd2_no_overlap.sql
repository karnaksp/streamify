WITH user_windows AS (
    SELECT
        userId,
        firstName,
        lastName,
        gender,
        rowActivationDate,
        rowExpirationDate,
        LEAD(rowActivationDate) OVER (
            PARTITION BY userId
            ORDER BY rowActivationDate, rowExpirationDate
        ) AS next_row_activation_date
    FROM {{ ref('dim_users') }}
),

overlapping_windows AS (
    SELECT *
    FROM user_windows
    WHERE next_row_activation_date IS NOT NULL
      AND rowExpirationDate > next_row_activation_date
),

invalid_current_rows AS (
    SELECT
        userId,
        COUNTIF(currentRow = 1) AS current_row_count
    FROM {{ ref('dim_users') }}
    GROUP BY userId
    HAVING current_row_count != 1
)

SELECT
    'overlapping_window' AS issue_type,
    userId,
    firstName,
    lastName,
    gender,
    rowActivationDate,
    rowExpirationDate,
    next_row_activation_date
FROM overlapping_windows

UNION ALL

SELECT
    'invalid_current_row_count' AS issue_type,
    userId,
    NULL AS firstName,
    NULL AS lastName,
    NULL AS gender,
    NULL AS rowActivationDate,
    NULL AS rowExpirationDate,
    NULL AS next_row_activation_date
FROM invalid_current_rows
