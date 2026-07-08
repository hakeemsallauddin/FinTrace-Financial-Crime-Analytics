import pandas as pd
import plotly.graph_objects as go
import networkx as nx
import streamlit as st

from dashboard.data_loader import load_transactions, run_analysis


st.set_page_config(
    page_title="FinTrace",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def get_transactions():
    return load_transactions()


@st.cache_resource
def get_analysis():
    df = get_transactions()
    return run_analysis(df)


df = get_transactions()
analysis = get_analysis()


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.title("FinTrace")
    st.caption("Investigation Workspace")

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Pattern Alerts",
            "Network Analysis",
            "Account Investigation",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.caption("Dataset")
    st.write(f"{len(df):,} transactions")
    st.write(f"{analysis['network'].number_of_nodes():,} accounts")


# ---------------- OVERVIEW PAGE ----------------

if page == "Overview":

    st.title("Investigation Overview")
    st.caption(
        "Financial crime monitoring and transaction network analytics"
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Transactions",
        f"{len(df):,}",
    )

    col2.metric(
        "Accounts",
        f"{analysis['network'].number_of_nodes():,}",
    )

    col3.metric(
        "Structuring Cases",
        len(analysis["graph_structuring_cases"]),
    )

    col4.metric(
        "Layering Chains",
        len(analysis["layering_cases"]),
    )

    st.divider()

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Recent Transaction Activity")

        st.dataframe(
            df[
                [
                    "transaction_id",
                    "sender_id",
                    "receiver_id",
                    "amount",
                    "timestamp",
                    "channel",
                    "country",
                ]
            ].head(15),
            width="stretch",
            hide_index=True,
        )

    with right:
        st.subheader("Dataset Profile")

        label_counts = (
            df["label"]
            .value_counts()
            .rename_axis("Category")
            .reset_index(name="Transactions")
        )

        st.dataframe(
            label_counts,
            width="stretch",
            hide_index=True,
        )


# ---------------- PATTERN ALERTS ----------------

elif page == "Pattern Alerts":

    st.title("Pattern Alerts")
    st.caption(
        "Review transaction behaviour identified by the detection engine"
    )

    st.divider()

    pattern_results = analysis["patterns"]

    rule_structuring = pattern_results["structuring"]
    graph_structuring = analysis["graph_structuring_cases"]
    layering_cases = analysis["layering_cases"]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Rule-Based Alerts",
        len(rule_structuring),
    )

    col2.metric(
        "Network Structuring Cases",
        len(graph_structuring),
    )

    col3.metric(
        "Layering Chains",
        len(layering_cases),
    )

    st.divider()

    alert_type = st.selectbox(
        "Alert Category",
        [
            "Rule-Based Structuring",
            "Network Structuring",
            "Layering Chains",
        ],
    )

    # ---------------- RULE-BASED STRUCTURING ----------------

    if alert_type == "Rule-Based Structuring":

        st.subheader("Rule-Based Structuring Alerts")

        st.caption(
            "Accounts showing repeated transaction activity within "
            "defined time and amount thresholds."
        )

        display_df = rule_structuring.copy()

        display_df["total_amount"] = display_df[
            "total_amount"
        ].round(2)

        display_df["avg_amount"] = display_df[
            "avg_amount"
        ].round(2)

        display_df["risk_score"] = display_df[
            "risk_score"
        ].round(2)

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
        )

    # ---------------- NETWORK STRUCTURING ----------------

    elif alert_type == "Network Structuring":

        st.subheader("Network Structuring Cases")

        st.caption(
            "Accounts distributing funds across multiple counterparties "
            "within a limited time window."
        )

        graph_df = pd.DataFrame(graph_structuring)

        graph_df["edge_list"] = graph_df["edge_list"].apply(
            lambda edges: " | ".join(
                f"{sender} → {receiver}"
                for sender, receiver in edges
            )
        )

        st.dataframe(
            graph_df,
            width="stretch",
            hide_index=True,
        )

    # ---------------- LAYERING CHAINS ----------------

    elif alert_type == "Layering Chains":

        st.subheader("Multi-Hop Layering Chains")

        st.caption(
            "Potential movement of funds through connected accounts "
            "across multiple transaction hops."
        )

        for index, case in enumerate(layering_cases, start=1):

            chain_text = " → ".join(case["chain"])

            with st.expander(
                f"Case {index} · "
                f"{case['chain_length']} hops · "
                f"{case['total_amount']:,.2f}"
            ):

                st.write("**Fund Flow**")
                st.code(chain_text)

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Chain Length",
                    case["chain_length"],
                )

                col2.metric(
                    "Total Amount",
                    f"{case['total_amount']:,.2f}",
                )

                col3.metric(
                    "Accounts",
                    len(case["chain"]),
                )

                st.write(
                    f"**Start Account:** {case['start_node']}"
                )

                st.write(
                    f"**End Account:** {case['end_node']}"
                )


# ---------------- NETWORK ANALYSIS ----------------

elif page == "Network Analysis":

    st.title("Network Analysis")
    st.caption(
        "Trace connected accounts and multi-hop movement of funds"
    )

    st.divider()

    network = analysis["network"]
    centrality = analysis["centrality_scores"].copy()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Accounts", network.number_of_nodes())
    col2.metric("Connections", network.number_of_edges())
    col3.metric("Layering Chains", len(analysis["layering_cases"]))
    col4.metric(
        "Highest Risk Score",
        f"{centrality['risk_score'].max():.3f}",
    )

    st.divider()

    st.subheader("Highest-Risk Network Accounts")
    st.caption(
        "Accounts ranked using connectivity, intermediary position, "
        "and incoming transaction relationships."
    )

    top_accounts = centrality.head(10).copy()

    top_accounts[
        [
            "degree_centrality",
            "betweenness_centrality",
            "in_degree_centrality",
            "risk_score",
        ]
    ] = top_accounts[
        [
            "degree_centrality",
            "betweenness_centrality",
            "in_degree_centrality",
            "risk_score",
        ]
    ].round(3)

    st.dataframe(
        top_accounts,
        width="stretch",
        hide_index=True,
    )

    st.divider()

    st.subheader("Layering Chain Explorer")

    selected_case = st.selectbox(
        "Select a detected chain",
        range(len(analysis["layering_cases"])),
        format_func=lambda index: (
            f"Case {index + 1} · "
            f"{analysis['layering_cases'][index]['chain_length']} hops · "
            f"{analysis['layering_cases'][index]['total_amount']:,.2f}"
        ),
    )

    case = analysis["layering_cases"][selected_case]

    st.write("**Detected Fund Flow**")

    st.code(
        " → ".join(case["chain"]),
        language=None,
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Hops", case["chain_length"])
    col2.metric("Accounts", len(case["chain"]))
    col3.metric(
        "Total Amount",
        f"{case['total_amount']:,.2f}",
    )

    st.write(f"**Origin Account:** {case['start_node']}")
    st.write(f"**Destination Account:** {case['end_node']}")
    st.divider()

    st.subheader("Interactive Fund Flow Network")
    st.caption(
        "Visual representation of the selected layering chain."
    )

    chain_nodes = case["chain"]

    chain_graph = network.subgraph(chain_nodes).copy()

    positions = nx.spring_layout(
        chain_graph,
        seed=42,
    )

    edge_x = []
    edge_y = []

    for source, target in chain_graph.edges():

        x0, y0 = positions[source]
        x1, y1 = positions[target]

        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        hoverinfo="none",
        line=dict(
            width=2,
        ),
    )

    node_x = []
    node_y = []
    node_text = []

    for node in chain_graph.nodes():

        x, y = positions[node]

        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        hovertext=node_text,
        hoverinfo="text",
        marker=dict(
            size=28,
            line=dict(width=2),
        ),
    )

    figure = go.Figure(
        data=[
            edge_trace,
            node_trace,
        ]
    )

    figure.update_layout(
        height=500,
        showlegend=False,
        hovermode="closest",
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20,
        ),
        xaxis=dict(
            visible=False,
        ),
        yaxis=dict(
            visible=False,
        ),
    )

    st.plotly_chart(
        figure,
        width="stretch",
    )


# ---------------- ACCOUNT INVESTIGATION ----------------

elif page == "Account Investigation":

    st.title("Account Investigation")
    st.caption(
        "Review account activity, counterparties, network risk, and detected cases"
    )

    st.divider()

    network = analysis["network"]
    centrality = analysis["centrality_scores"].copy()

    all_accounts = sorted(
        set(df["sender_id"]).union(set(df["receiver_id"]))
    )

    selected_account = st.selectbox(
        "Select Account",
        all_accounts,
    )

    # ---------------- ACCOUNT TRANSACTIONS ----------------

    sent_transactions = df[
        df["sender_id"] == selected_account
    ].copy()

    received_transactions = df[
        df["receiver_id"] == selected_account
    ].copy()

    account_transactions = df[
        (df["sender_id"] == selected_account)
        | (df["receiver_id"] == selected_account)
    ].copy()

    # ---------------- ACCOUNT RISK ----------------

    risk_row = centrality[
        centrality["node_id"] == selected_account
    ]

    if not risk_row.empty:
        risk_score = risk_row.iloc[0]["risk_score"]
        degree_score = risk_row.iloc[0]["degree_centrality"]
        betweenness_score = risk_row.iloc[0]["betweenness_centrality"]
    else:
        risk_score = 0
        degree_score = 0
        betweenness_score = 0

    # ---------------- METRICS ----------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Transactions",
        len(account_transactions),
    )

    col2.metric(
        "Sent",
        len(sent_transactions),
    )

    col3.metric(
        "Received",
        len(received_transactions),
    )

    col4.metric(
        "Network Risk Score",
        f"{risk_score:.3f}",
    )

    st.divider()

    # ---------------- RISK PROFILE ----------------

    left, right = st.columns([1, 2])

    with left:

        st.subheader("Risk Profile")

        st.write(
            f"**Degree Centrality:** {degree_score:.3f}"
        )

        st.write(
            f"**Betweenness Centrality:** {betweenness_score:.3f}"
        )

        if risk_score >= 0.35:
            st.error("Higher network-risk profile")

        elif risk_score >= 0.25:
            st.warning("Moderate network-risk profile")

        else:
            st.success("Lower network-risk profile")

    # ---------------- COUNTERPARTIES ----------------

    with right:

        st.subheader("Top Counterparties")

        sent_counterparties = (
            sent_transactions["receiver_id"]
            .value_counts()
            .rename_axis("counterparty")
            .reset_index(name="transactions")
        )

        received_counterparties = (
            received_transactions["sender_id"]
            .value_counts()
            .rename_axis("counterparty")
            .reset_index(name="transactions")
        )

        counterparties = pd.concat(
            [
                sent_counterparties,
                received_counterparties,
            ]
        )

        counterparties = (
            counterparties
            .groupby("counterparty", as_index=False)["transactions"]
            .sum()
            .sort_values(
                "transactions",
                ascending=False,
            )
            .head(10)
        )

        st.dataframe(
            counterparties,
            width="stretch",
            hide_index=True,
        )

    st.divider()

    # ---------------- CASE INVOLVEMENT ----------------

    st.subheader("Detected Case Involvement")

    structuring_cases = [
        case
        for case in analysis["graph_structuring_cases"]
        if case["sender_id"] == selected_account
    ]

    layering_cases = [
        case
        for case in analysis["layering_cases"]
        if selected_account in case["chain"]
    ]

    col1, col2 = st.columns(2)

    col1.metric(
        "Structuring Cases",
        len(structuring_cases),
    )

    col2.metric(
        "Layering Chains",
        len(layering_cases),
    )

    if structuring_cases:

        st.write("**Structuring Case Details**")

        st.dataframe(
            pd.DataFrame(structuring_cases),
            width="stretch",
            hide_index=True,
        )

    if layering_cases:

        st.write("**Layering Chain Involvement**")

        for index, case in enumerate(layering_cases, start=1):

            st.code(
                " → ".join(case["chain"]),
                language=None,
            )

    if not structuring_cases and not layering_cases:

        st.info(
            "This account does not currently appear in a detected "
            "network structuring or layering case."
        )

        st.divider()

    # ---------------- INVESTIGATION SUMMARY ----------------

    st.subheader("Investigation Summary")
    st.caption(
        "System-generated case context based on transaction and network indicators"
    )

    indicators = []

    if risk_score >= 0.35:
        indicators.append(
            "Account has a comparatively high network-risk score."
        )

    elif risk_score >= 0.25:
        indicators.append(
            "Account has a moderate network-risk score."
        )

    if degree_score >= 0.75:
        indicators.append(
            "Account is highly connected within the transaction network."
        )

    if betweenness_score >= 0.02:
        indicators.append(
            "Account may act as an intermediary between other accounts."
        )

    if structuring_cases:
        indicators.append(
            f"Account appears as the sender in "
            f"{len(structuring_cases)} detected structuring case(s)."
        )

    if layering_cases:
        indicators.append(
            f"Account appears in "
            f"{len(layering_cases)} detected multi-hop layering chain(s)."
        )

    if indicators:

        for indicator in indicators:
            st.write(f"- {indicator}")

    else:
        st.write(
            "No significant investigation indicators were identified "
            "for this account."
        )

    st.write("**Review Priority**")

    if layering_cases or structuring_cases or risk_score >= 0.35:
        st.error(
            "HIGH — Review the account's transaction sequence, "
            "counterparties, and detected network relationships."
        )

    elif risk_score >= 0.25:
        st.warning(
            "MEDIUM — Review unusual transaction behaviour and "
            "network connections."
        )

    else:
        st.success(
            "LOW — No major case indicators currently require "
            "priority review."
        )

        st.info(
        "This output is an analytical screening aid. "
        "A flagged indicator is not proof of financial crime "
        "and should be reviewed with supporting evidence."
    )

    # ---------------- CASE REPORT EXPORT ----------------

    if layering_cases or structuring_cases or risk_score >= 0.35:
        review_priority = "HIGH"

    elif risk_score >= 0.25:
        review_priority = "MEDIUM"

    else:
        review_priority = "LOW"

    case_report = account_transactions.copy()

    case_report.insert(
        0,
        "investigated_account",
        selected_account,
    )

    case_report.insert(
        1,
        "network_risk_score",
        round(risk_score, 3),
    )

    case_report.insert(
        2,
        "degree_centrality",
        round(degree_score, 3),
    )

    case_report.insert(
        3,
        "betweenness_centrality",
        round(betweenness_score, 3),
    )

    case_report.insert(
        4,
        "structuring_cases",
        len(structuring_cases),
    )

    case_report.insert(
        5,
        "layering_chains",
        len(layering_cases),
    )

    case_report.insert(
        6,
        "review_priority",
        review_priority,
    )

    report_csv = case_report.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Export Investigation Case Report",
        data=report_csv,
        file_name=(
            f"FinTrace_{selected_account}_Case_Report.csv"
        ),
        mime="text/csv",
        width="stretch",
    )

    st.divider()

    # ---------------- TRANSACTION HISTORY ----------------

    # ---------------- TRANSACTION HISTORY ----------------

    st.subheader("Transaction History")

    account_transactions = account_transactions.sort_values(
        "timestamp",
        ascending=False,
    )

    st.dataframe(
        account_transactions[
            [
                "transaction_id",
                "sender_id",
                "receiver_id",
                "amount",
                "timestamp",
                "channel",
                "country",
            ]
        ],
        width="stretch",
        hide_index=True,
    )