"""
Comprehensive test suite for Project B (NYC 311 Data Quality Engine).
Tests:
- All 12 corruption injection functions
- Reproducibility with random seeds
- Rule detectors across all 12 corruption types
- Statistical detectors (LOF, Z-Score, Jaccard)
- Multi-tier Hybrid Pipeline execution
"""

import numpy as np
import pandas as pd
import pytest

from project_b.corruption.injector import CorruptionInjector
from project_b.data.fetch_nyc_311 import generate_realistic_nyc_311_data
from project_b.detectors.rules.rule_detectors import RulesDetector
from project_b.detectors.statistical.statistical_detectors import StatisticalDetector
from project_b.pipeline.hybrid_pipeline import HybridDataQualityPipeline


@pytest.fixture(scope="module")
def sample_clean_df():
    """Deterministic clean NYC 311 slice of 200 rows."""
    return generate_realistic_nyc_311_data(num_rows=200, seed=42)


@pytest.fixture(scope="module")
def injector():
    return CorruptionInjector(seed=42)


@pytest.fixture(scope="module")
def rules_detector():
    return RulesDetector()


@pytest.fixture(scope="module")
def stats_detector():
    return StatisticalDetector(random_state=42)


@pytest.fixture(scope="module")
def hybrid_pipeline():
    return HybridDataQualityPipeline()


# ==============================================================================
# TEST 1: ALL 12 CORRUPTION INJECTORS & REPRODUCIBILITY
# ==============================================================================

@pytest.mark.parametrize("corruption_id", list(range(1, 13)))
def test_all_12_corruptions_run(sample_clean_df, injector, corruption_id):
    """Ensure all 12 corruption types inject successfully and produce matching ground truth."""
    res = injector.inject(corruption_id, sample_clean_df, rate=0.10)
    assert res is not None
    assert len(res.labels) == len(res.df)
    assert sum(res.labels) > 0, f"Corruption {corruption_id} produced 0 corrupted rows"


def test_corruption_reproducibility(sample_clean_df, injector):
    """Ensure identical random seeds yield identical corrupted datasets and labels."""
    res1 = injector.inject_latitude_longitude_swapped(sample_clean_df, rate=0.10, seed=123)
    res2 = injector.inject_latitude_longitude_swapped(sample_clean_df, rate=0.10, seed=123)

    assert res1.corrupted_indices == res2.corrupted_indices
    np.testing.assert_array_equal(res1.labels, res2.labels)
    assert res1.df["latitude"].equals(res2.df["latitude"])


# ==============================================================================
# TEST 2: RULE DETECTORS ON CORRUPTIONS
# ==============================================================================

def test_rule_detector_schema(sample_clean_df, injector, rules_detector):
    """Rule detector catches dropped schema columns (Type 1)."""
    corrupt = injector.inject_renamed_or_dropped_column(sample_clean_df, target_col="agency", drop=True)
    preds, exps = rules_detector.detect_schema(corrupt.df)
    assert np.all(preds == 1)
    assert "Missing expected columns" in exps[0]


def test_rule_detector_type_corruption(sample_clean_df, injector, rules_detector):
    """Rule detector catches non-numeric corrupted ZIP codes (Type 2)."""
    corrupt = injector.inject_column_type_change(sample_clean_df, col="incident_zip", rate=0.15)
    preds, _ = rules_detector.detect_type_corruption(corrupt.df)
    # True positives must match injected rows
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


def test_rule_detector_date_format_switch(sample_clean_df, injector, rules_detector):
    """Rule detector catches non-standard date formats (Type 3)."""
    corrupt = injector.inject_date_format_switch(sample_clean_df)
    preds, _ = rules_detector.detect_date_format_switch(corrupt.df)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


def test_rule_detector_lat_lon_swap(sample_clean_df, injector, rules_detector):
    """Rule detector catches swapped latitude and longitude (Type 4)."""
    corrupt = injector.inject_latitude_longitude_swapped(sample_clean_df, rate=0.10)
    preds, _ = rules_detector.detect_coordinate_bounds_and_swap(corrupt.df)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


def test_rule_detector_exact_duplicates(sample_clean_df, injector, rules_detector):
    """Rule detector catches exact duplicate rows (Type 5)."""
    corrupt = injector.inject_exact_duplicates(sample_clean_df, rate=0.05)
    preds, _ = rules_detector.detect_exact_duplicates(corrupt.df)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


def test_rule_detector_closed_before_created(sample_clean_df, injector, rules_detector):
    """Rule detector catches closed < created temporal paradoxes (Type 8)."""
    corrupt = injector.inject_closed_before_created(sample_clean_df, rate=0.10)
    preds, _ = rules_detector.detect_closed_before_created(corrupt.df)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


def test_rule_detector_borough_zip_mismatch(sample_clean_df, injector, rules_detector):
    """Rule detector catches cross-column borough-zip mismatches (Type 9)."""
    corrupt = injector.inject_zip_borough_inconsistent(sample_clean_df, rate=0.10)
    preds, _ = rules_detector.detect_zip_borough_inconsistency(corrupt.df)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


def test_rule_detector_pii(sample_clean_df, injector, rules_detector):
    """Rule detector catches free-text PII (Type 12)."""
    corrupt = injector.inject_personal_data_leak(sample_clean_df, rate=0.10)
    preds, _ = rules_detector.detect_pii(corrupt.df)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


# ==============================================================================
# TEST 3: STATISTICAL DETECTORS
# ==============================================================================

def test_statistical_null_spike_zscore(sample_clean_df, injector, stats_detector):
    """Statistical detector flags agency null rate spike via Z-score (Type 7)."""
    corrupt = injector.inject_null_spike(sample_clean_df, agency="NYPD", spike_rate=0.90)
    preds, exps = stats_detector.detect_null_rate_zscore(corrupt.df)
    assert sum(preds) > 0
    flagged_indices = np.where(preds == 1)[0]
    # Check that flagged records belong to NYPD
    assert all(corrupt.df.iloc[idx]["agency"] == "NYPD" for idx in flagged_indices)


def test_statistical_near_duplicates_jaccard(sample_clean_df, injector, stats_detector):
    """Statistical detector flags near-duplicates using Jaccard string similarity (Type 6)."""
    corrupt = injector.inject_near_duplicates(sample_clean_df, rate=0.05)
    preds, _ = stats_detector.detect_near_duplicates_similarity(corrupt.df, similarity_threshold=0.80)
    for idx in corrupt.corrupted_indices:
        assert preds[idx] == 1


# ==============================================================================
# TEST 4: HYBRID PIPELINE
# ==============================================================================

def test_hybrid_pipeline_execution(sample_clean_df, injector, hybrid_pipeline):
    """Hybrid pipeline executes all tiers cleanly on a corrupted dataset."""
    corrupt = injector.inject_closed_before_created(sample_clean_df, rate=0.10)
    res = hybrid_pipeline.run_hybrid_pipeline(corrupt.df, y_true=corrupt.labels)

    assert res is not None
    assert len(res.labels) == len(corrupt.df)
    assert res.metrics["f1"] > 0.80
    assert res.throughput_rows_per_sec > 100

