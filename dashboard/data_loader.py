import pandas as pd

from aml.graph import (
    build_network,
    centrality_score,
    detect_layering,
    detect_structuring,
)

from aml.patterns import run_all


def load_transactions(file_path="transactions.csv"):
    """Load and prepare transaction data."""
    df = pd.read_csv(file_path, parse_dates=["timestamp"])
    return df


def run_analysis(df):
    """Run the existing FinTrace analytics engine."""

    # Rule-based pattern detection
    pattern_results = run_all(df)

    # Transaction network
    network = build_network(df)

    # Graph analytics
    layering_cases = detect_layering(network)
    graph_structuring_cases = detect_structuring(network)
    centrality_scores = centrality_score(network)

    return {
        "patterns": pattern_results,
        "network": network,
        "layering_cases": layering_cases,
        "graph_structuring_cases": graph_structuring_cases,
        "centrality_scores": centrality_scores,
    }