"""
Project B Main Entrypoint: NYC 311 Data Quality Engine CLI & Pipeline Runner.
Usage:
    python project_b/main.py --profile
    python project_b/main.py --benchmark
    python project_b/main.py --inject 8 --rate 0.10
    python project_b/main.py --pipeline
"""

import argparse
import json
from pathlib import Path
import sys

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_b.benchmarks.dq_benchmark import print_dq_benchmark_table, run_dq_benchmarks
from project_b.corruption.injector import CorruptionInjector
from project_b.data.fetch_nyc_311 import get_nyc_311_data
from project_b.pipeline.hybrid_pipeline import HybridDataQualityPipeline
from project_b.profiling.profiler import DataProfiler
from shared.logging_config import setup_logging

logger = setup_logging()


def main():
    parser = argparse.ArgumentParser(description="NYC 311 Data Quality Engine (Project B)")
    parser.add_argument("--profile", action="store_true", help="Run comprehensive data profiling on NYC 311 dataset")
    parser.add_argument("--benchmark", action="store_true", help="Run full benchmark across 12 corruptions & pipelines")
    parser.add_argument("--inject", type=int, choices=list(range(1, 13)), help="Inject specific corruption type (1-12)")
    parser.add_argument("--rate", type=float, default=0.10, help="Corruption injection rate (default: 0.10)")
    parser.add_argument("--pipeline", action="store_true", help="Run Hybrid Data Quality Pipeline on active dataset")
    parser.add_argument("--limit", type=int, default=1000, help="Number of records to process")

    args = parser.parse_args()

    df = get_nyc_311_data(limit=args.limit).iloc[:args.limit].copy()

    if args.profile:
        print("\n>>> Profiling NYC 311 Service Requests Dataset...")
        profiler = DataProfiler(df)
        report = profiler.profile_all()
        print("\n" + "=" * 60)
        print("DATA PROFILING SUMMARY")
        print("=" * 60)
        print(f"Total Rows:            {report['summary']['total_rows']}")
        print(f"Total Columns:         {report['summary']['total_columns']}")
        print(f"Duplicate Rows:        {report['duplicates']['exact_duplicate_rows']}")
        print(f"Date Paradoxes:        {report['date_anomalies'].get('closed_before_created_count', 0)}")
        print(f"Coord Out-of-Bounds:   {report['coordinate_anomalies'].get('out_of_bounds_count', 0)}")
        print(f"ZIP-Borough Mismatches:{report['zip_code_issues'].get('borough_zip_mismatch_count', 0)}")
        print(f"Potential PII Leaks:   {report['pii_findings'].get('total_pii_occurrences', 0)}")
        print("=" * 60 + "\n")
        return

    if args.benchmark:
        print("\n>>> Executing Project B Benchmarks...")
        res = run_dq_benchmarks(batch_size=min(args.limit, 500))
        print_dq_benchmark_table(res)
        return

    if args.inject:
        print(f"\n>>> Injecting Corruption Type {args.inject} (rate={args.rate})...")
        injector = CorruptionInjector()
        res = injector.inject(args.inject, df, rate=args.rate)
        print(f"Original rows: {len(df)} | Corrupted rows: {sum(res.labels)}")
        print(f"Injection summary: {res.summary()}")

        pipe = HybridDataQualityPipeline()
        p_res = pipe.run_hybrid_pipeline(res.df, y_true=res.labels)
        print(f"\nHybrid Pipeline Detection Result:")
        print(f"F1 Score:    {p_res.metrics.get('f1')}")
        print(f"Precision:   {p_res.metrics.get('precision')}")
        print(f"Recall:      {p_res.metrics.get('recall')}")
        print(f"Throughput:  {p_res.throughput_rows_per_sec} rows/sec")
        return

    if args.pipeline:
        print("\n>>> Running Hybrid Pipeline on NYC 311 dataset...")
        pipe = HybridDataQualityPipeline()
        res = pipe.run_hybrid_pipeline(df)
        flagged = sum(res.labels)
        print(f"Processed {len(df)} rows.")
        print(f"Flagged anomalies: {flagged} ({round(flagged/len(df)*100, 2)}%)")
        print(f"Throughput: {res.throughput_rows_per_sec} rows/sec")
        return

    # Default action if no flags provided: Run profile
    print("No flag specified. Running default profiling. Use --help to view CLI options.")
    profiler = DataProfiler(df)
    report = profiler.profile_all()
    print(f"Profiled {len(df)} rows. Results saved to reports/project_b_profile_report.json.")


if __name__ == "__main__":
    main()

