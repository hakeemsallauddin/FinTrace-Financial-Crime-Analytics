-- ============================================================
-- AML Detection: Cash-Intensive Account Activity
-- ============================================================
-- Detects accounts where more than 70% of transactions are
-- cash-based, indicating potential use as a front business
-- to commingle illicit cash with legitimate revenue.
--
-- Typology : Cash-Intensive Business / Front Company
-- Reference: FinCEN Advisory FIN-2014-A005
--            FATF Risk-Based Approach Guidance (2014)
--
-- Parameters:
--   min_txn_count  : 5
--   cash_ratio_min : 0.70
--
-- Compatible: Oracle 12c+
-- ============================================================

WITH account_summary AS (
    SELECT
        sender_id                               AS account_id,
        COUNT(transaction_id)                   AS total_txns,
        SUM(CASE WHEN channel = 'cash'
                 THEN 1 ELSE 0 END)             AS cash_txns,
        SUM(CASE WHEN channel = 'cash'
                 THEN amount ELSE 0 END)        AS total_cash_amount,
        SUM(amount)                             AS total_amount,
        ROUND(
            SUM(CASE WHEN channel = 'cash'
                     THEN 1 ELSE 0 END) /
            NULLIF(COUNT(transaction_id), 0),
            4
        )                                       AS cash_ratio
    FROM transactions
    GROUP BY sender_id
)
SELECT
    account_id,
    total_txns,
    cash_txns,
    ROUND(total_cash_amount, 2)     AS total_cash_amount,
    ROUND(total_amount, 2)          AS total_amount,
    cash_ratio,
    'CASH_INTENSIVE'                AS alert_type,
    'FIN-2014-A005'                 AS fincen_reference,
    SYSDATE                         AS alert_generated_at
FROM account_summary
WHERE total_txns >= 5
  AND cash_ratio >= 0.70
ORDER BY cash_ratio DESC, total_cash_amount DESC;