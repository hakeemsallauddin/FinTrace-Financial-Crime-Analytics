import pandas as pd
from aml.synthetic import generate_transactions
from aml.anomaly import IsolationScorer, LOFScorer, ensemble_score


def test_isolation_scorer_returns_dataframe():
    df = generate_transactions(n=500)
    result = IsolationScorer().fit_score(df)
    assert isinstance(result, pd.DataFrame)


def test_isolation_scorer_required_columns():
    df = generate_transactions(n=500)
    result = IsolationScorer().fit_score(df)
    required = ["account_id", "anomaly_score", "is_anomaly"]
    for col in required:
        assert col in result.columns


def test_isolation_scores_between_zero_and_one():
    df = generate_transactions(n=500)
    result = IsolationScorer().fit_score(df)
    assert (result["anomaly_score"] >= 0).all()
    assert (result["anomaly_score"] <= 1).all()


def test_isolation_scorer_sorted_descending():
    df = generate_transactions(n=500)
    result = IsolationScorer().fit_score(df)
    assert result["anomaly_score"].is_monotonic_decreasing


def test_isolation_scorer_is_anomaly_is_bool():
    df = generate_transactions(n=500)
    result = IsolationScorer().fit_score(df)
    assert result["is_anomaly"].dtype == bool


def test_lof_scorer_returns_dataframe():
    df = generate_transactions(n=500)
    result = LOFScorer().fit_score(df)
    assert isinstance(result, pd.DataFrame)


def test_lof_scores_between_zero_and_one():
    df = generate_transactions(n=500)
    result = LOFScorer().fit_score(df)
    assert (result["anomaly_score"] >= 0).all()
    assert (result["anomaly_score"] <= 1).all()


def test_ensemble_score_returns_dataframe():
    df = generate_transactions(n=500)
    result = ensemble_score(df)
    assert isinstance(result, pd.DataFrame)


def test_ensemble_required_columns():
    df = generate_transactions(n=500)
    result = ensemble_score(df)
    required = [
        "account_id", "iso_score", "lof_score",
        "ensemble_score", "flagged_by_both", "is_anomaly"
    ]
    for col in required:
        assert col in result.columns


def test_ensemble_flagged_by_both_is_subset_of_anomalies():
    df = generate_transactions(n=500)
    result = ensemble_score(df)
    # Every account flagged by both must also be marked as anomaly
    both = result[result["flagged_by_both"]]
    assert both["is_anomaly"].all()


def test_no_duplicate_accounts_in_ensemble():
    df = generate_transactions(n=500)
    result = ensemble_score(df)
    assert result["account_id"].nunique() == len(result)