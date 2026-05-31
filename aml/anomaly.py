import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler


def _build_features(df):
    """
    Engineer features from raw transaction data for anomaly detection.
    Aggregates to the account level — one row per account with
    behavioral features derived from their transaction history.

    Features engineered:
    - txn_count        : total number of transactions
    - total_amount     : sum of all transaction amounts
    - avg_amount       : mean transaction amount
    - std_amount       : standard deviation of amounts (consistency)
    - max_amount       : largest single transaction
    - unique_receivers : number of distinct counterparties
    - cash_ratio       : proportion of cash transactions
    - avg_hour         : average hour of day transactions occur
    - night_ratio      : proportion of transactions between 10pm–6am
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    df["is_night"] = df["hour"].apply(lambda h: 1 if (h >= 22 or h < 6) else 0)
    df["is_cash"] = (df["channel"] == "cash").astype(int)

    features = df.groupby("sender_id").agg(
        txn_count=("amount", "count"),
        total_amount=("amount", "sum"),
        avg_amount=("amount", "mean"),
        std_amount=("amount", "std"),
        max_amount=("amount", "max"),
        unique_receivers=("receiver_id", "nunique"),
        cash_ratio=("is_cash", "mean"),
        avg_hour=("hour", "mean"),
        night_ratio=("is_night", "mean"),
    ).reset_index()

    features["std_amount"] = features["std_amount"].fillna(0)
    return features


class IsolationScorer:
    """
    Anomaly scorer using Isolation Forest.

    Isolation Forest isolates anomalies by randomly partitioning
    the feature space. Anomalous accounts require fewer partitions
    to isolate — they are flagged with higher anomaly scores.

    Well-suited for AML because it handles high-dimensional transaction
    feature spaces and does not require labeled training data, which
    is typically scarce in compliance settings.

    References
    ----------
    Liu, F.T., Ting, K.M., Zhou, Z.H. (2008). Isolation Forest.
    FATF Risk-Based Approach Guidance for the Banking Sector (2014)
    """

    def __init__(self, contamination=0.05, random_state=42):
        """
        Parameters
        ----------
        contamination : float
            Expected proportion of anomalies in the dataset.
            Default 0.05 (5%) — typical for AML alert rates.
        random_state : int
            Random seed for reproducibility.
        """
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100,
        )
        self.scaler = StandardScaler()
        self.feature_cols = [
            "txn_count", "total_amount", "avg_amount", "std_amount",
            "max_amount", "unique_receivers", "cash_ratio",
            "avg_hour", "night_ratio",
        ]
        self.is_fitted = False

    def fit_score(self, df):
        """
        Build features, fit the model, and return anomaly scores
        for all accounts in one step.

        Parameters
        ----------
        df : pd.DataFrame
            Raw transaction data.

        Returns
        -------
        pd.DataFrame
            One row per account with columns: account_id,
            anomaly_score (0–1, higher = more anomalous),
            is_anomaly (bool), and all engineered features.
        """
        features = _build_features(df)
        X = features[self.feature_cols].values
        X_scaled = self.scaler.fit_transform(X)

        self.model.fit(X_scaled)
        self.is_fitted = True

        # Isolation Forest returns -1 for anomalies, 1 for normal
        raw_scores = self.model.decision_function(X_scaled)

        # Normalize to 0–1 where 1 = most anomalous
        normalized = 1 - (raw_scores - raw_scores.min()) / (
            raw_scores.max() - raw_scores.min() + 1e-10
        )

        features["anomaly_score"] = normalized.round(6)
        features["is_anomaly"] = self.model.predict(X_scaled) == -1
        features = features.rename(columns={"sender_id": "account_id"})

        return (
            features[["account_id", "anomaly_score", "is_anomaly"] + self.feature_cols]
            .sort_values("anomaly_score", ascending=False)
            .reset_index(drop=True)
        )


class LOFScorer:
    """
    Anomaly scorer using Local Outlier Factor (LOF).

    LOF measures the local density deviation of an account's
    behavior compared to its neighbors. Accounts in sparse
    regions of the feature space (behaving unlike their peers)
    receive high outlier scores.

    Complementary to IsolationForest — use both and flag accounts
    that score high on both methods for higher-confidence alerts.

    References
    ----------
    Breunig, M.M. et al. (2000). LOF: Identifying Density-Based
    Local Outliers. ACM SIGMOD.
    """

    def __init__(self, n_neighbors=20, contamination=0.05):
        """
        Parameters
        ----------
        n_neighbors : int
            Number of neighbors to consider. Default 20.
        contamination : float
            Expected proportion of anomalies. Default 0.05.
        """
        self.n_neighbors = n_neighbors
        self.contamination = contamination
        self.scaler = StandardScaler()
        self.feature_cols = [
            "txn_count", "total_amount", "avg_amount", "std_amount",
            "max_amount", "unique_receivers", "cash_ratio",
            "avg_hour", "night_ratio",
        ]

    def fit_score(self, df):
        """
        Build features, fit LOF, and return anomaly scores.

        Parameters
        ----------
        df : pd.DataFrame
            Raw transaction data.

        Returns
        -------
        pd.DataFrame
            One row per account with anomaly scores and features.
        """
        features = _build_features(df)

        # LOF needs at least n_neighbors + 1 samples
        n_neighbors = min(self.n_neighbors, len(features) - 1)
        if n_neighbors < 1:
            features["anomaly_score"] = 0.0
            features["is_anomaly"] = False
            return features.rename(columns={"sender_id": "account_id"})

        X = features[self.feature_cols].values
        X_scaled = self.scaler.fit_transform(X)

        lof = LocalOutlierFactor(
            n_neighbors=n_neighbors,
            contamination=self.contamination,
        )
        predictions = lof.fit_predict(X_scaled)
        raw_scores = -lof.negative_outlier_factor_

        normalized = (raw_scores - raw_scores.min()) / (
            raw_scores.max() - raw_scores.min() + 1e-10
        )

        features["anomaly_score"] = normalized.round(6)
        features["is_anomaly"] = predictions == -1
        features = features.rename(columns={"sender_id": "account_id"})

        return (
            features[["account_id", "anomaly_score", "is_anomaly"] + self.feature_cols]
            .sort_values("anomaly_score", ascending=False)
            .reset_index(drop=True)
        )


def ensemble_score(df, contamination=0.05):
    """
    Run both IsolationForest and LOF and return a combined
    ensemble score. Accounts flagged by both models are
    higher-confidence alerts.

    This is the recommended function for production use —
    combining multiple unsupervised methods reduces false
    positives compared to using either model alone.

    Parameters
    ----------
    df : pd.DataFrame
        Raw transaction data.
    contamination : float
        Expected anomaly proportion for both models. Default 0.05.

    Returns
    -------
    pd.DataFrame
        One row per account with columns: account_id,
        iso_score, lof_score, ensemble_score, flagged_by_both,
        is_anomaly.
    """
    iso = IsolationScorer(contamination=contamination).fit_score(df)
    lof = LOFScorer(contamination=contamination).fit_score(df)

    merged = iso[["account_id", "anomaly_score", "is_anomaly"]].rename(
        columns={"anomaly_score": "iso_score", "is_anomaly": "iso_anomaly"}
    ).merge(
        lof[["account_id", "anomaly_score", "is_anomaly"]].rename(
            columns={"anomaly_score": "lof_score", "is_anomaly": "lof_anomaly"}
        ),
        on="account_id",
        how="inner",
    )

    merged["ensemble_score"] = (
        (merged["iso_score"] * 0.6) + (merged["lof_score"] * 0.4)
    ).round(6)
    merged["flagged_by_both"] = merged["iso_anomaly"] & merged["lof_anomaly"]
    merged["is_anomaly"] = merged["iso_anomaly"] | merged["lof_anomaly"]

    return (
        merged[["account_id", "iso_score", "lof_score",
                "ensemble_score", "flagged_by_both", "is_anomaly"]]
        .sort_values("ensemble_score", ascending=False)
        .reset_index(drop=True)
    )