import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import string


def _random_id(prefix="ACC", length=8):
    return prefix + "".join(random.choices(string.digits, k=length))


def _random_timestamp(start, end):
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def generate_transactions(
    n=1000,
    structuring_pct=0.05,
    layering_pct=0.05,
    smurfing_pct=0.03,
    n_accounts=50,
    seed=42,
):
    """
    Generate a synthetic AML transaction dataset with labeled scenarios.

    Parameters
    ----------
    n : int
        Total number of transactions to generate.
    structuring_pct : float
        Fraction of transactions that are structuring (breaking up large
        amounts into sub-$10,000 transactions to avoid CTR filing).
    layering_pct : float
        Fraction of transactions that are part of a layering chain
        (rapid movement through multiple accounts to obscure origin).
    smurfing_pct : float
        Fraction of transactions that are smurfing (multiple individuals
        making deposits just below reporting thresholds).
    n_accounts : int
        Number of unique account IDs in the dataset.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: transaction_id, sender_id, receiver_id,
        amount, timestamp, channel, country, label.

    References
    ----------
    FinCEN Advisory FIN-2014-A005: Guidance on Structuring
    FATF Typologies Report: Trade-Based Money Laundering (2006)
    """
    random.seed(seed)
    np.random.seed(seed)

    accounts = [_random_id("ACC") for _ in range(n_accounts)]
    channels = ["wire", "ACH", "cash", "check", "digital_wallet"]
    countries = ["US", "US", "US", "US", "MX", "CN", "RU", "NG", "PA", "KY"]

    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)

    rows = []
    txn_counter = 1

    # ── Normal transactions ──────────────────────────────────────────
    n_normal = int(n * (1 - structuring_pct - layering_pct - smurfing_pct))
    for _ in range(n_normal):
        sender, receiver = random.sample(accounts, 2)
        rows.append({
            "transaction_id": f"TXN{txn_counter:07d}",
            "sender_id":      sender,
            "receiver_id":    receiver,
            "amount":         round(np.random.lognormal(mean=7.5, sigma=1.5), 2),
            "timestamp":      _random_timestamp(start_date, end_date),
            "channel":        random.choice(channels),
            "country":        random.choice(countries),
            "label":          "normal",
        })
        txn_counter += 1

    # ── Structuring transactions ─────────────────────────────────────
    # Pattern: a single sender breaks one large amount into multiple
    # transactions each just under $10,000 within a short window.
    # Ref: FinCEN Advisory FIN-2014-A005
    n_structuring = int(n * structuring_pct)
    for _ in range(n_structuring):
        sender   = random.choice(accounts)
        receiver = random.choice([a for a in accounts if a != sender])
        base_ts  = _random_timestamp(start_date, end_date)
        rows.append({
            "transaction_id": f"TXN{txn_counter:07d}",
            "sender_id":      sender,
            "receiver_id":    receiver,
            "amount":         round(random.uniform(8_000, 9_999), 2),
            "timestamp":      base_ts + timedelta(minutes=random.randint(0, 120)),
            "channel":        "cash",
            "country":        "US",
            "label":          "structuring",
        })
        txn_counter += 1

    # ── Layering transactions ────────────────────────────────────────
    # Pattern: funds move rapidly through a chain of accounts
    # (A → B → C → D) within hours to obscure the origin.
    # Ref: FATF Typologies Report 2006
    n_layering = int(n * layering_pct)
    chain_length = 4
    for _ in range(n_layering // chain_length + 1):
        chain    = random.sample(accounts, chain_length + 1)
        amount   = round(random.uniform(20_000, 200_000), 2)
        base_ts  = _random_timestamp(start_date, end_date)
        for hop in range(chain_length):
            if txn_counter > n:
                break
            rows.append({
                "transaction_id": f"TXN{txn_counter:07d}",
                "sender_id":      chain[hop],
                "receiver_id":    chain[hop + 1],
                "amount":         round(amount * random.uniform(0.9, 1.0), 2),
                "timestamp":      base_ts + timedelta(hours=hop * random.randint(1, 6)),
                "channel":        random.choice(["wire", "ACH"]),
                "country":        random.choice(countries),
                "label":          "layering",
            })
            txn_counter += 1

    # ── Smurfing transactions ────────────────────────────────────────
    # Pattern: multiple different senders each send just-below-threshold
    # amounts to the same receiver in a short window.
    # Ref: FATF Glossary — Smurfing
    n_smurfing = int(n * smurfing_pct)
    for _ in range(n_smurfing):
        receiver = random.choice(accounts)
        sender   = random.choice([a for a in accounts if a != receiver])
        rows.append({
            "transaction_id": f"TXN{txn_counter:07d}",
            "sender_id":      sender,
            "receiver_id":    receiver,
            "amount":         round(random.uniform(3_000, 9_500), 2),
            "timestamp":      _random_timestamp(start_date, end_date),
            "channel":        "cash",
            "country":        "US",
            "label":          "smurfing",
        })
        txn_counter += 1

    df = (
        pd.DataFrame(rows)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return df


def get_summary(df):
    """
    Print a quick summary of the generated dataset.
    Useful for sanity-checking before using the data in other modules.
    """
    print(f"Total transactions : {len(df):,}")
    print(f"Unique senders     : {df['sender_id'].nunique():,}")
    print(f"Unique receivers   : {df['receiver_id'].nunique():,}")
    print(f"Date range         : {df['timestamp'].min().date()} → {df['timestamp'].max().date()}")
    print(f"Amount range       : ${df['amount'].min():,.2f} → ${df['amount'].max():,.2f}")
    print()
    print("Label breakdown:")
    print(df["label"].value_counts().to_string())