"""
Test suite for the Plain-Language English & Hinglish Tax Input Parser.
Verifies parsing of standard phrases, Hinglish queries, salary formats,
missing information requests, and contradiction detection.
"""

from decimal import Decimal
import json
import pytest

from project_a.parsers.tax_input_parser import TaxInputParser
from shared.config import PROJECT_A_DIR

SAMPLES_PATH = PROJECT_A_DIR / "parsers" / "sample_descriptions.json"


@pytest.fixture(scope="module")
def parser():
    return TaxInputParser()


@pytest.fixture(scope="module")
def samples():
    with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_sample_descriptions_count(samples):
    """Ensure at least 50 sample descriptions are provided in sample_descriptions.json."""
    assert len(samples) >= 50


def test_standard_assignment_prompt(parser):
    """Test the exact example from the assignment specification:
    'My annual salary is 12 lakh, I pay 20,000 rent monthly, and I invested 1.5 lakh in 80C.'
    """
    query = "My annual salary is 12 lakh, I pay 20,000 rent monthly, and I invested 1.5 lakh in 80C."
    res = parser.parse(query)

    assert res.is_valid is True
    assert res.tax_input is not None
    assert res.tax_input.gross_salary == Decimal("1200000.00")
    assert res.tax_input.rent_paid == Decimal("240000.00")  # 20k * 12
    assert res.tax_input.section_80c == Decimal("150000.00")
    assert res.clarification_question is None


def test_hinglish_query_parsing(parser):
    """Test Hinglish natural language parsing."""
    query = "Mera annual package 15 lakh hai, main Mumbai me 30,000 monthly kiraya deta hu aur 1.5L 80C me invest kiya hai."
    res = parser.parse(query)

    assert res.is_valid is True
    assert res.tax_input is not None
    assert res.tax_input.gross_salary == Decimal("1500000.00")
    assert res.tax_input.rent_paid == Decimal("360000.00")
    assert res.tax_input.section_80c == Decimal("150000.00")
    assert res.tax_input.is_metro is True  # Mumbai is metro


def test_missing_salary_requests_clarification(parser):
    """Never invent missing values. If salary is absent, ask a clarification question."""
    query = "I pay 25,000 monthly rent in Kolkata and invested 1.5L in 80C. Please calculate my tax."
    res = parser.parse(query)

    assert res.is_valid is False
    assert res.tax_input is None
    assert res.clarification_question is not None
    assert "salary" in res.clarification_question.lower() or "ctc" in res.clarification_question.lower()


def test_contradictory_salary_detected(parser):
    """Contradiction between monthly salary and annual salary must be flagged."""
    query = "My annual salary is 10 lakh per annum, but I earn 2 lakh per month. 80C is 1.5 lakh."
    res = parser.parse(query)

    assert res.is_valid is False
    assert len(res.contradictions) > 0
    assert "contradiction" in res.clarification_question.lower()


def test_contradictory_rent_detected(parser):
    """Contradiction: Living in owned house with no rent vs paying positive rent."""
    query = "I live in my own house and pay no rent, but I pay 30,000 monthly rent for HRA exemption. Salary 14 lakh."
    res = parser.parse(query)

    assert res.is_valid is False
    assert len(res.contradictions) > 0


def test_different_salary_formats(parser):
    """Support LPA, Crore, Lakh, and k formats."""
    q_lpa = "My CTC is 18 LPA."
    res_lpa = parser.parse(q_lpa)
    assert res_lpa.is_valid is True
    assert res_lpa.tax_input.gross_salary == Decimal("1800000.00")

    q_cr = "I earn 1.2 crore per annum."
    res_cr = parser.parse(q_cr)
    assert res_cr.is_valid is True
    assert res_cr.tax_input.gross_salary == Decimal("12000000.00")

    q_m = "My monthly salary is 100k per month."
    res_m = parser.parse(q_m)
    assert res_m.is_valid is True
    assert res_m.tax_input.gross_salary == Decimal("1200000.00")

