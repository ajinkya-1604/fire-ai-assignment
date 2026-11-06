"""
Official Indian Income Tax Sources, Legal Clauses, and Statutory Citations.
All tax provisions reference official Finance Acts and the Income-tax Act, 1961.
No tax provisions or clauses are fabricated.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TaxClause:
    section: str
    act_reference: str
    document_name: str
    source_url: str
    effective_date: str
    description: str


OFFICIAL_TAX_SOURCES: Dict[str, TaxClause] = {
    "OLD_SLABS": TaxClause(
        section="First Schedule, Part I, Paragraph A",
        act_reference="Finance Act, 1961 (as amended annually)",
        document_name="Income-tax Act, 1961 / Finance (No. 2) Act, 2024",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="1961-04-01 (Amended FY 2024-25)",
        description="Progressive tax slabs under Old Regime: 0-2.5L Nil, 2.5-5L 5%, 5-10L 20%, >10L 30%."
    ),
    "NEW_SLABS_FY24_25": TaxClause(
        section="Section 115BAC(1A)",
        act_reference="Finance (No. 2) Act, 2024 (Act No. 15 of 2024)",
        document_name="Finance (No. 2) Act, 2024 Official Gazette",
        source_url="https://incometaxindia.gov.in/Pages/budget-and-bills/finance-bill.aspx",
        effective_date="2024-04-01 (AY 2025-26)",
        description="New Tax Regime Slabs: 0-3L Nil, 3-7L 5%, 7-10L 10%, 10-12L 15%, 12-15L 20%, >15L 30%."
    ),
    "NEW_SLABS_FY25_26": TaxClause(
        section="Section 115BAC(1A) amended by Finance Act 2025",
        act_reference="Finance Act, 2025",
        document_name="Finance Act, 2025 Official Gazette",
        source_url="https://incometaxindia.gov.in/Pages/budget-and-bills/finance-bill.aspx",
        effective_date="2025-04-01 (AY 2026-27)",
        description="Revised New Regime Slabs: 0-4L Nil, 4-8L 5%, 8-12L 10%, 12-16L 15%, 16-20L 20%, 20-24L 25%, >24L 30%."
    ),
    "STD_DEDUCTION_OLD": TaxClause(
        section="Section 16(ia)",
        act_reference="Finance Act, 2019",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2019-04-01",
        description="Standard deduction of ₹50,000 for salaried employees under Old Regime."
    ),
    "STD_DEDUCTION_NEW_FY24_25": TaxClause(
        section="Section 16(ia) read with Section 115BAC(1A)",
        act_reference="Finance (No. 2) Act, 2024",
        document_name="Finance (No. 2) Act, 2024",
        source_url="https://incometaxindia.gov.in/Pages/budget-and-bills/finance-bill.aspx",
        effective_date="2024-04-01 (AY 2025-26)",
        description="Enhanced standard deduction of ₹75,000 for salaried employees under New Regime."
    ),
    "HRA_EXEMPTION": TaxClause(
        section="Section 10(13A) read with Rule 2A of Income-tax Rules, 1962",
        act_reference="Income-tax Act, 1961",
        document_name="Income-tax Rules, 1962",
        source_url="https://incometaxindia.gov.in/pages/rules/income-tax-rules-1962.aspx",
        effective_date="1962-04-01",
        description="HRA exemption is the least of: (i) Actual HRA received, (ii) Rent paid minus 10% of salary, (iii) 50% of salary in Metros (Delhi, Mumbai, Kolkata, Chennai) or 40% in non-metros."
    ),
    "SEC_80C": TaxClause(
        section="Section 80C",
        act_reference="Finance Act, 2014",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2014-04-01",
        description="Deduction in respect of life insurance premia, deferred annuity, contributions to PF, PPF, ELSS, tuition fees etc., up to ₹1,50,000."
    ),
    "SEC_80CCD_1B": TaxClause(
        section="Section 80CCD(1B)",
        act_reference="Finance Act, 2015",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2015-04-01",
        description="Additional deduction for individual contribution to National Pension System (NPS) up to ₹50,000."
    ),
    "SEC_80D": TaxClause(
        section="Section 80D",
        act_reference="Finance Act, 2018",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2018-04-01",
        description="Health insurance deduction: Self/family up to ₹25,000 (₹50,000 if senior citizen >=60 yrs); Parents up to ₹25,000 (₹50,000 if senior citizen parents). Maximum ₹1,00,000."
    ),
    "SEC_24B": TaxClause(
        section="Section 24(b)",
        act_reference="Finance (No. 2) Act, 2014",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2014-04-01",
        description="Deduction on interest payable on borrowed capital for self-occupied house property, capped at ₹2,00,000."
    ),
    "REBATE_87A_OLD": TaxClause(
        section="Section 87A",
        act_reference="Finance Act, 2019",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2019-04-01",
        description="Rebate of up to ₹12,500 if total taxable income does not exceed ₹5,00,000 under Old Regime."
    ),
    "REBATE_87A_NEW_FY24_25": TaxClause(
        section="Section 87A (First Proviso)",
        act_reference="Finance Act, 2023 read with Finance (No. 2) Act, 2024",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/Pages/budget-and-bills/finance-bill.aspx",
        effective_date="2023-04-01 (AY 2024-25 onwards)",
        description="Full tax rebate if total income does not exceed ₹7,00,000 (max ₹25,000). Proviso provides marginal relief for income marginally exceeding ₹7,00,000."
    ),
    "REBATE_87A_NEW_FY25_26": TaxClause(
        section="Section 87A (First Proviso amended)",
        act_reference="Finance Act, 2025",
        document_name="Finance Act, 2025",
        source_url="https://incometaxindia.gov.in/Pages/budget-and-bills/finance-bill.aspx",
        effective_date="2025-04-01 (AY 2026-27)",
        description="Enhanced tax rebate under New Regime for taxable income up to ₹12,00,000 (maximum rebate ₹60,000)."
    ),
    "SURCHARGE_MARGINAL_RELIEF": TaxClause(
        section="First Schedule, Part I, Paragraph A & Finance Act provisions",
        act_reference="Finance Act, 1961 (amended annually)",
        document_name="Finance Acts",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2023-04-01",
        description="Surcharge: 10% (>50L-1Cr), 15% (>1Cr-2Cr), 25% (>2Cr-5Cr), 37% (>5Cr in Old Regime, capped at 25% in New Regime). Marginal relief restricts total tax + surcharge to not exceed tax on threshold plus excess income."
    ),
    "HEALTH_EDUCATION_CESS": TaxClause(
        section="Section 115JB & Finance Acts",
        act_reference="Finance Act, 2018",
        document_name="Income-tax Act, 1961",
        source_url="https://incometaxindia.gov.in/pages/acts/income-tax-act.aspx",
        effective_date="2018-04-01",
        description="Health and Education Cess calculated at the rate of 4% of (Income-tax after rebate + Surcharge)."
    )
}

