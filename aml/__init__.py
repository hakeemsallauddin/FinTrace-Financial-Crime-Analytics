"""aml-analytics: open-source toolkit for AML and fraud analytics."""

__version__ = "1.1.0"

from aml import synthetic, graph, velocity, patterns, anomaly, fraud
from aml.fraud import APPFraudScorer, ColumnConfig, ScoringWeights, score_transactions

__all__ = [
    "synthetic",
    "graph",
    "velocity",
    "patterns",
    "anomaly",
    "fraud",
    "APPFraudScorer",
    "ColumnConfig",
    "ScoringWeights",
    "score_transactions",
]