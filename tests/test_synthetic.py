import pandas as pd
from aml.synthetic import generate_transactions, get_summary


def test_returns_dataframe():
    df = generate_transactions(n=200)
    assert isinstance(df, pd.DataFrame)


def test_required_columns_present():
    df = generate_transactions(n=200)
    required = [
        "transaction_id", "sender_id", "receiver_id",
        "amount", "timestamp", "channel", "country", "label"
    ]
    for col in required:
        assert col in df.columns, f"Missing column: {col}"


def test_label_values_are_valid():
    df = generate_transactions(n=500)
    valid_labels = {"normal", "structuring", "layering", "smurfing"}
    assert set(df["label"].unique()).issubset(valid_labels)


def test_no_self_transactions():
    df = generate_transactions(n=500)
    assert (df["sender_id"] != df["receiver_id"]).all()


def test_amounts_are_positive():
    df = generate_transactions(n=500)
    assert (df["amount"] > 0).all()


def test_seed_reproducibility():
    df1 = generate_transactions(n=200, seed=1)
    df2 = generate_transactions(n=200, seed=1)
    pd.testing.assert_frame_equal(df1, df2)


def test_structuring_amounts_below_threshold():
    df = generate_transactions(n=1000)
    structuring = df[df["label"] == "structuring"]
    assert (structuring["amount"] < 10_000).all()