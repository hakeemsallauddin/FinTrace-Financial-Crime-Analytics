-- =============================================================================
-- AML Detection: Dormant Account Reactivation
-- Database:      PostgreSQL
-- Reference:     FinCEN Advisory FIN-2016-A005
--                FATF Typologies Report (2006)
-- Parameters:    %(dormant_days)s   %(burst_days)s
-- =============================================================================

WITH account_activity AS (
    SELECT
        sender_id                               AS account_id,
        transaction_date,
        amount,
        LAG(transaction_date) OVER (
            PARTITION BY sender_id
            ORDER BY transaction_date
        )                                       AS prev_transaction_date
    FROM
        transactions
),
dormancy_gaps AS (
    SELECT
        account_id,
        prev_transaction_date                   AS last_activity_before_gap,
        transaction_date                        AS reactivation_date,
        EXTRACT(EPOCH FROM (
            transaction_date - prev_transaction_date
        )) / 86400                              AS gap_days
    FROM
        account_activity
    WHERE
        transaction_date - prev_transaction_date
            >= (%(dormant_days)s * INTERVAL '1 day')
),
post_reactivation AS (
    SELECT
        d.account_id,
        d.last_activity_before_gap,
        d.reactivation_date,
        ROUND(d.gap_days::numeric, 1)           AS gap_days,
        COUNT(t.transaction_id)                 AS post_txn_count,
        COALESCE(SUM(t.amount), 0)              AS post_total_amount
    FROM
        dormancy_gaps d
        LEFT JOIN transactions t
            ON  d.account_id = t.sender_id
            AND t.transaction_date BETWEEN d.reactivation_date
                AND d.reactivation_date + (%(burst_days)s * INTERVAL '1 day')
    GROUP BY
        d.account_id,
        d.last_activity_before_gap,
        d.reactivation_date,
        d.gap_days
)
SELECT
    account_id,
    last_activity_before_gap,
    reactivation_date,
    gap_days,
    post_txn_count,
    post_total_amount,
    'FIN-2016-A005'     AS fincen_reference,
    'dormancy'          AS typology
FROM
    post_reactivation
WHERE
    post_txn_count > 0
ORDER BY
    gap_days DESC,
    post_total_amount DESC;