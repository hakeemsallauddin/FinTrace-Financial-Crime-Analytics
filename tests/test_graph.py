import pandas as pd
import networkx as nx
from aml.synthetic import generate_transactions
from aml.graph import (
    build_network,
    detect_structuring,
    detect_layering,
    centrality_score,
    get_network_summary,
)


def test_build_network_returns_digraph():
    df = generate_transactions(n=200)
    G = build_network(df)
    assert isinstance(G, nx.DiGraph)


def test_build_network_has_nodes_and_edges():
    df = generate_transactions(n=200)
    G = build_network(df)
    assert G.number_of_nodes() > 0
    assert G.number_of_edges() > 0


def test_detect_structuring_returns_list():
    df = generate_transactions(n=500)
    G = build_network(df)
    alerts = detect_structuring(G)
    assert isinstance(alerts, list)


def test_structuring_alerts_have_required_keys():
    df = generate_transactions(n=500)
    G = build_network(df)
    alerts = detect_structuring(G)
    if alerts:
        required = ["sender_id", "transaction_count", "total_amount",
                    "time_window_hours", "edge_list"]
        for key in required:
            assert key in alerts[0], f"Missing key: {key}"


def test_detect_layering_returns_list():
    df = generate_transactions(n=300)
    G = build_network(df)
    chains = detect_layering(G, min_hops=2)
    assert isinstance(chains, list)


def test_centrality_score_returns_dataframe():
    df = generate_transactions(n=200)
    G = build_network(df)
    scores = centrality_score(G)
    assert isinstance(scores, pd.DataFrame)


def test_centrality_score_has_required_columns():
    df = generate_transactions(n=200)
    G = build_network(df)
    scores = centrality_score(G)
    required = ["node_id", "degree_centrality",
                "betweenness_centrality", "in_degree_centrality", "risk_score"]
    for col in required:
        assert col in scores.columns


def test_centrality_score_sorted_descending():
    df = generate_transactions(n=200)
    G = build_network(df)
    scores = centrality_score(G)
    assert scores["risk_score"].is_monotonic_decreasing