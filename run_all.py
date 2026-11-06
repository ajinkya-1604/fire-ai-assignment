"""
Single-Command End-to-End Experiment Execution Harness.
Fulfills User Requirement:
    "The following command must reproduce the experiments:
     python run_all.py
     It should:
     1. Check configuration.
     2. Check data availability.
     3. Run Project A tests.
     4. Run Project A benchmarks.
     5. Run Project B profiling.
     6. Run corruption experiments.
     7. Run all detector benchmarks.
     8. Run the hybrid pipeline.
     9. Generate result tables and reports.
     10. Save outputs in reports/."
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure project root in path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_a.benchmarks.tax_benchmark import print_benchmark_table, run_benchmarks
from project_b.benchmarks.dq_benchmark import print_dq_benchmark_table, run_dq_benchmarks
from project_b.data.fetch_nyc_311 import get_nyc_311_dataset
from project_b.profiling.profiler import profile_all_datasets
from shared.config import DATA_B_DIR, REPORTS_DIR
from shared.gemini_client import GeminiClient
from shared.logging_config import setup_logging

logger = setup_logging()


def print_step(step_num: int, title: str):
    print("\n" + "=" * 80)
    print(f"STEP {step_num}: {title.upper()}")
    print("=" * 80)


def step_1_check_configuration() -> Dict[str, Any]:
    print_step(1, "Checking Environment & API Configuration")
    gemini_client = GeminiClient()
    is_gemini_ready = gemini_client.is_configured()

    status = {
        "python_version": sys.version.split()[0],
        "project_root": str(PROJECT_ROOT),
        "reports_dir": str(REPORTS_DIR),
        "gemini_api_configured": is_gemini_ready,
        "gemini_model": gemini_client.model_name,
    }

    print(f"Python Runtime:        {status['python_version']}")
    print(f"Project Root:          {status['project_root']}")
    print(f"Reports Output:        {status['reports_dir']}")
    if is_gemini_ready:
        print(f"Gemini API:            [CONNECTED] (Model: {status['gemini_model']})")
    else:
        print("Gemini API:            [NOT CONFIGURED] (Running deterministic modules; LLM marked NOT RUN)")
        print("                       To enable live Gemini calls: add GEMINI_API_KEY in .env")

    return status


def step_2_check_data_availability() -> bool:
    print_step(2, "Checking Dataset Availability & Provenance")
    try:
        df, prov = get_nyc_311_dataset(source="auto", limit=1000)
        print(f"Dataset Loaded:        {prov['source']} ({prov['rows']} total rows available)")
        print(f"Is Synthetic:          {prov['is_synthetic']}")
        print(f"Sample Batch Size:     {len(df)} rows, {len(df.columns)} columns")
        print("Dataset verification:  [PASS]")
        return True
    except Exception as e:
        print(f"Dataset verification failed: {e}")
        print("Dataset verification:  [FAIL]")
        return False


def step_3_run_project_a_tests() -> bool:
    print_step(3, "Running Project A Automated Tests (Pytest)")
    cmd = [sys.executable, "-m", "pytest", "project_a/tests", "-q"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        print("Project A tests:       [FAIL]")
        return False
    print("Project A tests:       [PASS]")
    return True


def step_4_run_project_a_benchmarks():
    print_step(4, "Running Project A Multi-Implementation Benchmarks")
    # Fresh benchmark execution with deterministic seed
    res = run_benchmarks(sample_size=40, determinism_runs=10)
    print_benchmark_table(res)


def step_5_run_project_b_profiling():
    print_step(5, "Running Project B Data Profiling (Real & Synthetic)")
    rep = profile_all_datasets()
    for k, v in rep.items():
        print(f"  [{k.upper()}] Profiled {v['summary']['total_rows']} rows, {v['summary']['total_columns']} cols (Synthetic={v['provenance']['is_synthetic']})")
    print("Data Profiling:        [PASS]")


def step_6_7_8_run_project_b_corruptions_and_detectors():
    print_step(6, "Running 12 Corruption Injections, Detector Families & Hybrid Pipeline Benchmarks")
    # Fresh benchmark execution with seed=42
    res = run_dq_benchmarks(batch_size=500, seed=42)
    print_dq_benchmark_table(res)


def step_9_run_project_b_tests() -> bool:
    print_step(9, "Running Project B Automated Tests (Pytest)")
    cmd = [sys.executable, "-m", "pytest", "project_b/tests", "-q"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        print("Project B tests:       [FAIL]")
        return False
    print("Project B tests:       [PASS]")
    return True


def step_10_verify_reports_and_output() -> bool:
    print_step(10, "Verifying Generated Reports & Output Artifacts")
    
    # Required JSON Benchmark Artifacts
    required_json_artifacts = [
        REPORTS_DIR / "project_a_benchmark_results.json",
        REPORTS_DIR / "project_b_profile_report.json",
        REPORTS_DIR / "project_b_benchmark_results.json",
    ]

    # Required Documentation Deliverables
    required_markdown_reports = [
        PROJECT_ROOT / "RESULTS_A.md",
        PROJECT_ROOT / "RESULTS_B.md",
        PROJECT_ROOT / "DECISION_MATRIX.md",
        PROJECT_ROOT / "AI_USAGE.md",
        PROJECT_ROOT / "README.md",
    ]

    all_ok = True

    print("\n--- JSON Benchmark Outputs ---")
    for p in required_json_artifacts:
        if p.exists() and p.stat().st_size > 0:
            size_kb = p.stat().st_size / 1024.0
            print(f"  [PASS] {p.name:<35} ({size_kb:.1f} KB)")
        else:
            print(f"  [FAIL] {p.name:<35} (MISSING OR EMPTY)")
            all_ok = False

    print("\n--- Markdown Audit & Evaluation Reports ---")
    for p in required_markdown_reports:
        if p.exists() and p.stat().st_size > 0:
            size_kb = p.stat().st_size / 1024.0
            print(f"  [PASS] {p.name:<35} ({size_kb:.1f} KB)")
        else:
            print(f"  [FAIL] {p.name:<35} (MISSING OR EMPTY)")
            all_ok = False

    return all_ok


def main():
    start_time = time.perf_counter()
    config = step_1_check_configuration()
    
    if not step_2_check_data_availability():
        print("\nERROR: Step 2 (Data Availability) failed. Aborting execution.")
        sys.exit(1)

    if not step_3_run_project_a_tests():
        print("\nERROR: Step 3 (Project A Tests) failed. Aborting execution.")
        sys.exit(1)

    try:
        step_4_run_project_a_benchmarks()
    except Exception as e:
        print(f"\nERROR in Step 4 (Project A Benchmarks): {e}")
        sys.exit(1)

    try:
        step_5_run_project_b_profiling()
    except Exception as e:
        print(f"\nERROR in Step 5 (Project B Profiling): {e}")
        sys.exit(1)

    try:
        step_6_7_8_run_project_b_corruptions_and_detectors()
    except Exception as e:
        print(f"\nERROR in Step 6-8 (Project B Benchmarks): {e}")
        sys.exit(1)

    if not step_9_run_project_b_tests():
        print("\nERROR: Step 9 (Project B Tests) failed. Aborting execution.")
        sys.exit(1)

    artifacts_verified = step_10_verify_reports_and_output()
    elapsed = time.perf_counter() - start_time

    if not artifacts_verified:
        print("\n" + "=" * 80)
        print("EXPERIMENT EXECUTION FAILED: Missing one or more required output artifacts!")
        print("=" * 80)
        sys.exit(1)

    print("\n" + "=" * 80)
    print("ALL EXPERIMENTS SUCCESSFULLY EXECUTED, VERIFIED, AND REPRODUCED!")
    print(f"Status: PASS | Deterministic Seed: 42 | Elapsed: {elapsed:.2f}s")
    print("=" * 80)
    print("Interactive Streamlit Dashboard can be launched with:")
    print("    streamlit run dashboard/app.py\n")


if __name__ == "__main__":
    main()
