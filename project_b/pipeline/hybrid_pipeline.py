"""
Multi-Tier Hybrid Data Quality Pipeline for NYC 311 Service Requests.
Architecture:
- Tier 1 (Rules): Executes on 100% of incoming rows (O(1) vectorized, $0 cost, catches structural/date/schema/exact dups).
- Tier 2 (Statistical/ML): Executes on batch distributions, spatial clusters, and text features (catches null spikes, coordinate outliers, near-dups).
- Tier 3 (LLM Reviewer): Executes ONLY on ambiguous, unconfirmed, or high-risk candidate records (semantic contradictions, subtle PII).

Provides side-by-side comparison between:
1. Rules-Only Pipeline
2. Statistical-Only Pipeline
3. LLM-Only Pipeline
4. Hybrid Pipeline
"""

import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from project_b.detectors.llm.llm_detector import LLMReviewer
from project_b.detectors.rules.rule_detectors import RulesDetector
from project_b.detectors.statistical.statistical_detectors import StatisticalDetector
from shared.logging_config import get_logger
from shared.metrics import calculate_classification_metrics

logger = get_logger("hybrid_pipeline")


class PipelineResult:
    """Consolidated container for pipeline execution results."""

    def __init__(
        self,
        name: str,
        labels: np.ndarray,
        explanations: List[str],
        latency_ms: float,
        cost_usd: float,
        throughput_rows_per_sec: float,
        metrics: Optional[Dict[str, float]] = None,
    ):
        self.name = name
        self.labels = labels
        self.explanations = explanations
        self.latency_ms = latency_ms
        self.cost_usd = cost_usd
        self.throughput_rows_per_sec = throughput_rows_per_sec
        self.metrics = metrics or {}


class HybridDataQualityPipeline:
    """
    Tiered data quality engine combining Rules, Statistics, and LLMs.
    """

    def __init__(
        self,
        rules_detector: Optional[RulesDetector] = None,
        stat_detector: Optional[StatisticalDetector] = None,
        llm_reviewer: Optional[LLMReviewer] = None,
    ):
        self.rules = rules_detector or RulesDetector()
        self.stats = stat_detector or StatisticalDetector()
        self.llm = llm_reviewer or LLMReviewer()

    # =========================================================================
    # PIPELINE 1: Rules-Only Pipeline
    # =========================================================================
    def run_rules_only(self, df: pd.DataFrame, y_true: Optional[np.ndarray] = None) -> PipelineResult:
        t0 = time.perf_counter()
        total_rows = len(df)
        labels = np.zeros(total_rows, dtype=int)
        explanations = [""] * total_rows

        # Check all rule checks
        checks = [
            self.rules.detect_schema(df),
            self.rules.detect_type_corruption(df),
            self.rules.detect_date_format_switch(df),
            self.rules.detect_coordinate_bounds_and_swap(df),
            self.rules.detect_exact_duplicates(df),
            self.rules.detect_near_duplicates(df),
            self.rules.detect_null_spike(df),
            self.rules.detect_closed_before_created(df),
            self.rules.detect_zip_borough_inconsistency(df),
            self.rules.detect_complaint_descriptor_mismatch(df),
            self.rules.detect_resolution_status_contradiction(df),
            self.rules.detect_pii(df),
        ]

        for check_labels, check_exp in checks:
            mask = check_labels == 1
            labels[mask] = 1
            for idx in np.where(mask)[0]:
                if not explanations[idx]:
                    explanations[idx] = check_exp[idx]

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        throughput = (total_rows / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0

        metrics = calculate_classification_metrics(list(y_true), list(labels)) if y_true is not None else {}
        return PipelineResult(
            name="Rules-Only Pipeline",
            labels=labels,
            explanations=explanations,
            latency_ms=round(elapsed_ms, 2),
            cost_usd=0.0,
            throughput_rows_per_sec=round(throughput, 1),
            metrics=metrics,
        )

    # =========================================================================
    # PIPELINE 2: Statistical-Only Pipeline
    # =========================================================================
    def run_statistical_only(self, df: pd.DataFrame, y_true: Optional[np.ndarray] = None) -> PipelineResult:
        t0 = time.perf_counter()
        total_rows = len(df)
        labels = np.zeros(total_rows, dtype=int)
        explanations = [""] * total_rows

        checks = [
            self.stats.detect_coordinate_lof(df),
            self.stats.detect_null_rate_zscore(df),
            self.stats.detect_near_duplicates_similarity(df),
            self.stats.detect_frequency_anomaly(df, "complaint_type", "descriptor"),
            self.stats.detect_date_format_shift_statistical(df, "created_date"),
            self.stats.detect_duration_isolation_forest(df),
            self.stats.detect_digit_density_anomaly(df),
        ]

        for check_labels, check_exp in checks:
            mask = check_labels == 1
            labels[mask] = 1
            for idx in np.where(mask)[0]:
                if not explanations[idx]:
                    explanations[idx] = check_exp[idx]

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        throughput = (total_rows / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0

        metrics = calculate_classification_metrics(list(y_true), list(labels)) if y_true is not None else {}
        return PipelineResult(
            name="Statistical-Only Pipeline",
            labels=labels,
            explanations=explanations,
            latency_ms=round(elapsed_ms, 2),
            cost_usd=0.0,
            throughput_rows_per_sec=round(throughput, 1),
            metrics=metrics,
        )

    # =========================================================================
    # PIPELINE 3: LLM-Only Pipeline (Sampled)
    # =========================================================================
    def run_llm_only(self, df: pd.DataFrame, y_true: Optional[np.ndarray] = None) -> PipelineResult:
        t0 = time.perf_counter()
        total_rows = len(df)

        labels, explanations, meta = self.llm.review_batch(df)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        throughput = (total_rows / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0

        metrics = calculate_classification_metrics(list(y_true), list(labels)) if y_true is not None else {}
        return PipelineResult(
            name="LLM-Only Pipeline (Sampled)",
            labels=labels,
            explanations=explanations,
            latency_ms=round(elapsed_ms, 2),
            cost_usd=meta.get("cost_usd", 0.0),
            throughput_rows_per_sec=round(throughput, 1),
            metrics=metrics,
        )

    # =========================================================================
    # PIPELINE 4: Multi-Tier Hybrid Pipeline
    # =========================================================================
    def run_hybrid_pipeline(self, df: pd.DataFrame, y_true: Optional[np.ndarray] = None) -> PipelineResult:
        """
        Tier 1: Rules on 100% of rows.
        Tier 2: Statistical anomalies on batch distributions.
        Tier 3: LLM review on flagged or borderline records.
        """
        t0 = time.perf_counter()
        total_rows = len(df)
        final_labels = np.zeros(total_rows, dtype=int)
        final_explanations = [""] * total_rows
        total_cost = 0.0

        # Step 1: Run deterministic fast rules (Tier 1)
        r_res = self.run_rules_only(df)
        final_labels = r_res.labels.copy()
        final_explanations = list(r_res.explanations)

        # Step 2: Run targeted statistical detectors (Tier 2) on batch summaries & suspicious distributions
        stat_checks = [
            self.stats.detect_null_rate_zscore(df),
            self.stats.detect_coordinate_lof(df),
        ]
        for s_labels, s_exps in stat_checks:
            for i, is_stat in enumerate(s_labels):
                if is_stat and final_labels[i] == 0:
                    final_labels[i] = 1
                    final_explanations[i] = f"[Tier 2 Statistical] {s_exps[i]}"

        # Step 3: Run LLM Reviewer (Tier 3) on sampled ambiguous/flagged records
        if self.llm.is_available():
            candidate_indices = np.where(final_labels == 1)[0].tolist()
            if candidate_indices:
                llm_labels, llm_exps, llm_meta = self.llm.review_batch(df, candidate_indices=candidate_indices)
                total_cost += llm_meta.get("cost_usd", 0.0)
                for idx in candidate_indices:
                    if llm_labels[idx] == 1 and llm_exps[idx]:
                        final_explanations[idx] = f"[Tier 3 Verified] {llm_exps[idx]}"

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        throughput = (total_rows / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0

        metrics = calculate_classification_metrics(list(y_true), list(final_labels)) if y_true is not None else {}
        return PipelineResult(
            name="Hybrid Multi-Tier Pipeline",
            labels=final_labels,
            explanations=final_explanations,
            latency_ms=round(elapsed_ms, 2),
            cost_usd=total_cost,
            throughput_rows_per_sec=round(throughput, 1),
            metrics=metrics,
        )
