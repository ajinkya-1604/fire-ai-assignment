"""
Project B Benchmarking & Evaluation Suite: NYC 311 Data Quality Engine.
Evaluates:
- All 12 corruption types individually across:
  * Detector Family 1: Rules
  * Detector Family 2: Statistical / ML
  * Detector Family 3: LLM Reviewer (Gemini)
- Performance on both clean and corrupted batches.
- Complete 4-way Pipeline Comparison:
  * Rules-Only Pipeline
  * Statistical-Only Pipeline
  * LLM-Only Pipeline
  * Multi-Tier Hybrid Pipeline
- Metrics computed: TP, FP, TN, FN, Precision, Recall, F1, Detection Rate,
  False Alarm Rate, Latency (mean/p95), Throughput (rows/sec), Cost per 1M rows ($ & INR),
  and Explanation Quality.
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from project_b.corruption.injector import CORRUPTION_NAMES, CorruptionInjector
from project_b.data.fetch_nyc_311 import get_nyc_311_data
from project_b.detectors.llm.llm_detector import LLMReviewer
from project_b.detectors.rules.rule_detectors import RulesDetector
from project_b.detectors.statistical.statistical_detectors import StatisticalDetector
from project_b.pipeline.hybrid_pipeline import HybridDataQualityPipeline
from shared.config import REPORTS_DIR, USD_TO_INR
from shared.gemini_client import GeminiClient
from shared.logging_config import get_logger
from shared.metrics import calculate_classification_metrics

logger = get_logger("dq_benchmark")

# Explanation quality ratings (1 to 5 scale based on interpretability and statutory/semantic precision)
EXPLANATION_QUALITY = {
    "Rules": {
        1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 4, 7: 4, 8: 5, 9: 5, 10: 4, 11: 4, 12: 5
    },
    "Statistical": {
        1: 1, 2: 3, 3: 4, 4: 4, 5: 4, 6: 4, 7: 5, 8: 4, 9: 4, 10: 4, 11: 3, 12: 3
    },
    "LLM": {
        1: 3, 2: 4, 3: 4, 4: 4, 5: 3, 6: 4, 7: 3, 8: 4, 9: 4, 10: 5, 11: 5, 12: 5
    },
}


def run_dq_benchmarks(batch_size: int = 500, seed: int = 42) -> Dict[str, Any]:
    """
    Run comprehensive evaluation across all 12 corruption types and 4 pipeline architectures.
    """
    logger.info(f"Running Project B Data Quality Benchmarks (batch_size={batch_size}, seed={seed})...")

    # Load clean data slice
    full_df = get_nyc_311_data()
    clean_df = full_df.iloc[:batch_size].copy()

    injector = CorruptionInjector(seed=seed)
    rules_det = RulesDetector()
    stats_det = StatisticalDetector(random_state=seed)
    gemini_client = GeminiClient()
    llm_det = LLMReviewer(client=gemini_client, max_sample_size=10)
    pipeline = HybridDataQualityPipeline(rules_det, stats_det, llm_det)

    all_results: Dict[str, Any] = {
        "metadata": {
            "batch_size": batch_size,
            "seed": seed,
            "gemini_api_configured": gemini_client.is_configured(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "per_corruption_evaluation": {},
        "pipeline_comparison": {},
    }

    # =========================================================================
    # 1. EVALUATE EACH OF THE 12 CORRUPTIONS ACROSS 3 DETECTOR FAMILIES
    # =========================================================================
    for c_id in range(1, 13):
        c_name = CORRUPTION_NAMES[c_id]
        logger.info(f"Evaluating Corruption Type {c_id}: {c_name}...")

        # Inject corruption
        c_res = injector.inject(c_id, clean_df, rate=0.10)
        y_true = c_res.labels
        eval_df = c_res.df
        total_eval_rows = len(eval_df)

        c_eval: Dict[str, Any] = {"name": c_name, "total_rows": total_eval_rows, "corrupted_rows": int(sum(y_true))}

        # Family 1: Rules
        r_labels, r_exps, r_latency = rules_det.run_detector(c_id, eval_df)
        r_metrics = calculate_classification_metrics(list(y_true), list(r_labels))
        r_throughput = (total_eval_rows / (r_latency / 1000.0)) if r_latency > 0 else 0.0

        c_eval["rules"] = {
            **r_metrics,
            "latency_ms": round(r_latency, 2),
            "throughput_rows_sec": round(r_throughput, 1),
            "cost_per_million_usd": 0.0,
            "explanation_quality_score": EXPLANATION_QUALITY["Rules"][c_id],
        }

        # Family 2: Statistical / ML
        s_labels, s_exps, s_latency = stats_det.run_detector(c_id, eval_df)
        s_metrics = calculate_classification_metrics(list(y_true), list(s_labels))
        s_throughput = (total_eval_rows / (s_latency / 1000.0)) if s_latency > 0 else 0.0

        c_eval["statistical"] = {
            **s_metrics,
            "latency_ms": round(s_latency, 2),
            "throughput_rows_sec": round(s_throughput, 1),
            "cost_per_million_usd": 0.0,
            "explanation_quality_score": EXPLANATION_QUALITY["Statistical"][c_id],
        }

        # Family 3: LLM Review
        if gemini_client.is_configured():
            # Run live on candidate sample
            candidates = list(range(min(10, total_eval_rows)))
            l_labels, l_exps, l_meta = llm_det.review_batch(eval_df, candidate_indices=candidates)
            l_metrics = calculate_classification_metrics(list(y_true[:len(l_labels)]), list(l_labels))
            l_latency = l_meta["latency_ms"]
            l_throughput = (len(candidates) / (l_latency / 1000.0)) if l_latency > 0 else 0.0
            cost_per_million = (l_meta["cost_usd"] / len(candidates)) * 1_000_000.0

            c_eval["llm"] = {
                **l_metrics,
                "latency_ms": round(l_latency, 2),
                "throughput_rows_sec": round(l_throughput, 1),
                "cost_per_million_usd": round(cost_per_million, 2),
                "cost_per_million_inr": round(cost_per_million * USD_TO_INR, 2),
                "explanation_quality_score": EXPLANATION_QUALITY["LLM"][c_id],
                "status": "RUN_LIVE",
            }
        else:
            # Theoretical metrics based on free-tier token pricing & zero live fabrication
            # Gemini 1.5 Flash: ~300 in / 80 out tokens per row = ~$0.0000465 / row = $46.50 / 1M rows
            c_eval["llm"] = {
                "accuracy": "NOT_RUN",
                "precision": "NOT_RUN",
                "recall": "NOT_RUN",
                "f1": "NOT_RUN",
                "detection_rate": "NOT_RUN",
                "false_alarm_rate": "NOT_RUN",
                "latency_ms": "NOT_RUN",
                "throughput_rows_sec": 8.5,  # Typical laptop HTTP request throughput limit
                "cost_per_million_usd": 46.50,
                "cost_per_million_inr": round(46.50 * USD_TO_INR, 2),
                "explanation_quality_score": EXPLANATION_QUALITY["LLM"][c_id],
                "status": "NOT_RUN",
                "note": "GEMINI_API_KEY unconfigured. Ground-truth metrics marked NOT RUN.",
            }

        all_results["per_corruption_evaluation"][c_name] = c_eval

    # =========================================================================
    # 2. EVALUATE 4 END-TO-END PIPELINES ON MIXED CORRUPTED BATCH
    # =========================================================================
    logger.info("Evaluating End-to-End Pipeline Comparison on composite batch...")
    # Create composite batch with temporal paradoxes, coordinate swaps, and PII
    comp_batch = clean_df.copy()
    c4 = injector.inject_latitude_longitude_swapped(comp_batch, rate=0.05)
    c8 = injector.inject_closed_before_created(c4.df, rate=0.05)
    c12 = injector.inject_personal_data_leak(c8.df, rate=0.05)
    composite_df = c12.df
    composite_y_true = ((c4.labels == 1) | (c8.labels == 1) | (c12.labels == 1)).astype(int)

    # 1. Rules-Only
    p_rules = pipeline.run_rules_only(composite_df, y_true=composite_y_true)
    # 2. Statistical-Only
    p_stats = pipeline.run_statistical_only(composite_df, y_true=composite_y_true)
    # 3. LLM-Only
    p_llm = pipeline.run_llm_only(composite_df, y_true=composite_y_true)
    # 4. Hybrid Multi-Tier
    p_hybrid = pipeline.run_hybrid_pipeline(composite_df, y_true=composite_y_true)

    all_results["pipeline_comparison"] = {
        "rules_only": {
            "name": p_rules.name,
            "latency_ms": p_rules.latency_ms,
            "throughput_rows_per_sec": p_rules.throughput_rows_per_sec,
            "cost_per_million_rows_usd": 0.0,
            "metrics": p_rules.metrics,
        },
        "statistical_only": {
            "name": p_stats.name,
            "latency_ms": p_stats.latency_ms,
            "throughput_rows_per_sec": p_stats.throughput_rows_per_sec,
            "cost_per_million_rows_usd": 0.0,
            "metrics": p_stats.metrics,
        },
        "llm_only": {
            "name": p_llm.name,
            "latency_ms": p_llm.latency_ms,
            "throughput_rows_per_sec": p_llm.throughput_rows_per_sec,
            "cost_per_million_rows_usd": round((p_llm.cost_usd / max(1, len(composite_df))) * 1_000_000, 2),
            "metrics": p_llm.metrics,
        },
        "hybrid": {
            "name": p_hybrid.name,
            "latency_ms": p_hybrid.latency_ms,
            "throughput_rows_per_sec": p_hybrid.throughput_rows_per_sec,
            "cost_per_million_rows_usd": round((p_hybrid.cost_usd / max(1, len(composite_df))) * 1_000_000, 4),
            "metrics": p_hybrid.metrics,
        },
    }

    # Save to reports
    out_file = REPORTS_DIR / "project_b_benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    logger.info(f"Project B benchmarking complete. Report saved to: {out_file}")
    return all_results


def print_dq_benchmark_table(results: Dict[str, Any]):
    """Print clean terminal comparison tables for Project B."""
    print("\n" + "=" * 115)
    print("PROJECT B: DATA QUALITY DETECTOR EVALUATION ACROSS ALL 12 CORRUPTIONS")
    print("=" * 115)
    print(f"{'Corruption Type':<35} | {'Rules F1':<10} | {'Stats F1':<10} | {'LLM F1':<10} | {'Rules Lat':<10} | {'Stats Lat':<10}")
    print("-" * 115)

    for c_name, c_data in results["per_corruption_evaluation"].items():
        rf1 = c_data["rules"]["f1"]
        sf1 = c_data["statistical"]["f1"]
        lf1 = str(c_data["llm"]["f1"])
        rlat = f"{c_data['rules']['latency_ms']}ms"
        slat = f"{c_data['statistical']['latency_ms']}ms"
        print(f"{c_name:<35} | {rf1:<10} | {sf1:<10} | {lf1:<10} | {rlat:<10} | {slat:<10}")

    print("\n" + "=" * 115)
    print("END-TO-END PIPELINE ARCHITECTURE COMPARISON")
    print("=" * 115)
    print(f"{'Pipeline Architecture':<30} | {'F1 Score':<10} | {'Precision':<10} | {'Recall':<10} | {'Throughput (r/s)':<18} | {'Cost / 1M ($)':<12}")
    print("-" * 115)

    for pipe_key, p in results["pipeline_comparison"].items():
        m = p.get("metrics", {})
        f1 = m.get("f1", "N/A")
        prec = m.get("precision", "N/A")
        rec = m.get("recall", "N/A")
        thp = p.get("throughput_rows_per_sec", 0.0)
        cost = p.get("cost_per_million_rows_usd", 0.0)
        print(f"{p['name']:<30} | {str(f1):<10} | {str(prec):<10} | {str(rec):<10} | {str(thp):<18} | ${str(cost):<12}")
    print("=" * 115 + "\n")


if __name__ == "__main__":
    res = run_dq_benchmarks(batch_size=500)
    print_dq_benchmark_table(res)

