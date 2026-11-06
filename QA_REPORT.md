# QA & Engineering Audit Report: Rules vs. LLMs Take-Home Assignment

**Auditor Role**: Senior Python Engineer & QA Auditor  
**Repository**: `fire-ai-assignment`  
**Execution Environment**: Python 3.12.3, Windows 11, Pytest 9.2.0, Random Seed 42  
**Audit Date**: November 6, 2026  
**Final Status**: **ALL 8 AUDIT ISSUES RESOLVED (PASS)**  

---

## 1. Executive Audit Summary

Following a comprehensive technical review, 8 critical integrity, consistency, and architectural requirements were audited and remediated across the codebase. All fixes preserve the existing modular architecture without unnecessary rewrites, eliminate all unverified claims, and enforce 100% adherence to the official Fire AI assignment specification.

| Audit Issue | Area | Initial Review Finding | Remediation Action | Status |
|---|---|---|---|:---:|
| **Issue 1** | `RESULTS_A.md` | Reported estimated LLM accuracy and determinism as numerical facts while JSON benchmark recorded `NOT_RUN`. | Replaced all unexecuted LLM measurements with `NOT RUN *(Requires GEMINI_API_KEY)*`. Synchronized all Hand-Coded and Compiled metrics directly to `reports/project_a_benchmark_results.json`. | **RESOLVED** |
| **Issue 2** | `RESULTS_B.md` | Contained non-standard corruption names (mojibake, future dates) and invented LLM F1 scores. | Corrected the report to strictly match the 12 required corruption types. Updated Markdown tables directly from `reports/project_b_benchmark_results.json`. Marked LLM as `NOT RUN`. | **RESOLVED** |
| **Issue 3** | NYC 311 Dataset | Real data was concentrated near Dec 31, 2023 with only 1,000 records; needed seasonal pagination and provenance clarity. | Implemented stratified seasonal pagination across calendar year 2023 (Jan, Apr, Jul, Oct, Dec) retrieving 2,500 real verified records (45 cols). Documented row count in manifest; explicitly labeled as representative sample, not complete archive. Kept synthetic data (10,000 rows, seed 42) strictly separate. | **RESOLVED** |
| **Issue 4** | 12 Corruptions & Composite Pipeline | Needed individual execution, ground-truth label preservation, confusion matrices, detector applicability rationale, and composite pipeline evaluation. | Evaluated all 12 corruptions individually across Rules, Statistical, LLM (NOT RUN), and Hybrid. Computed full confusion matrices. Added End-to-End Composite Multi-Corruption Pipeline benchmark (Hybrid F1 0.3067, 1.0000 recall, 5,352.6 rows/sec). | **RESOLVED** |
| **Issue 5** | `run_all.py` | Could print success even when artifacts were missing; did not fail with non-zero exit codes. | Upgraded step 10 to check all 3 JSON artifacts and 5 Markdown reports. Enforced `sys.exit(1)` on any step failure. Enforced random seed 42. Fresh benchmarks saved on every run. | **RESOLVED** |
| **Issue 6** | Virtual Env & Git | `.gitignore` did not exclude the `fireai/` virtual environment or temporary cache files. | Updated `.gitignore` to explicitly exclude `fireai/`, `venv/`, `.venv/`, `__pycache__/`, `.env`, temporary raw data, and cache files, while preserving `requirements.txt`. | **RESOLVED** |
| **Issue 7** | `AI_USAGE.md` | Contained unsupported claims regarding manual web portal testing and live Gemini arithmetic errors during offline execution. | Clarified the 30 statutory benchmark vectors as legal test vectors verified via unit tests. Strictly separated actual observations from theoretical/literature explanations of LLM tokenization drift. | **RESOLVED** |
| **Issue 8** | Final QA Suite | Full regression test execution across individual and combined test suites. | All 41 pytest tests passed (17 Project A, 24 Project B). `run_all.py` end-to-end verified in 11.39s. Dashboard verified across all 12 corruptions. | **RESOLVED** |

---

## 2. In-Depth Remediation by Issue

### Issue 1: Project A Benchmark Consistency (`RESULTS_A.md`)
- **Root Cause**: `RESULTS_A.md` included placeholder numerical ranges (e.g. `~65-75% accuracy`, `82% determinism`) for the query-time LLM even when `GEMINI_API_KEY` was missing from `.env` and `reports/project_a_benchmark_results.json` showed `"status": "NOT_RUN"`.
- **Fix Applied**:
  - All query-time LLM metrics in `RESULTS_A.md` now explicitly report `NOT RUN *(Requires GEMINI_API_KEY)*`.
  - Added an auditable disclosure in Section 3 separating empirical code measurements from theoretical model cost estimates ($0.0825/1k queries based on Google AI published pricing).
  - Synchronized Hand-Coded Rules (100.0% accuracy, 100.0% determinism, sub-millisecond latency, $0.00 cost) and LLM-Compiled Rules (100.0% accuracy, 100.0% determinism, sub-millisecond latency, $0.00 cost) exactly to the generated JSON benchmark output.

### Issue 2: Project B Corruption Types & Benchmark Integrity (`RESULTS_B.md`)
- **Root Cause**: An earlier version of `RESULTS_B.md` referenced generic data quality corruptions (mojibake, future dates, invalid enums) rather than the 12 specific assignments requirements. Furthermore, placeholder LLM F1 scores were listed.
- **Fix Applied**:
  - Rebuilt `RESULTS_B.md` around the exact 12 required corruption types:
    1. Renamed or dropped column.
    2. Column type change.
    3. Date format switch.
    4. Latitude and longitude swapped.
    5. Exact duplicates.
    6. Near-duplicates.
    7. Null spike in one agency.
    8. Closed date earlier than created date.
    9. ZIP inconsistent with borough.
    10. Complaint Type inconsistent with Descriptor.
    11. Resolution Description contradicting Status.
    12. Personal data inside free-text fields.
  - Replaced all invented LLM F1 scores with `NOT RUN`.
  - Recalculated and populated all Markdown table metrics directly from `reports/project_b_benchmark_results.json`.
  - Added detector applicability explanations for every corruption mode.

### Issue 3: NYC 311 Dataset Pagination, Date Range, & Provenance (`fetch_nyc_311.py`)
- **Root Cause**: The data fetcher previously lacked robust seasonal pagination, retrieving only 1,000 records concentrated around December 31, 2023, and needed strict separation between real Open Data records and synthetic baseline data.
- **Fix Applied**:
  - Implemented stratified seasonal pagination in `fetch_real_nyc_311_data()` querying the official Socrata API (`erm2-nwe9`) across 5 calendar windows (Jan, Apr, Jul, Oct, Dec 2023), filtering strictly on `created_date between ...`.
  - Retrieved and verified 2,500 seasonal 2023 records spanning `2023-01-16 22:13:12` to `2023-12-16 23:59:22` across all 45 native Socrata columns.
  - Saved real data to `project_b/data/nyc_311_2023_real.csv` with audit manifest `project_b/data/nyc_311_real_manifest.json` explicitly recording `is_representative_sample=True` and `is_complete_nyc_archive=False`.
  - Kept synthetic dataset generation strictly separate (`project_b/data/nyc_311_2023_synthetic.csv`, 10,000 records), explicitly tagged with `is_synthetic=True` and `data_source="SYNTHETIC_REPRODUCIBLE_GENERATOR"` with seed 42.
  - Upgraded `project_b/profiling/profiler.py` to profile real and synthetic data separately (`project_b_profile_report_real.json` and `project_b_profile_report_synthetic.json`).

### Issue 4: Individual Evaluation of All 12 Corruptions & Composite Pipeline (`dq_benchmark.py`)
- **Fix Applied**:
  - In `project_b/benchmarks/dq_benchmark.py`, evaluated all 12 required corruption types individually on 500-row batches.
  - Preserved ground-truth binary labels ($1 = \text{corrupted}, 0 = \text{clean}$).
  - Computed full confusion matrix (`total_samples`, `tp`, `fp`, `tn`, `fn`, `accuracy`, `precision`, `recall`, `f1`, `detection_rate`, `false_alarm_rate`, `latency_ms`, `throughput_rows_sec`).
  - Added `APPLICABILITY_RATIONALE` mapping for all 12 corruptions explaining why rules, statistical models, or LLMs are applicable or non-applicable.
  - Added an End-to-End Composite Multi-Corruption Pipeline benchmark combining coordinate swaps (C4), temporal reversals (C8), and PII leaks (C12).
  - Measured End-to-End Metrics:
    - Rules Pipeline: Recall 1.0000, Precision 0.1812, F1 0.3067, Latency 93.41 ms, Throughput 5,352.6 rows/sec, Cost $0.00.
    - Statistical Pipeline: Recall 1.0000, Precision 0.1724, F1 0.2941, Latency 719.54 ms, Throughput 694.9 rows/sec, Cost $0.00.
    - LLM Pipeline: `NOT_RUN` with theoretical economics documented ($46.50/1M rows, ~8.5 rows/sec).
    - Multi-Tier Hybrid Pipeline: Recall 1.0000, Precision 0.1812, F1 0.3067, Latency 93.41 ms, Throughput 5,352.6 rows/sec, Cost $0.00.
  - Clarified that on unredacted real municipal records, natural text noise yields F1 ~0.3067 - 0.3676, while on clean synthetic baseline batches, F1 is 1.0000.

### Issue 5: Reproduction Harness Verification & Error Handling (`run_all.py`)
- **Root Cause**: The verification step printed a success message without asserting that required reports were present and valid.
- **Fix Applied**:
  - Step 10 now strictly verifies all 3 JSON benchmark outputs and all 5 Markdown deliverables.
  - Exits with `sys.exit(1)` immediately if any unit test, benchmark, or required report fails or is missing.
  - Distinguishes `[PASS]`, `[FAIL]`, and `[NOT RUN]` in terminal logging.
  - Uses random seed 42 throughout for 100% deterministic reproducibility.
  - Runs in 11.39 seconds end-to-end.

### Issue 6: Repository Cleanliness & Virtual Environment Isolation (`.gitignore`)
- **Fix Applied**:
  - Updated `.gitignore` to explicitly exclude `fireai/`, `venv/`, `.venv/`, `__pycache__/`, `.env`, temporary raw data, and cache files.
  - Verified that `requirements.txt` is retained.

### Issue 7: AI Usage & Transparency Audit (`AI_USAGE.md`)
- **Fix Applied**:
  - Removed claims regarding 30 manual web calculator entries; accurately described the 30 statutory test vectors derived from enacted legal provisions and verified via automated assertions.
  - Removed references to live Gemini runtime errors during offline benchmark runs.
  - Structured Section 3 into: (3.1) Actual Observations in the Benchmark Run, (3.2) Theoretical Analysis of Tokenization and Discontinuity Drift, and (3.3) Known Vulnerabilities in Semantic Data Quality Detection.

---

## 3. Automated Test Verification Results

### Combined Test Suite (`pytest -v`)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Project\fire-ai-assignment
plugins: anyio-4.16.0
collected 41 items

project_a/tests/test_parser.py::test_sample_descriptions_count PASSED    [  2%]
project_a/tests/test_parser.py::test_standard_assignment_prompt PASSED   [  4%]
project_a/tests/test_parser.py::test_hinglish_query_parsing PASSED       [  7%]
project_a/tests/test_parser.py::test_missing_salary_requests_clarification PASSED [  9%]
project_a/tests/test_parser.py::test_contradictory_salary_detected PASSED [ 12%]
project_a/tests/test_parser.py::test_contradictory_rent_detected PASSED  [ 14%]
project_a/tests/test_parser.py::test_different_salary_formats PASSED     [ 17%]
project_a/tests/test_tax_engine.py::test_officially_verified_cases_count PASSED [ 19%]
project_a/tests/test_tax_engine.py::test_officially_verified_cases_accuracy PASSED [ 21%]
project_a/tests/test_tax_engine.py::test_compiled_engine_equivalence PASSED [ 24%]
project_a/tests/test_tax_engine.py::test_zero_income PASSED              [ 26%]
project_a/tests/test_tax_engine.py::test_standard_deduction_boundary PASSED [ 29%]
project_a/tests/test_tax_engine.py::test_section_87a_rebate_old_regime_threshold PASSED [ 31%]
project_a/tests/test_tax_engine.py::test_section_87a_marginal_relief_new_regime_fy24_25 PASSED [ 34%]
project_a/tests/test_tax_engine.py::test_finance_act_2025_new_regime_12l_zero_tax PASSED [ 36%]
project_a/tests/test_tax_engine.py::test_surcharge_marginal_relief_at_51_lakh PASSED [ 39%]
project_a/tests/test_tax_engine.py::test_hra_metro_vs_non_metro PASSED   [ 41%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[1] PASSED [ 43%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[2] PASSED [ 46%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[3] PASSED [ 48%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[4] PASSED [ 51%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[5] PASSED [ 53%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[6] PASSED [ 56%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[7] PASSED [ 58%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[8] PASSED [ 60%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[9] PASSED [ 63%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[10] PASSED [ 65%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[11] PASSED [ 68%]
project_b/tests/test_corruption_and_detectors.py::test_all_12_corruptions_run[12] PASSED [ 70%]
project_b/tests/test_corruption_and_detectors.py::test_corruption_reproducibility PASSED [ 73%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_schema PASSED [ 75%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_type_corruption PASSED [ 78%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_date_format_switch PASSED [ 80%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_lat_lon_swap PASSED [ 82%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_exact_duplicates PASSED [ 85%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_closed_before_created PASSED [ 87%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_borough_zip_mismatch PASSED [ 90%]
project_b/tests/test_corruption_and_detectors.py::test_rule_detector_pii PASSED [ 92%]
project_b/tests/test_corruption_and_detectors.py::test_statistical_null_spike_zscore PASSED [ 95%]
project_b/tests/test_corruption_and_detectors.py::test_statistical_near_duplicates_jaccard PASSED [ 97%]
project_b/tests/test_corruption_and_detectors.py::test_hybrid_pipeline_execution PASSED [100%]

============================= 41 passed in 5.31s ==============================
```

---

## 4. List of All Modified Files

1. [`.gitignore`](file:///d:/Project/fire-ai-assignment/.gitignore): Added `fireai/`, virtual env paths, temporary raw caches, and build artifacts.
2. [`project_b/data/fetch_nyc_311.py`](file:///d:/Project/fire-ai-assignment/project_b/data/fetch_nyc_311.py): Implemented paginated Socrata API query for 2023, date verification, separate synthetic generator, and backward-compatible aliases.
3. [`project_b/profiling/profiler.py`](file:///d:/Project/fire-ai-assignment/project_b/profiling/profiler.py): Upgraded to profile real and synthetic data separately (`profile_all_datasets`).
4. [`project_b/benchmarks/dq_benchmark.py`](file:///d:/Project/fire-ai-assignment/project_b/benchmarks/dq_benchmark.py): Added per-corruption hybrid evaluation, detector applicability rationales, and clean table output.
5. [`project_a/main.py`](file:///d:/Project/fire-ai-assignment/project_a/main.py): Added standalone path resolution for direct CLI execution.
6. [`project_b/main.py`](file:///d:/Project/fire-ai-assignment/project_b/main.py): Added standalone path resolution for direct CLI execution.
7. [`run_all.py`](file:///d:/Project/fire-ai-assignment/run_all.py): Enhanced verification step 10 to validate all JSON artifacts and Markdown deliverables with non-zero exit codes.
8. [`RESULTS_A.md`](file:///d:/Project/fire-ai-assignment/RESULTS_A.md): Corrected table to mark unconfigured query-time LLM as `NOT RUN`, aligned numbers with JSON benchmark output.
9. [`RESULTS_B.md`](file:///d:/Project/fire-ai-assignment/RESULTS_B.md): Rebuilt table around the exact 12 required corruptions, marked LLM as `NOT RUN`, aligned numbers with JSON benchmark output.
10. [`DECISION_MATRIX.md`](file:///d:/Project/fire-ai-assignment/DECISION_MATRIX.md): Synchronized measured metrics and marked theoretical estimates.
11. [`AI_USAGE.md`](file:///d:/Project/fire-ai-assignment/AI_USAGE.md): Removed unverified claims; strictly separated observations from theoretical failure modes.
12. [`README.md`](file:///d:/Project/fire-ai-assignment/README.md): Synchronized benchmark matrices, provenance, and 12 corruptions list.
13. [`QA_REPORT.md`](file:///d:/Project/fire-ai-assignment/QA_REPORT.md): This QA audit deliverable.

---

## 5. Remaining Limitations & Operational Recommendations

1. **Google Gemini Free Tier Rate Limits (TPM / RPM)**:
   When running live Gemini queries (if an API key is provided), the Google AI free tier limits queries to 15 RPM. The benchmark harness includes adaptive throttling (`time.sleep(1.0)` and batching) to stay within free-tier quotas. When unconfigured, the system gracefully records metrics as `NOT RUN`.
2. **NYC Open Data Socrata Rate Limits (HTTP 429 & Query Timeouts)**:
   Unauthenticated queries to Socrata without an App Token are subject to occasional throttling and timeouts when performing global unindexed sorts over 35M+ records. The ingestion module incorporates seasonal window queries without global order, exponential backoff, and polite sleep intervals.
3. **Statistical Outlier Calibration & Municipal Field Noise**:
   Uncurated real-world municipal resolution notes naturally contain inspector phone numbers, contractor names, and unit abbreviations. In production, regex PII detection should be augmented with an approved departmental entity dictionary or dedicated NER model to suppress non-sensitive municipal operational contacts.
4. **Offline Evaluation vs. Streaming Production**:
   Offline benchmarks evaluate micro-batches of 500 rows. In the 50M rows/day production blueprint, Tier 1 is executed on continuous Kafka streams using Polars/Rust workers, and Tier 2 runs on rolling 5-minute sliding windows via PySpark/Ray.

---

## 6. Exact Reproduction Commands for Submission

```bash
# 1. Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# 2. Run complete end-to-end experiment reproduction (all 10 stages)
python run_all.py

# 3. Run automated pytest test suites
pytest -v

# 4. Run individual project test suites
pytest project_a/tests -v
pytest project_b/tests -v

# 5. Launch interactive Streamlit workbench
streamlit run dashboard/app.py
```

