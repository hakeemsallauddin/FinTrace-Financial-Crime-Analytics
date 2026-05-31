-- =============================================================================
-- AML Detection: Transaction Velocity
-- Database:      PostgreSQL
-- Reference:     FATF Guidance on AML/CFT Measures (2012)
--                FinCEN Advisory FIN-2019-A003
-- Parameters:    %(window_hours)s   %(min_count)s   %(min_amount)s
-- =============================================================================

SELECT
    account_id,
    window_start,
    window_end,
    transaction_count,
    total_amount,
    avg_amount,
    'FATF-2012'         AS fatf_reference,
    'velocity'          AS typology
FROM (
    SELECT
        t1.sender_id                            AS account_id,
        t1.transaction_date                     AS window_start,
        MAX(t2.transaction_date)                AS window_end,
        COUNT(t2.transaction_id)                AS transaction_count,
        SUM(t2.amount)                          AS total_amount,
        AVG(t2.amount)                          AS avg_amount
    FROM
        transactions t1
        JOIN transactions t2
            ON  t1.sender_id = t2.sender_id
            AND t2.transaction_date BETWEEN t1.transaction_date
                AND t1.transaction_date + (%(window_hours)s * INTERVAL '1 hour')
    WHERE
        t1.transaction_date >= NOW() - INTERVAL '30 days'
    GROUP BY
        t1.sender_id,
        t1.transaction_date
    HAVING
        COUNT(t2.transaction_id) >= %(min_count)s
        AND SUM(t2.amount) >= %(min_amount)s
) subquery
ORDER BY
    transaction_count DESC;