-- =============================================================================
-- AML Detection: Cash-Intensive Business Risk
-- Database:      PostgreSQL
-- Reference:     FinCEN Advisory FIN-2014-A005
--                FATF Risk-Based Approach for the Banking Sector (2014)
-- Parameters:    %(cash_ratio)s   %(min_txn_count)s   %(lookback_days)s
-- =============================================================================

SELECT
    sender_id                                       AS account_id,
    COUNT(*)                                        AS total_transactions,
    SUM(CASE WHEN channel = 'cash'
             THEN 1 ELSE 0 END)                     AS cash_transactions,
    ROUND(
        SUM(CASE WHEN channel = 'cash'
                 THEN 1.0 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 4
    )                                               AS cash_ratio,
    SUM(CASE WHEN channel = 'cash'
             THEN amount ELSE 0 END)                AS total_cash_amount,
    SUM(amount)                                     AS total_amount,
    'FIN-2014-A005'                                 AS fincen_reference,
    'cash_intensive'                                AS typology
FROM
    transactions
WHERE
    transaction_date >= NOW() - (%(lookback_days)s * INTERVAL '1 day')
GROUP BY
    sender_id
HAVING
    COUNT(*) >= %(min_txn_count)s
    AND ROUND(
        SUM(CASE WHEN channel = 'cash'
                 THEN 1.0 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 4
    ) >= %(cash_ratio)s
ORDER BY
    cash_ratio DESC,
    total_cash_amount DESC;