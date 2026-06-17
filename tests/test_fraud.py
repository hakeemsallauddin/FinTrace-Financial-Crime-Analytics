"""Tests for aml.fraud (APP fraud detection)."""

import numpy as np
import pandas as pd
import pytest

from aml.fraud import APPFraudScorer, ColumnConfig, ScoringWeights, score_transactions


def _normal_history(account, counterparty, start, n, step_hours=72, amount=120.0, jitter=15.0, seed=0):
    """A customer making small, regular payments to a known payee."""
    rng = np.random.default_rng(seed)
    rows = []
    t = pd.Timestamp(start)
    for i in range(n):
        rows.append(
            {
                "transaction_id": f"{account}-{i}",
                "timestamp": t,
                "account": account,
                "counterparty": counterparty,
                "amount": float(max(5.0, amount + rng.normal(0, jitter))),
            }
        )
        t = t + pd.Timedelta(hours=step_hours)
    return pd.DataFrame(rows)


@pytest.fixture
def app_fraud_dataset():
    """Normal baseline for ACC1 followed by a textbook APP-fraud payment."""
    hist = _normal_history("ACC1", "UTILITY_CO", "2026-01-01", n=10)
    fraud_time = hist["timestamp"].max() + pd.Timedelta(hours=72)
    fraud = pd.DataFrame(
        [
            {
                "transaction_id": "ACC1-FRAUD",
                "timestamp": fraud_time,
                "account": "ACC1",
                "counterparty": "MULE_ACCT_X",  # brand new payee
                "amount": 9000.0,               # huge vs ~120 baseline, round number
            }
        ]
    )
    return pd.concat([hist, fraud], ignore_index=True), "ACC1-FRAUD"


def test_score_columns_present(app_fraud_dataset):
    df, _ = app_fraud_dataset
    out = score_transactions(df)
    for col in ["app_fraud_score", "reason_codes", "amount_zscore", "new_counterparty"]:
        assert col in out.columns
    assert out["app_fraud_score"].between(0, 100).all()


def test_fraud_payment_scores_high(app_fraud_dataset):
    df, fraud_id = app_fraud_dataset
    out = score_transactions(df).set_index("transaction_id")
    fraud_score = out.loc[fraud_id, "app_fraud_score"]
    normal_scores = out.drop(index=fraud_id)["app_fraud_score"]
    assert fraud_score >= 70, f"expected high score, got {fraud_score}"
    assert fraud_score > normal_scores.max()


def test_fraud_reason_codes(app_fraud_dataset):
    df, fraud_id = app_fraud_dataset
    out = score_transactions(df).set_index("transaction_id")
    codes = set(out.loc[fraud_id, "reason_codes"])
    assert "NEW_PAYEE" in codes
    assert "AMOUNT_ANOMALY" in codes
    assert "NEW_PAYEE_LARGE_VALUE" in codes


def test_normal_payments_score_low(app_fraud_dataset):
    df, fraud_id = app_fraud_dataset
    out = score_transactions(df).set_index("transaction_id")
    # established payee, in-pattern amounts -> low risk after history builds
    settled = out.drop(index=fraud_id).iloc[4:]  # skip cold-start rows
    assert (settled["app_fraud_score"] < 40).all()


def test_new_counterparty_flag():
    df = _normal_history("ACC2", "PAYEE_A", "2026-02-01", n=5)
    new_payee = pd.DataFrame(
        [{
            "transaction_id": "ACC2-NEW",
            "timestamp": df["timestamp"].max() + pd.Timedelta(hours=72),
            "account": "ACC2",
            "counterparty": "PAYEE_B",
            "amount": 130.0,
        }]
    )
    out = score_transactions(pd.concat([df, new_payee], ignore_index=True)).set_index("transaction_id")
    assert out.loc["ACC2-NEW", "new_counterparty"] == 1
    assert out.loc[df["transaction_id"].iloc[-1], "new_counterparty"] == 0


def test_velocity_spike_detected():
    # Account suddenly fires many outbound payments inside the 24h window.
    base = _normal_history("ACC3", "PAYEE_A", "2026-03-01", n=6, step_hours=72)
    burst_start = base["timestamp"].max() + pd.Timedelta(hours=72)
    burst = pd.DataFrame(
        [{
            "transaction_id": f"ACC3-B{i}",
            "timestamp": burst_start + pd.Timedelta(hours=i),
            "account": "ACC3",
            "counterparty": "PAYEE_A",
            "amount": 110.0,
        } for i in range(6)]
    )
    out = score_transactions(pd.concat([base, burst], ignore_index=True)).set_index("transaction_id")
    last_burst = out.loc["ACC3-B5"]
    assert last_burst["vel_count"] >= 4
    assert "OUTBOUND_VELOCITY_SPIKE" in set(last_burst["reason_codes"])


def test_mule_fanin_detected():
    # One beneficiary receives from many distinct senders in a short window.
    rows = []
    t0 = pd.Timestamp("2026-04-01")
    for s in range(8):
        rows.append({
            "transaction_id": f"S{s}",
            "timestamp": t0 + pd.Timedelta(hours=s),
            "account": f"SENDER_{s}",
            "counterparty": "MULE_HUB",
            "amount": 250.0,
        })
    df = pd.DataFrame(rows)
    out = score_transactions(df).set_index("transaction_id")
    # the last payment into the hub should see high fan-in from prior senders
    assert out.loc["S7", "mule_fanin"] >= 6
    assert "MULE_FANIN" in set(out.loc["S7", "reason_codes"])


def test_custom_column_config():
    df = pd.DataFrame({
        "id": ["a", "b"],
        "ts": pd.to_datetime(["2026-05-01", "2026-05-02"]),
        "payer": ["X", "X"],
        "payee": ["Y", "Z"],
        "value": [100.0, 100.0],
    })
    cfg = ColumnConfig(timestamp="ts", account="payer", counterparty="payee",
                       amount="value", transaction_id="id")
    out = score_transactions(df, columns=cfg)
    assert "app_fraud_score" in out.columns
    assert len(out) == 2


def test_missing_columns_raises():
    df = pd.DataFrame({"timestamp": [], "account": [], "amount": []})
    with pytest.raises(KeyError):
        score_transactions(df)


def test_fit_then_score_uses_reference_history():
    ref = _normal_history("ACC9", "PAYEE_A", "2026-06-01", n=8)
    batch = pd.DataFrame(
        [{
            "transaction_id": "ACC9-BATCH",
            "timestamp": ref["timestamp"].max() + pd.Timedelta(hours=24),
            "account": "ACC9",
            "counterparty": "NEW_MULE",
            "amount": 8000.0,
        }]
    )
    scorer = APPFraudScorer()
    out = scorer.score(batch, reference=ref).set_index("transaction_id")
    assert len(out) == 1  # only the batch row is returned
    assert out.loc["ACC9-BATCH", "app_fraud_score"] >= 60
    assert "NEW_PAYEE" in set(out.loc["ACC9-BATCH", "reason_codes"])


def test_weights_are_tunable(app_fraud_dataset):
    df, fraud_id = app_fraud_dataset
    light = ScoringWeights(new_counterparty=0.0, new_payee_large=0.0)
    out_default = score_transactions(df).set_index("transaction_id")
    out_light = score_transactions(df, weights=light).set_index("transaction_id")
    # zeroing the new-payee signals must lower the fraud row's score
    assert out_light.loc[fraud_id, "app_fraud_score"] < out_default.loc[fraud_id, "app_fraud_score"]


def test_handles_tiny_input():
    df = pd.DataFrame({
        "transaction_id": ["only"],
        "timestamp": pd.to_datetime(["2026-01-01"]),
        "account": ["ACC"],
        "counterparty": ["CP"],
        "amount": [100.0],
    })
    out = score_transactions(df)
    assert len(out) == 1
    assert np.isfinite(out["app_fraud_score"]).all()
