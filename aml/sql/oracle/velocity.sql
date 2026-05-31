-- ============================================================
-- AML Detection: Transaction Velocity
-- ============================================================
-- Detects accounts with unusually high transaction frequency
-- within a rolling 24-hour window. High velocity is a key
-- indicator of layering and rapid fund movement.
--
-- Typology : Layering / Rapid Fund Movement
-- Reference: FATF Guidance on AML/CFT Measures (2012)
--            FinCEN Advisory FIN-2019-A003
--
-- Parameters:
--   window_hours  : 24
--   min_txn_count : 5
--
-- Compatible: Oracle 12c+
-- ============================================================

WITH account_activity AS (
    SELECT
        sender_id       AS account_id,
        transaction_id,
        amount,
        txn_timestamp,
        channel
    FROM transactions
    UNION ALL
    SELECT
        receiver_id     AS account_id,
        transaction_id,
        amount,
        txn_timestamp,
        channel
    FROM transactions
),
velocity_window AS (
    SELECT
        a.account_id,
        a.transaction_id,
        a.txn_timestamp,
        COUNT(b.transaction_id)     AS txn_count_in_window,
        SUM(b.amount)               AS total_amount_in_window,
        AVG(b.amount)               AS avg_amount_in_window,
        MIN(b.txn_timestamp)        AS window_start,
        MAX(b.txn_timestamp)        AS window_end
    FROM account_activity a
    JOIN account_activity b
        ON  a.account_id = b.account_id
        AND b.txn_timestamp BETWEEN a.txn_timestamp
            AND a.txn_timestamp + INTERVAL '24' HOUR
    GROUP BY
        a.account_id,
        a.transaction_id,
        a.txn_timestamp
)
SELECT
    account_id,
    MAX(txn_count_in_window)            AS max_txns_in_24hrs,
    ROUND(MAX(total_amount_in_window), 2) AS max_total_amount,
    ROUND(AVG(avg_amount_in_window), 2) AS avg_txn_amount,
    'VELOCITY'                          AS alert_type,
    'FATF-2012'                         AS reference,
    SYSDATE                             AS alert_generated_at
FROM velocity_window
WHERE txn_count_in_window >= 5
GROUP BY account_id
ORDER BY max_txns_in_24hrs DESC;