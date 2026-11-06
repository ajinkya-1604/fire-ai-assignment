"""
Interactive Streamlit Multi-Page Dashboard for Rules vs LLMs Take-Home Assignment.
Sections:
- Section A: Indian Income Tax Engine (Old vs New Regime, Statutory Citations, 3-Way Engine Comparison)
- Section B: NYC 311 Data Quality Engine (Data Profiler, 12-Type Corruption Workbench, Confusion Matrices)
- Section C: Benchmark Explorer & Decision Matrix (Interactive Comparative Visualizations)
"""

from decimal import Decimal
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Setup pathing
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_a.calculators.compiled_engine import CompiledTaxEngine
from project_a.calculators.hand_coded_engine import calculate_tax
from project_a.parsers.tax_input_parser import TaxInputParser
from project_a.rules.base_rules import TaxInput
from project_b.corruption.injector import CORRUPTION_NAMES, CorruptionInjector
from project_b.data.fetch_nyc_311 import get_nyc_311_data
from project_b.detectors.rules.rule_detectors import RulesDetector
from project_b.detectors.statistical.statistical_detectors import StatisticalDetector
from project_b.pipeline.hybrid_pipeline import HybridDataQualityPipeline
from project_b.profiling.profiler import DataProfiler
from shared.config import REPORTS_DIR
from shared.metrics import format_currency_inr

st.set_page_config(
    page_title="Rules vs LLMs: Indian Tax & Data Quality Engines",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚖️ Rules vs LLMs: System Architecture & Benchmark Workbench")
st.caption("Fire AI Engineering Take-Home Assignment | Built with Python 3.12, Streamlit & Decimal Precision")

# Sidebar Navigation
sidebar_nav = st.sidebar.radio(
    "Select System Section",
    [
        "🏛️ Section A: Income Tax Calculator",
        "🔍 Section B: Data Quality Engine",
        "📊 Section C: Benchmark & Decision Matrix",
    ],
)

# =============================================================================
# SECTION A: INDIAN INCOME TAX ENGINE
# =============================================================================
if "Section A" in sidebar_nav:
    st.header("Section A: Indian Salaried Income Tax Engine")
    st.markdown("""
    Compare **Hand-Coded Deterministic Rules**, **Query-Time LLM**, and **LLM-Compiled Rules**
    across **FY 2024-25** and **FY 2025-26 (Finance Act 2025)** under both **Old** and **New** Tax Regimes.
    All financial computations strictly utilize `Decimal` arithmetic.
    """)

    tax_tab1, tax_tab2 = st.tabs(["🧮 Interactive Calculator", "💬 Plain-Language Parser (English & Hinglish)"])

    with tax_tab1:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Taxpayer Financial Profile")
            fy_select = st.selectbox("Financial Year", ["2024-25", "2025-26"], index=0)
            gross_salary = st.number_input("Annual Gross Salary (₹)", min_value=0.0, value=1200000.0, step=50000.0)
            basic_salary = st.number_input("Annual Basic + DA (₹, 0 for 50% default)", min_value=0.0, value=0.0, step=50000.0)
            rent_paid = st.number_input("Annual Rent Paid (₹)", min_value=0.0, value=240000.0, step=10000.0)
            is_metro = st.checkbox("Rented Accommodation in Metro City (Delhi, Mumbai, Kolkata, Chennai)", value=False)

            with st.expander("Chapter VI-A Deductions (Old Regime)", expanded=True):
                sec_80c = st.number_input("Section 80C - PF, PPF, ELSS, Life Insurance (₹, max 1.5L)", min_value=0.0, value=150000.0, step=10000.0)
                sec_80ccd = st.number_input("Section 80CCD(1B) - NPS Contribution (₹, max 50k)", min_value=0.0, value=50000.0, step=5000.0)
                sec_80d_self = st.number_input("Section 80D - Self/Family Health Insurance (₹)", min_value=0.0, value=25000.0, step=5000.0)
                is_senior_self = st.checkbox("Self is Senior Citizen (>= 60 years)", value=False)
                sec_80d_parents = st.number_input("Section 80D - Parents Health Insurance (₹)", min_value=0.0, value=30000.0, step=5000.0)
                is_senior_parents = st.checkbox("Parents are Senior Citizens (>= 60 years)", value=True)
                home_loan_24b = st.number_input("Section 24(b) - Home Loan Interest for Self-Occupied House (₹, max 2L)", min_value=0.0, value=0.0, step=10000.0)

            # Build TaxInput
            inp = TaxInput(
                gross_salary=Decimal(str(gross_salary)),
                basic_salary=Decimal(str(basic_salary)) if basic_salary > 0 else None,
                hra_received=Decimal(str(rent_paid)),
                rent_paid=Decimal(str(rent_paid)),
                is_metro=is_metro,
                section_80c=Decimal(str(sec_80c)),
                section_80ccd_1b=Decimal(str(sec_80ccd)),
                section_80d_self=Decimal(str(sec_80d_self)),
                is_senior_citizen_self=is_senior_self,
                section_80d_parents=Decimal(str(sec_80d_parents)),
                is_senior_citizen_parents=is_senior_parents,
                home_loan_interest_24b=Decimal(str(home_loan_24b)),
                financial_year=fy_select,
            )

        with col2:
            st.subheader("Regime Comparison & Breakdown")
            old_res = calculate_tax(inp, "OLD")
            new_res = calculate_tax(inp, "NEW")

            diff = old_res.total_tax - new_res.total_tax
            if diff > Decimal("0"):
                st.success(f"💡 **Recommendation: NEW REGIME is optimal!** You save **{format_currency_inr(diff)}**.")
            elif diff < Decimal("0"):
                st.success(f"💡 **Recommendation: OLD REGIME is optimal!** You save **{format_currency_inr(abs(diff))}**.")
            else:
                st.info("💡 **Both regimes yield identical tax.**")

            # Comparison Summary Cards
            c1, c2 = st.columns(2)
            c1.metric("Old Regime Tax", format_currency_inr(old_res.total_tax), delta=f"-{format_currency_inr(diff)}" if diff > 0 else None)
            c2.metric("New Regime Tax", format_currency_inr(new_res.total_tax), delta=f"-{format_currency_inr(abs(diff))}" if diff < 0 else None)

            # Breakdown Table
            breakdown_df = pd.DataFrame([
                {"Component": "Gross Salary", "Old Regime": format_currency_inr(old_res.gross_salary), "New Regime": format_currency_inr(new_res.gross_salary)},
                {"Component": "Standard Deduction", "Old Regime": format_currency_inr(old_res.standard_deduction), "New Regime": format_currency_inr(new_res.standard_deduction)},
                {"Component": "HRA Exemption", "Old Regime": format_currency_inr(old_res.total_exemptions), "New Regime": format_currency_inr(new_res.total_exemptions)},
                {"Component": "Chapter VI-A Deductions", "Old Regime": format_currency_inr(sum(old_res.chapter_via_deductions.values(), Decimal('0'))), "New Regime": "₹0.00 (Ineligible)"},
                {"Component": "Net Taxable Income", "Old Regime": format_currency_inr(old_res.taxable_income), "New Regime": format_currency_inr(new_res.taxable_income)},
                {"Component": "Slab Tax", "Old Regime": format_currency_inr(old_res.slab_tax), "New Regime": format_currency_inr(new_res.slab_tax)},
                {"Component": "Section 87A Rebate", "Old Regime": format_currency_inr(old_res.rebate_87a), "New Regime": format_currency_inr(new_res.rebate_87a)},
                {"Component": "Marginal Relief", "Old Regime": format_currency_inr(old_res.marginal_relief), "New Regime": format_currency_inr(new_res.marginal_relief)},
                {"Component": "Surcharge", "Old Regime": format_currency_inr(old_res.surcharge), "New Regime": format_currency_inr(new_res.surcharge)},
                {"Component": "4% Health & Education Cess", "Old Regime": format_currency_inr(old_res.cess), "New Regime": format_currency_inr(new_res.cess)},
                {"Component": "TOTAL TAX PAYABLE", "Old Regime": format_currency_inr(old_res.total_tax), "New Regime": format_currency_inr(new_res.total_tax)},
            ])
            st.dataframe(breakdown_df, hide_index=True, use_container_width=True)

            with st.expander("📜 Statutory Legal Clauses & Audit Trail"):
                st.write("**New Regime Statutory Citations:**")
                for comp, clause in new_res.source_clauses.items():
                    st.write(f"- `{comp}`: {clause}")
                st.write("**Old Regime Statutory Citations:**")
                for comp, clause in old_res.source_clauses.items():
                    st.write(f"- `{comp}`: {clause}")

    with tax_tab2:
        st.subheader("Natural Language Tax Input Parser")
        sample_prompts = [
            "My annual salary is 12 lakh, I pay 20,000 rent monthly, and I invested 1.5 lakh in 80C.",
            "Mera annual package 15 lakh hai, main Mumbai me 30,000 monthly kiraya deta hu aur 1.5L 80C me invest kiya hai.",
            "My CTC is 18 LPA, paying 35k monthly rent in Bangalore, invested 150000 in PPF under 80C.",
            "I pay 25,000 monthly rent in Kolkata and invested 1.5L in 80C. Please calculate my tax.",
            "My annual salary is 10 lakh per annum, but I earn 2 lakh per month. 80C is 1.5 lakh.",
        ]
        selected_sample = st.selectbox("Choose a pre-built sample or type your own below:", ["-- Custom Input --"] + sample_prompts)
        default_val = selected_sample if selected_sample != "-- Custom Input --" else sample_prompts[0]
        user_query = st.text_area("Tax Declaration (English or Hinglish)", value=default_val, height=100)

        if st.button("Parse & Compute Tax"):
            parser = TaxInputParser()
            parse_res = parser.parse(user_query)

            if parse_res.is_valid:
                st.success("✅ Query successfully parsed into structured TaxInput!")
                p_inp = parse_res.tax_input
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Gross Salary:** {format_currency_inr(p_inp.gross_salary)}")
                    st.write(f"**Rent Paid:** {format_currency_inr(p_inp.rent_paid)} (Metro: {p_inp.is_metro})")
                    st.write(f"**Section 80C:** {format_currency_inr(p_inp.section_80c)}")
                with col_b:
                    st.write(f"**Financial Year:** {p_inp.financial_year}")
                    p_old = calculate_tax(p_inp, "OLD")
                    p_new = calculate_tax(p_inp, "NEW")
                    st.metric("Old Regime Tax", format_currency_inr(p_old.total_tax))
                    st.metric("New Regime Tax", format_currency_inr(p_new.total_tax))
            else:
                st.error("⚠️ Clarification Required:")
                st.warning(parse_res.clarification_question)
                if parse_res.contradictions:
                    st.write("**Detected Contradictions:**")
                    for c in parse_res.contradictions:
                        st.write(f"- {c}")

# =============================================================================
# SECTION B: NYC 311 DATA QUALITY ENGINE
# =============================================================================
elif "Section B" in sidebar_nav:
    st.header("Section B: NYC 311 Data Quality & Corruption Workbench")
    st.markdown("""
    Explore real-time data profiling, inject any of the **12 required corruption types**,
    and evaluate **Rules**, **Statistical/ML**, and **LLM Reviewer** detectors on live batches.
    """)

    dq_tab1, dq_tab2, dq_tab3 = st.tabs(["📊 Data Profiler", "🧪 12-Corruption Injector & Detectors", "⚡ Hybrid Pipeline"])

    with dq_tab1:
        st.subheader("NYC 311 Service Requests: Data Profiling")
        df_sample = get_nyc_311_data().iloc[:1000]

        if st.button("Run Data Profiling on NYC 311 Dataset"):
            profiler = DataProfiler(df_sample)
            report = profiler.profile_all()

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Profiled Rows", report["summary"]["total_rows"])
            col_m2.metric("Exact Duplicates", report["duplicates"]["exact_duplicate_rows"])
            col_m3.metric("Invalid Dates", report["date_anomalies"].get("closed_before_created_count", 0))
            col_m4.metric("Potential PII Leaks", report["pii_findings"]["total_pii_occurrences"])

            st.write("### Missing Values by Column (%)")
            missing_df = pd.DataFrame([
                {"Column": col, "Missing Count": d["missing_count"], "Missing %": d["missing_percent"]}
                for col, d in report["missing_values"].items()
            ])
            fig_missing = px.bar(missing_df, x="Column", y="Missing %", title="Null Rate Distribution Across Features")
            st.plotly_chart(fig_missing, use_container_width=True)

            st.write("### Borough Distribution")
            st.json(report["categorical_consistency"].get("borough_distribution", {}))

    with dq_tab2:
        st.subheader("Corruption Injector & Multi-Family Detector Evaluation")
        corruption_id = st.selectbox(
            "Select Corruption to Inject (1 to 12):",
            list(CORRUPTION_NAMES.keys()),
            format_func=lambda x: f"Type {x}: {CORRUPTION_NAMES[x]}",
        )
        rate = st.slider("Corruption Injection Rate", min_value=0.01, max_value=0.30, value=0.10, step=0.01)

        raw_df = get_nyc_311_data().iloc[:500].copy()
        injector = CorruptionInjector(seed=42)
        corrupted_res = injector.inject(corruption_id, raw_df, rate=rate)

        st.info(f"Injected {len(corrupted_res.corrupted_indices)} corrupted records out of {len(corrupted_res.df)} rows ({rate*100:.1f}% rate).")

        # Run Detectors
        rules_det = RulesDetector()
        stats_det = StatisticalDetector(random_state=42)

        r_labels, r_exps, r_lat = rules_det.run_detector(corruption_id, corrupted_res.df)
        s_labels, s_exps, s_lat = stats_det.run_detector(corruption_id, corrupted_res.df)

        from shared.metrics import calculate_classification_metrics
        r_m = calculate_classification_metrics(list(corrupted_res.labels), list(r_labels))
        s_m = calculate_classification_metrics(list(corrupted_res.labels), list(s_labels))

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.write("#### 🛡️ Family 1: Rules Detector")
            st.metric("Rules F1 Score", r_m["f1"])
            st.write(f"- **Precision:** {r_m['precision']} | **Recall:** {r_m['recall']}")
            st.write(f"- **Detection Rate:** {r_m['detection_rate']} | **False Alarm Rate:** {r_m['false_alarm_rate']}")
            st.write(f"- **Latency:** {r_lat:.2f} ms")

        with col_d2:
            st.write("#### 📈 Family 2: Statistical / ML Detector")
            st.metric("Statistical F1 Score", s_m["f1"])
            st.write(f"- **Precision:** {s_m['precision']} | **Recall:** {s_m['recall']}")
            st.write(f"- **Detection Rate:** {s_m['detection_rate']} | **False Alarm Rate:** {s_m['false_alarm_rate']}")
            st.write(f"- **Latency:** {s_lat:.2f} ms")

        st.write("#### Inspect Detected Anomaly Examples")
        flagged_df = corrupted_res.df.copy()
        flagged_df["Ground_Truth"] = corrupted_res.labels
        flagged_df["Rules_Flagged"] = r_labels
        flagged_df["Rules_Explanation"] = r_exps

        # Dynamically select columns present in dataframe to safely handle dropped/renamed columns
        candidate_cols = [
            "unique_key", "agency", "dept_code", "complaint_type", "descriptor",
            "incident_zip", "status", "created_date", "closed_date"
        ]
        present_cols = [c for c in candidate_cols if c in flagged_df.columns]
        display_cols = list(dict.fromkeys(present_cols + ["Ground_Truth", "Rules_Flagged", "Rules_Explanation"]))

        flagged_subset = flagged_df[flagged_df["Ground_Truth"] == 1]
        if flagged_subset.empty:
            flagged_subset = flagged_df
        st.dataframe(flagged_subset[display_cols].head(10), hide_index=True)

    with dq_tab3:
        st.subheader("Tiered Hybrid Pipeline Performance")
        st.markdown("""
        The Hybrid Architecture executes:
        1. **Tier 1 (Rules)** on 100% of rows (O(1), $0 cost).
        2. **Tier 2 (Statistical)** on batch distributions & clustering.
        3. **Tier 3 (LLM Reviewer)** selectively on ambiguous candidates.
        """)

        pipe_df = get_nyc_311_data().iloc[:500].copy()
        c_inj = injector.inject_closed_before_created(pipe_df, rate=0.08)
        pipe = HybridDataQualityPipeline()

        h_res = pipe.run_hybrid_pipeline(c_inj.df, y_true=c_inj.labels)
        r_res = pipe.run_rules_only(c_inj.df, y_true=c_inj.labels)
        s_res = pipe.run_statistical_only(c_inj.df, y_true=c_inj.labels)

        comp_df = pd.DataFrame([
            {"Architecture": "Rules-Only", "F1 Score": r_res.metrics["f1"], "Precision": r_res.metrics["precision"], "Recall": r_res.metrics["recall"], "Throughput (rows/sec)": r_res.throughput_rows_per_sec, "Cost / 1M ($)": 0.0},
            {"Architecture": "Statistical-Only", "F1 Score": s_res.metrics["f1"], "Precision": s_res.metrics["precision"], "Recall": s_res.metrics["recall"], "Throughput (rows/sec)": s_res.throughput_rows_per_sec, "Cost / 1M ($)": 0.0},
            {"Architecture": "Hybrid Multi-Tier", "F1 Score": h_res.metrics["f1"], "Precision": h_res.metrics["precision"], "Recall": h_res.metrics["recall"], "Throughput (rows/sec)": h_res.throughput_rows_per_sec, "Cost / 1M ($)": round(h_res.cost_usd * 1_000_000 / len(pipe_df), 4)},
        ])
        st.dataframe(comp_df, hide_index=True, use_container_width=True)

# =============================================================================
# SECTION C: BENCHMARKS & DECISION MATRIX
# =============================================================================
elif "Section C" in sidebar_nav:
    st.header("Section C: Comprehensive Benchmarks & Decision Matrix")

    st.subheader("Project A: Indian Tax Engine Benchmark Comparison")
    tax_rep_path = REPORTS_DIR / "project_a_benchmark_results.json"
    if tax_rep_path.exists():
        with open(tax_rep_path, "r", encoding="utf-8") as f:
            tax_bench = json.load(f)

        impls = tax_bench["implementations"]
        tax_table = []
        for key, d in impls.items():
            tax_table.append({
                "Engine": d["name"],
                "Rupee Exact Accuracy (%)": d.get("rupee_exact_accuracy_percent"),
                "10-Run Determinism (%)": d.get("determinism_10_runs_percent"),
                "Latency Mean (ms)": d.get("latency_mean_ms"),
                "Cost / 1k Req ($)": d.get("cost_per_1000_requests_usd"),
                "Statutory Traceability (%)": d.get("statutory_traceability_percent"),
            })
        st.dataframe(pd.DataFrame(tax_table), hide_index=True, use_container_width=True)
    else:
        st.info("Run `python project_a/main.py --benchmark` to generate Project A benchmark results.")

    st.subheader("Project B: Data Quality Engine Benchmark Comparison")
    dq_rep_path = REPORTS_DIR / "project_b_benchmark_results.json"
    if dq_rep_path.exists():
        with open(dq_rep_path, "r", encoding="utf-8") as f:
            dq_bench = json.load(f)

        pipe_comp = dq_bench["pipeline_comparison"]
        dq_table = []
        for key, p in pipe_comp.items():
            m = p.get("metrics", {})
            dq_table.append({
                "Architecture": p["name"],
                "F1 Score": m.get("f1", "N/A"),
                "Precision": m.get("precision", "N/A"),
                "Recall": m.get("recall", "N/A"),
                "Throughput (rows/sec)": p.get("throughput_rows_per_sec"),
                "Cost / 1M Rows ($)": p.get("cost_per_million_rows_usd"),
            })
        st.dataframe(pd.DataFrame(dq_table), hide_index=True, use_container_width=True)

        # Plotly chart comparing F1 and Throughput
        chart_df = pd.DataFrame(dq_table)
        fig_pipe = px.bar(chart_df, x="Architecture", y="Throughput (rows/sec)", color="F1 Score", title="Throughput and F1 Score by Pipeline Architecture")
        st.plotly_chart(fig_pipe, use_container_width=True)
    else:
        st.info("Run `python project_b/main.py --benchmark` to generate Project B benchmark results.")

