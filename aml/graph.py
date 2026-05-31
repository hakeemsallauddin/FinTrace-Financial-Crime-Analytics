import pandas as pd
import numpy as np
import networkx as nx
from datetime import timedelta


def build_network(df, directed=True):
    """
    Build a transaction network graph from a DataFrame.

    Each node is an account. Each edge is a transaction, with
    amount, timestamp, channel, and label as edge attributes.

    Parameters
    ----------
    df : pd.DataFrame
        Transaction data with columns: sender_id, receiver_id,
        amount, timestamp, channel, label.
    directed : bool
        If True, returns a DiGraph (directed). Default True —
        direction matters for layering detection.

    Returns
    -------
    networkx.DiGraph or networkx.Graph
    """
    G = nx.DiGraph() if directed else nx.Graph()

    for _, row in df.iterrows():
        G.add_edge(
            row["sender_id"],
            row["receiver_id"],
            amount=row["amount"],
            timestamp=row["timestamp"],
            channel=row["channel"],
            label=row.get("label", "unknown"),
        )

    return G


def detect_structuring(G, threshold=9_000, max_gap_hours=48):
    """
    Detect potential structuring — accounts sending multiple transactions
    just below the CTR reporting threshold within a short time window.

    Structuring (also called smurfing) involves breaking up large cash
    amounts into smaller transactions each just under $10,000 to avoid
    triggering a Currency Transaction Report (CTR).

    Parameters
    ----------
    G : networkx.DiGraph
        Transaction network from build_network().
    threshold : float
        Amount below which a transaction is considered suspicious
        for structuring. Default 9,000 (just under CTR threshold).
    max_gap_hours : int
        Maximum hours between transactions to consider them part
        of the same structuring pattern. Default 48.

    Returns
    -------
    list of dict
        Each dict contains: sender_id, transaction_count,
        total_amount, time_window_hours, edge_list.

    References
    ----------
    FinCEN Advisory FIN-2014-A005: Guidance on Structuring
    31 U.S.C. 5324 — Structuring transactions to evade reporting
    """
    alerts = []

    for node in G.nodes():
        outgoing = [
            (u, v, d) for u, v, d in G.edges(node, data=True)
            if d["amount"] < threshold
        ]

        if len(outgoing) < 2:
            continue

        outgoing_sorted = sorted(outgoing, key=lambda x: x[2]["timestamp"])

        for i in range(len(outgoing_sorted)):
            window = [outgoing_sorted[i]]
            for j in range(i + 1, len(outgoing_sorted)):
                t1 = outgoing_sorted[i][2]["timestamp"]
                t2 = outgoing_sorted[j][2]["timestamp"]
                gap = (t2 - t1).total_seconds() / 3600
                if gap <= max_gap_hours:
                    window.append(outgoing_sorted[j])
                else:
                    break

            if len(window) >= 2:
                total = sum(e[2]["amount"] for e in window)
                t_start = window[0][2]["timestamp"]
                t_end = window[-1][2]["timestamp"]
                hours = (t_end - t_start).total_seconds() / 3600

                alerts.append({
                    "sender_id":          node,
                    "transaction_count":  len(window),
                    "total_amount":       round(total, 2),
                    "time_window_hours":  round(hours, 2),
                    "edge_list":          [(e[0], e[1]) for e in window],
                })

    # Deduplicate — keep the longest window per sender
    seen = {}
    for alert in alerts:
        sid = alert["sender_id"]
        if sid not in seen or alert["transaction_count"] > seen[sid]["transaction_count"]:
            seen[sid] = alert

    return list(seen.values())


def detect_layering(G, min_hops=3, max_hops=6):
    """
    Detect potential layering — funds moving rapidly through a chain
    of accounts to obscure the origin (A → B → C → D).

    Layering is the second stage of money laundering where illicit
    funds are moved through multiple accounts or jurisdictions to
    create distance from the original crime.

    Parameters
    ----------
    G : networkx.DiGraph
        Transaction network from build_network().
    min_hops : int
        Minimum chain length to flag as suspicious. Default 3.
    max_hops : int
        Maximum chain length to trace. Default 6.

    Returns
    -------
    list of dict
        Each dict contains: chain, chain_length, total_amount,
        start_node, end_node.

    References
    ----------
    FATF Typologies Report: Money Laundering (2006)
    FinCEN Advisory FIN-2022-A001: Concerning Potential Evasion
    """
    alerts = []
    visited_chains = set()

    for source in G.nodes():
        for target in G.nodes():
            if source == target:
                continue
            try:
                paths = list(nx.all_simple_paths(
                    G, source, target,
                    cutoff=max_hops
                ))
                for path in paths:
                    if len(path) - 1 < min_hops:
                        continue

                    chain_key = tuple(path)
                    if chain_key in visited_chains:
                        continue
                    visited_chains.add(chain_key)

                    edge_amounts = []
                    for i in range(len(path) - 1):
                        edge_data = G.get_edge_data(path[i], path[i + 1])
                        if edge_data:
                            edge_amounts.append(edge_data.get("amount", 0))

                    alerts.append({
                        "chain":        path,
                        "chain_length": len(path) - 1,
                        "total_amount": round(sum(edge_amounts), 2),
                        "start_node":   path[0],
                        "end_node":     path[-1],
                    })
            except nx.NetworkXError:
                continue

    return sorted(alerts, key=lambda x: x["chain_length"], reverse=True)


def centrality_score(G):
    """
    Score each account node by its centrality in the transaction network.

    High centrality nodes are accounts that sit at the center of many
    transaction flows — a pattern consistent with funnel accounts used
    in money laundering operations.

    Computes three centrality measures and returns a combined risk score:
    - Degree centrality: how many direct connections the account has
    - Betweenness centrality: how often the account sits on the shortest
      path between other accounts (funnel account indicator)
    - In-degree centrality: ratio of incoming vs outgoing transactions

    Parameters
    ----------
    G : networkx.DiGraph
        Transaction network from build_network().

    Returns
    -------
    pd.DataFrame
        One row per node with columns: node_id, degree_centrality,
        betweenness_centrality, in_degree_centrality, risk_score.
        Sorted by risk_score descending.
    """
    degree      = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G)
    in_degree   = nx.in_degree_centrality(G)

    rows = []
    for node in G.nodes():
        d  = degree.get(node, 0)
        b  = betweenness.get(node, 0)
        i  = in_degree.get(node, 0)
        risk = round((0.3 * d) + (0.5 * b) + (0.2 * i), 6)
        rows.append({
            "node_id":                node,
            "degree_centrality":      round(d, 6),
            "betweenness_centrality": round(b, 6),
            "in_degree_centrality":   round(i, 6),
            "risk_score":             risk,
        })

    return (
        pd.DataFrame(rows)
        .sort_values("risk_score", ascending=False)
        .reset_index(drop=True)
    )


def get_network_summary(G):
    """
    Print a summary of the transaction network.
    Useful for quick sanity checks before running detection functions.
    """
    print(f"Nodes (accounts)   : {G.number_of_nodes():,}")
    print(f"Edges (transactions): {G.number_of_edges():,}")
    print(f"Is directed        : {G.is_directed()}")

    if G.number_of_nodes() > 0:
        degree_vals = [d for _, d in G.degree()]
        print(f"Avg degree         : {round(sum(degree_vals)/len(degree_vals), 2)}")
        print(f"Max degree node    : {max(G.degree(), key=lambda x: x[1])[0]}")