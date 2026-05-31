-- ============================================================
-- AML Detection: Structuring (CTR Avoidance)
-- ============================================================
-- Detects accounts sending multiple transactions just below
-- the $10,000 CTR reporting threshold within a 48-hour window.
--
-- Typology : Structuring / CTR Avoidance
-- Reference: FinCEN Advisory FIN-2014-A005
--            31 U.S.C. 5324 - Prohibition on structuring
--
-- Parameters (adjust as needed):
--   threshold    : 9000  (just below CTR threshold)
--   window_hours : 48
--   min_count    : 2     (minimum transactions to flag)
--
-- Compatible: Oracle 12c+
-- ============================================================

WITH suspicious_txns AS (
    SELECT
        sender_id,
        transaction_id,
        amount,
        txn_timestamp,
        channel
    FROM transactions
    WHERE amount < 9000
      AND amount > 3000
      AND channel = 'cash'
),
windowed AS (
    SELECT
        a.sender_id,
        a.transaction_id,
        a.amount,
        a.txn_timestamp,
        COUNT(b.transaction_id)     AS txn_count_in_window,
        SUM(b.amount)               AS total_amount_in_window,
        MIN(b.txn_timestamp)        AS window_start,
        MAX(b.txn_timestamp)        AS window_end
    FROM suspicious_txns a
    JOIN suspicious_txns b
        ON  a.sender_id = b.sender_id
        AND b.txn_timestamp BETWEEN a.txn_timestamp
            AND a.txn_timestamp + INTERVAL '48' HOUR
    GROUP BY
        a.sender_id,
        a.transaction_id,
        a.amount,
        a.txn_timestamp
)
SELECT
    sender_id,
    txn_count_in_window,
    ROUND(total_amount_in_window, 2)    AS total_amount,
    window_start,
    window_end,
    ROUND(
        (CAST(window_end AS DATE) - CAST(window_start AS DATE)) * 24,
        2
    )                                   AS window_hours,
    'STRUCTURING'                       AS alert_type,
    'FIN-2014-A005'                     AS fincen_reference,
    SYSDATE                             AS alert_generated_at
FROM windowed
WHERE txn_count_in_window >= 2
ORDER BY txn_count_in_window DESC, total_amount_in_window DESC;