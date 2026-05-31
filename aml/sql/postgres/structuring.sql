-- =============================================================================
-- AML Detection: Structuring (CTR Avoidance)
-- Database:      PostgreSQL
-- Reference:     FinCEN Advisory FIN-2014-A005
--                31 U.S.C. 5324
-- Parameters:    %(threshold)s   %(window_hours)s   %(min_count)s
-- =============================================================================

SELECT
    t1.sender_id,
    COUNT(*)                                        AS transaction_count,
    SUM(t1.amount)                                  AS total_amount,
    AVG(t1.amount)                                  AS avg_amount,
    MIN(t1.transaction_date)                        AS window_start,
    MAX(t1.transaction_date)                        AS window_end,
    EXTRACT(EPOCH FROM (
        MAX(t1.transaction_date) - MIN(t1.transaction_date)
    )) / 3600                                       AS window_hours_elapsed,
    'FIN-2014-A005'                                 AS fincen_reference,
    'structuring'                                   AS typology
FROM
    transactions t1
WHERE
    t1.amount < %(threshold)s
    AND t1.channel = 'cash'
    AND t1.transaction_date >= NOW() - INTERVAL '%(window_hours)s hours'
GROUP BY
    t1.sender_id
HAVING
    COUNT(*) >= %(min_count)s
ORDER BY
    transaction_count DESC,
    total_amount DESC;