"""
Project A Main Entrypoint: Indian Income Tax Engine CLI & Benchmark Runner.
Usage:
    python project_a/main.py --calculate --salary 1200000 --rent 20000 --c 150000
    python project_a/main.py --parse "My annual salary is 15 lakh, rent 25000 monthly"
    python project_a/main.py --benchmark
"""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_a.benchmarks.tax_benchmark import print_benchmark_table, run_benchmarks
from project_a.calculators.compiled_engine import CompiledTaxEngine
from project_a.calculators.hand_coded_engine import calculate_tax
from project_a.parsers.tax_input_parser import TaxInputParser
from project_a.rules.base_rules import TaxInput
from shared.logging_config import setup_logging
from shared.metrics import format_currency_inr

logger = setup_logging()


def main():
    parser = argparse.ArgumentParser(description="Indian Income Tax Engine (Project A)")
    parser.add_argument("--benchmark", action="store_true", help="Run full Project A benchmarks")
    parser.add_argument("--parse", type=str, help="Parse a plain-language English or Hinglish query")
    parser.add_argument("--calculate", action="store_true", help="Calculate tax for given parameters")
    parser.add_argument("--salary", type=float, default=1200000, help="Annual Gross Salary in INR")
    parser.add_argument("--rent", type=float, default=0, help="Annual Rent paid in INR")
    parser.add_argument("--c", type=float, default=0, help="Section 80C investment in INR")
    parser.add_argument("--nps", type=float, default=0, help="Section 80CCD(1B) NPS in INR")
    parser.add_argument("--d-self", type=float, default=0, help="Section 80D self in INR")
    parser.add_argument("--d-parents", type=float, default=0, help="Section 80D parents in INR")
    parser.add_argument("--senior-parents", action="store_true", help="Are parents senior citizens")
    parser.add_argument("--home-loan", type=float, default=0, help="Section 24(b) home loan interest in INR")
    parser.add_argument("--metro", action="store_true", help="Is rent accommodation in metro city")
    parser.add_argument("--fy", type=str, default="2024-25", choices=["2024-25", "2025-26"], help="Financial Year")

    args = parser.parse_args()

    if args.benchmark:
        print("\n>>> Running Project A Benchmarks...")
        res = run_benchmarks()
        print_benchmark_table(res)
        return

    if args.parse:
        print(f"\n>>> Parsing query: '{args.parse}'")
        input_parser = TaxInputParser()
        parse_res = input_parser.parse(args.parse)

        if not parse_res.is_valid:
            print("\n[CLARIFICATION REQUIRED]")
            print(parse_res.clarification_question)
            if parse_res.contradictions:
                print("\nContradictions flagged:")
                for c in parse_res.contradictions:
                    print(f" - {c}")
            return

        print("\n[SUCCESSFULLY PARSED TAX INPUT]")
        inp = parse_res.tax_input
        print(f"Annual Gross Salary: {format_currency_inr(inp.gross_salary)}")
        print(f"Rent Paid:           {format_currency_inr(inp.rent_paid)} (Metro: {inp.is_metro})")
        print(f"Section 80C:         {format_currency_inr(inp.section_80c)}")
        print(f"Section 80CCD(1B):   {format_currency_inr(inp.section_80ccd_1b)}")
        print(f"Section 80D:         {format_currency_inr(inp.section_80d_self + inp.section_80d_parents)}")
        print(f"Home Loan 24(b):     {format_currency_inr(inp.home_loan_interest_24b)}")
        print(f"Financial Year:      {inp.financial_year}")

        # Compute under both regimes
        old_res = calculate_tax(inp, "OLD")
        new_res = calculate_tax(inp, "NEW")
        print("\n" + "=" * 50)
        print(f"OLD REGIME TAX: {format_currency_inr(old_res.total_tax)}")
        print(f"NEW REGIME TAX: {format_currency_inr(new_res.total_tax)}")
        diff = old_res.total_tax - new_res.total_tax
        if diff > 0:
            print(f"RECOMMENDATION: NEW REGIME saves you {format_currency_inr(diff)}")
        elif diff < 0:
            print(f"RECOMMENDATION: OLD REGIME saves you {format_currency_inr(abs(diff))}")
        else:
            print("RECOMMENDATION: Both regimes yield identical tax.")
        print("=" * 50)
        return

    # Default calculate
    inp = TaxInput(
        gross_salary=Decimal(str(args.salary)),
        rent_paid=Decimal(str(args.rent)),
        hra_received=Decimal(str(args.rent)),
        is_metro=args.metro,
        section_80c=Decimal(str(args.c)),
        section_80ccd_1b=Decimal(str(args.nps)),
        section_80d_self=Decimal(str(args.d_self)),
        section_80d_parents=Decimal(str(args.d_parents)),
        is_senior_citizen_parents=args.senior_parents,
        home_loan_interest_24b=Decimal(str(args.home_loan)),
        financial_year=args.fy,
    )

    old_res = calculate_tax(inp, "OLD")
    new_res = calculate_tax(inp, "NEW")

    print("\n" + "=" * 65)
    print(f"TAX CALCULATION BREAKDOWN - FY {args.fy}")
    print("=" * 65)
    print(f"{'Component':<30} | {'Old Regime':<15} | {'New Regime':<15}")
    print("-" * 65)
    print(f"{'Gross Salary':<30} | {format_currency_inr(inp.gross_salary):<15} | {format_currency_inr(inp.gross_salary):<15}")
    print(f"{'Standard Deduction':<30} | {format_currency_inr(old_res.standard_deduction):<15} | {format_currency_inr(new_res.standard_deduction):<15}")
    print(f"{'HRA Exemption':<30} | {format_currency_inr(old_res.total_exemptions):<15} | {format_currency_inr(new_res.total_exemptions):<15}")
    print(f"{'Chapter VI-A Deductions':<30} | {format_currency_inr(sum(old_res.chapter_via_deductions.values(), Decimal('0'))):<15} | {format_currency_inr(Decimal('0')):<15}")
    print(f"{'Taxable Income':<30} | {format_currency_inr(old_res.taxable_income):<15} | {format_currency_inr(new_res.taxable_income):<15}")
    print(f"{'Slab Tax':<30} | {format_currency_inr(old_res.slab_tax):<15} | {format_currency_inr(new_res.slab_tax):<15}")
    print(f"{'Section 87A Rebate':<30} | {format_currency_inr(old_res.rebate_87a):<15} | {format_currency_inr(new_res.rebate_87a):<15}")
    print(f"{'Marginal Relief':<30} | {format_currency_inr(old_res.marginal_relief):<15} | {format_currency_inr(new_res.marginal_relief):<15}")
    print(f"{'Surcharge':<30} | {format_currency_inr(old_res.surcharge):<15} | {format_currency_inr(new_res.surcharge):<15}")
    print(f"{'4% Health & Education Cess':<30} | {format_currency_inr(old_res.cess):<15} | {format_currency_inr(new_res.cess):<15}")
    print("-" * 65)
    print(f"{'TOTAL TAX PAYABLE':<30} | {format_currency_inr(old_res.total_tax):<15} | {format_currency_inr(new_res.total_tax):<15}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

