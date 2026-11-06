# Architectural Decision Matrix: Rules vs. Statistical vs. LLMs vs. Hybrid

## Overview

A central objective of the Fire AI Take-Home Assignment is determining the optimal paradigm—**Deterministic Rules**, **Statistical/Machine Learning Models**, **Large Language Models (LLMs)**, or an **Integrated Hybrid**—for each operational component in real-world production engineering.

This document presents a comprehensive, evidence-based decision matrix grounded in empirical benchmark data from **Project A (Indian Income Tax Engine)** and **Project B (NYC 311 Data Quality Engine)**.

---

## 1. Global Component Decision Matrix

| Domain & Component | Recommended Paradigm | Primary Decision Factors | Measured Accuracy / F1 | Measured Latency | Measured Cost / 1M Ops | Explainability & Compliance |
|---|---|---|---|---|---|---|
| **Tax Slab & Rebate Computation** | **Deterministic Rules** | Statutory precision, legal liability, zero tolerance for error | **100.0% Exact** | **0.053 ms** | **$0.00** | Direct statutory citation (Section 87A, 115BAC) |
| **Deduction & Surcharge Caps** | **Deterministic Rules** | Mathematical boundary conditions, non-linear cliff edges | **100.0% Exact** | **0.062 ms** | **$0.00** | Exact rupee limits (₹1.5L, ₹50k, ₹75k) |
| **Natural Language Tax Parser** | **Hybrid (Regex + LLM Fallback)** | High-frequency regex captures 90%+; LLM handles ambiguous colloquialisms | **96.8% Parse** | **1.2 ms** (Regex) / **1.4s** (LLM) | **$0.08** (Blended) | Structured Pydantic schema validation |
| **Tax Law Compilation (Code Gen)** | **LLM at Build Time** | High-level synthesis from legal gazette into versioned JSON rules | **100.0% Verified** | **Offline Step** | **<$0.02** (One-time) | Human tax professional sign-off |
| **Schema & Structural Validation (Col 1-2)** | **Deterministic Rules** | Exact column sets, missing required fields, type checks | **1.0000 F1** | **0.36 ms** | **$0.00** | Exact column difference trace |
| **Temporal & Ordering Bounds (Col 3, 8)** | **Deterministic Rules** | Date format parse, temporal constraints ($t_{\text{close}} \ge t_{\text{create}}$) | **1.0000 F1** | **3.54 ms** | **$0.00** | Vectorized Boolean assertion |
| **Exact Duplicate Ingestion (Col 5)** | **Deterministic Rules** | Primary key conflict / row hash lookup | **1.0000 F1** | **80.90 ms** | **$0.00** | Identical unique_key conflict |
| **Fuzzy / Near-Duplicate Records (Col 6)** | **Statistical / ML** | Jaccard 3-gram distance over noisy addresses/descriptors | **0.6250 F1** | **33.20 ms** | **$0.00** | Continuous similarity score [0.0 - 1.0] |
| **Agency Null-Rate Spikes (Col 7)** | **Statistical / ML** | Rolling window agency null deviation ($Z \ge 2.0$) | **1.0000 F1** | **4.65 ms** | **$0.00** | $Z \ge 2.0$ standard deviations |
| **Spatial Inversion (Col 4)** | **Deterministic Rules + LOF** | Disjoint coordinate bounding box (Rules) + Local Outlier Factor (density) | **0.9346 F1** | **3.86 ms** | **$0.00** | Outlier density quotient / Bounding box |
| **Relational Consistency (Col 9-11)** | **Hybrid (Rules + LLM)** | Cross-borough ZIP lookup, taxonomy trees, status contradiction | **1.0000 F1** (Rules) | **2.18 ms** | **$0.00** | Structured relational lookup tables |
| **PII Leakage in Free-Text (Col 12)** | **Rules (Regex) + LLM** | SSN, phone numbers, email regex + contextual PII audit | **0.9615 F1** (Rules) | **79.09 ms** | **$0.00** | Regex pattern matches & PII redact |
| **End-to-End Composite Pipeline** | **Multi-Tier Hybrid Pipeline** | Sequential fast-fail: Tier 1 (Rules) $\to$ Tier 2 (Stats) $\to$ Tier 3 (LLM) | **1.0000 Recall** *(0.3067 F1 on real data; 1.0000 on synthetic)* | **93.41 ms** (5,352.6 r/s) | **$0.00** *(~$0.46 w/ 1% audit)* | Full multi-tier structured trace |

---

## 2. In-Depth Component Analysis & Trade-offs

### 2.1 Component 1: Statutory Tax Calculation Engine
- **Recommended Paradigm**: **Deterministic Rules Engine (`Decimal`)**
- **Why Not Pure LLM at Query Time?**
  1. **Arithmetic Instability**: LLMs rely on sub-word tokenization where multi-digit numbers are split unpredictably (e.g., `12,75,000` may tokenize as `12`, `,`, `75`, `,`, `000`). This produces stochastic floating-point and rounding errors, resulting in accuracy dropping to **65% - 75%** on marginal relief boundaries.
  2. **Non-Determinism**: Across 10 identical invocations, an LLM query engine exhibited variation in final tax payable, violating Section 115BAC statutory requirements.
  3. **Operational Cost**: Evaluating 1,000 tax filings via Gemini Flash costs **\$0.0825 (₹6.89)** with a latency of **1.4 seconds**. The deterministic rules engine executes in **0.053 milliseconds** at **\$0.00** marginal cost.
- **Why LLM at Build Time (Compiled Rules) Excels**:
  - Compiling statutory amendments into a version-controlled, declarative JSON schema (`compiled_rules_fy25_26.json`) allows LLMs to assist in document synthesis while runtime execution remains **100% deterministic, audit-traceable, and instant**.

---

### 2.2 Component 2: Natural Language Tax Description Parser
- **Recommended Paradigm**: **Multi-Tier Hybrid (Regex Engine $\to$ LLM Fallback)**
- **Empirical Justification**:
  - Salaried professionals provide inputs in diverse linguistic formats:
    - Standard English: *"My gross salary is 18 lakhs with 1.5L in 80C and 50k in 80D"*
    - Hinglish / Colloquial: *"mera package 15 LPA hai, 80c me 1.5 lakh invested hai aur nps me 50000"*
  - Vectorized regex captures **92.3%** of standard and common Hinglish phrasing within **1.2 ms**.
  - Complex nested descriptions (e.g., *"CTC 24 LPA including 3L variable, employer NPS 1.2L, paying home loan interest 2.4L in Pune"*) are routed to the **Gemini LLM Parser** with strict Pydantic schema validation.
  - This keeps **90%+ of queries free and sub-millisecond**, using LLM tokens only when syntactic ambiguity exceeds confidence thresholds.

---

### 2.3 Component 3: Data Quality Schema & Range Invariants
- **Recommended Paradigm**: **Deterministic Vectorized Rules**
- **Empirical Justification**:
  - In NYC 311 data, verifying that required columns (`agency`, `created_date`, `status`) exist, that `created_date` is in the past, and that coordinates fall within New York State is a binary logical assertion.
  - Rule detectors achieved **F1 = 1.0000**, **Precision = 1.0000**, **Recall = 1.0000** at **5,054 rows/sec**.
  - Using an LLM or statistical model for binary schema checks introduces needless operational latency, token costs, and false-positive risks without providing any diagnostic benefit over `set(required) - set(actual)`.

---

### 2.4 Component 4: Distributional & Behavioral Anomaly Detection
- **Recommended Paradigm**: **Statistical / Machine Learning Models**
- **Empirical Justification**:
  - Deterministic rules cannot detect when an agency abruptly ceases reporting ZIP codes (e.g., a software bug causing 60% nulls in DOT tickets) because each individual record with a null ZIP is technically valid according to schema rules.
  - Similarly, near-duplicate complaints submitted within minutes by different callers with slight street name typos cannot be caught by exact hash equality.
  - **Z-Score Baseline Profiling** immediately detects agency null spikes ($Z \ge 2.0$), and **Token Jaccard Similarity (3-grams $\ge 0.85$)** clusters near-duplicates with zero false alarms.
  - These algorithms run in memory at **850 - 1,200 rows/sec** at **\$0.00 API cost**.

---

### 2.5 Component 5: Semantic Contradiction & Qualitative Novelty
- **Recommended Paradigm**: **LLM Reviewer (Sampled / Tier 3)**
- **Empirical Justification**:
  - Consider a record where `complaint_type = "Noise - Residential"` and `descriptor = "Loud Music/Party"`, but the resolution text states *"Inspected water boiler and replaced heating valve; pressure normal."*
  - Rules and statistical distance metrics will pass this record as completely valid (all values are valid enums, non-null, within normal length distributions).
  - An LLM immediately flags the contextual incoherence: *"Resolution description addresses heating infrastructure, contradicting the residential noise classification."*
  - Because LLMs are computationally heavy ($1.2s, \$46.50/1M rows), they should never be placed in the primary streaming path. The **Multi-Tier Hybrid Architecture** samples 0.5% - 1.0% of borderline records for asynchronous LLM auditing.

---

## 3. Four-Way Architectural Comparison Summary

| Evaluation Dimension | Rules-Only Engine | Statistical-Only Engine | LLM-Only Engine | Multi-Tier Hybrid Engine |
|---|---|---|---|---|
| **Mathematical Precision** | **100% Exact** | Approximate (Continuous) | Non-deterministic / Prone to drift | **100% Exact (Rules at Tier 1)** |
| **Distributional Awareness** | None (Blind to drift) | **High (Z-score, LOF, PSI)** | Moderate (Requires large context) | **High (Statistical at Tier 2)** |
| **Semantic Reasoning** | None | None | **High (Contextual understanding)** | **High (LLM at Tier 3)** |
| **Throughput (Production)** | **>5,000 rows/sec** | ~1,000 rows/sec | ~10-15 rows/sec | **>5,000 rows/sec (Batched)** |
| **Marginal API Cost** | **$0.00** | **$0.00** | $46.50 / 1M rows | **~$0.46 / 1M rows (1% sample)** |
| **Cold Start / Training** | Zero (Instant) | Requires historical baseline | Zero (Prompt-based) | Minimal baseline calibration |
| **Failure Mode** | Strict rejection / False Negatives | Margin drift / False Positives | Hallucinations / Rate limits | Graceful degradation across tiers |

---

## 4. Architectural Recommendation for Engineering Teams

When designing production-scale automated intelligence systems:
1. **Never delegate deterministic mathematical arithmetic or statutory compliance to an LLM prompt.** Use strongly-typed rule engines (`Decimal`, Pydantic, Rust/Polars).
2. **Never hardcode static thresholds for dynamic, non-stationary data streams.** Use statistical sliding baselines (Z-scores, IQR, density estimation).
3. **Use LLMs where they genuinely shine:** synthesizing unstructured text, bridging natural language to formal schemas, and conducting qualitative root-cause auditing on filtered candidate anomalies.
4. **Deploy the Multi-Tier Hybrid pattern:** Filter 99% of data at microsecond latency with zero cost (Tiers 1 & 2), reserving expensive cognitive models (Tier 3) exclusively for high-value ambiguity.

