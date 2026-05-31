-- ============================================================
-- AML Detection: Dormant Account Reactivation
-- ============================================================
-- Detects accounts inactive for 90+ days that suddenly show
-- burst transaction activity after reactivation. Common in
-- sleeper account money laundering schemes.
--
-- Typology : Dormant Account / Sleeper Account
-- Reference: FinCEN Advisory FIN-2016-A005
--            FATF Typologies Report 2006
--
-- Parameters:
--   dormant_days         : 90
--   burst_window_hours   : 48
--   min_post_txn_count   : 3
--
-- Compatible: Oracle 12c+
-- ============================================================

WITH account_txns AS (
    SELECT
        sender_id           AS account_id,
        transaction_id,
        amount,
        txn_timestamp
    FROM transactions
),
with_gaps AS (
    SELECT
        account_id,
        txn_timestamp,
        amount,
        LAG(txn_timestamp) OVER (
            PARTITION BY account_id
            ORDER BY txn_timestamp
        )                   AS prev_txn_timestamp
    FROM account_txns
),
dormant_reactivations AS (
    SELECT
        account_id,
        prev_txn_timestamp  AS last_activity_before_gap,
        txn_timestamp       AS reactivation_date,
        ROUND(
            (CAST(txn_timestamp AS DATE) -
             CAST(prev_txn_timestamp AS DATE)),
            1
        )                   AS gap_days
    FROM with_gaps
    WHERE prev_txn_timestamp IS NOT NULL
      AND (CAST(txn_timestamp AS DATE) -
           CAST(prev_txn_timestamp AS DATE)) >= 90
),
post_reactivation AS (
    SELECT
        r.account_id,
        r.last_activity_before_gap,
        r.reactivation_date,
        r.gap_days,
        COUNT(t.transaction_id)     AS post_txn_count,
        ROUND(SUM(t.amount), 2)     AS post_total_amount
    FROM dormant_reactivations r
    JOIN account_txns t
        ON  r.account_id = t.account_id
        AND t.txn_timestamp BETWEEN r.reactivation_date
            AND r.reactivation_date + INTERVAL '48' HOUR
    GROUP BY
        r.account_id,
        r.last_activity_before_gap,
        r.reactivation_date,
        r.gap_days
)
SELECT
    account_id,
    last_activity_before_gap,
    reactivation_date,
    gap_days,
    post_txn_count,
    post_total_amount,
    'DORMANCY_REACTIVATION'     AS alert_type,
    'FIN-2016-A005'             AS fincen_reference,
    SYSDATE                     AS alert_generated_at
FROM post_reactivation
WHERE post_txn_count >= 3
ORDER BY gap_days DESC, post_total_amount DESC;