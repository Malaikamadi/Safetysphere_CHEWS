"""Flood early-warning validation diagnostics — no training, no CHEWS integration."""

from __future__ import annotations

from services.flood_validation import (
    VERDICT_E,
    candidate_targets,
    classify_threshold,
    community_geo_mismatches,
    flood_history_temporal_grain,
    missing_not_nonflood,
    rainfall_rule_predict,
    select_rainfall_threshold_on_train,
    temporal_columns,
    binary_metrics,
)


def test_training_schema_has_no_temporal_or_spatial_grain():
    columns = [
        "rainfall_mm_24h", "temperature_c", "humidity_percent", "elevation_m",
        "water_level_m", "drainage_quality", "soil_saturation", "community_reports",
        "flood_occurred",
    ]
    assert temporal_columns(columns) == []
    assert "district" not in columns
    assert "date" not in columns


def test_missing_flood_labels_are_not_converted_to_nonflood():
    assert missing_not_nonflood([1, 0, None, "", "NA", "null"]) == [1, 0, None, None, None, None]


def test_rainfall_baseline_is_selected_on_train_only():
    rain_train = [10, 20, 40, 120, 130, 15, 160, 30]
    y_train = [0, 0, 0, 1, 1, 0, 1, 0]
    chosen = select_rainfall_threshold_on_train(rain_train, y_train, candidates=(50.0, 100.0, 150.0))
    assert chosen["selected_on"] == "train_split_only"
    assert chosen["purpose"] == "diagnostic_baseline_not_operational_policy"
    pred = rainfall_rule_predict([40, 110, 200], chosen["selected_threshold_mm"])
    assert pred[0] == 0
    assert pred[-1] == 1


def test_binary_metrics_do_not_treat_accuracy_as_the_only_score():
    metrics = binary_metrics([1, 1, 0, 0], [1, 0, 0, 0])
    assert metrics["recall"] == 0.5
    assert metrics["missed_event_rate"] == 0.5
    assert "false_alarm_rate" in metrics


def test_year_only_catalog_history_is_not_a_dated_target():
    grain = flood_history_temporal_grain([
        {"year": 2017, "description": "Aug 14 mudslide", "impact": "casualties"},
        {"year": 2023, "description": "August flooding", "impact": "homes inundated"},
    ])
    assert grain["year_only"] is True
    assert grain["usable_as_dated_flood_target"] is False
    assert grain["n_with_day_field"] == 0


def test_community_geo_mismatch_flags_freetown_names_in_inland_districts():
    rows = [
        {"community": "Kissy", "district": "Tonkolili"},
        {"community": "Kroo Bay", "district": "Western Urban"},
        {"community": "Tikonko", "district": "Bo"},
    ]
    mismatches = community_geo_mismatches(rows)
    assert len(mismatches) == 1
    assert mismatches[0]["community"] == "Kissy"


def test_thresholds_are_labelled_hardcoded_until_validated():
    item = classify_threshold("heuristic_composite_high_0.60", 0.60, "hardcoded_prototype")
    assert item["validated_against_flood_events"] is False
    assert item["origin"] == "hardcoded_prototype"


def test_no_candidate_target_is_silently_selected_from_rainfall():
    candidates = candidate_targets()
    rainfall = next(c for c in candidates if c["id"] == "D")
    assert "not adopted as a supervised target" in rainfall["limitations"].lower() or (
        "Rainfall is not a flood event" in rainfall["limitations"]
    )
    observed = next(c for c in candidates if c["id"] == "A")
    assert observed["available_in_repo"] is False


def test_verdict_constant_is_not_ready_for_shadow():
    assert VERDICT_E == "E"


def test_audit_report_does_not_claim_real_world_auc_or_train():
    from services.flood_validation import (
        PROTECTED_PATHS,
        assert_protected_unchanged,
        build_flood_validation_report,
        sha256_file,
    )

    before = {name: sha256_file(path) for name, path in PROTECTED_PATHS.items()}
    report = build_flood_validation_report()
    after = assert_protected_unchanged(before)
    assert report["model_trained_this_phase"] is False
    assert report["invented_flood_labels"] is False
    assert report["missing_converted_to_nonflood"] is False
    assert report["target_assessment"]["supervised_flood_prediction_supported"] is False
    assert report["ml_justified"] is False
    assert report["verdict"]["classification"] == "E"
    assert report["existing_model"]["live_dashboard_calls_predict_ml"] is False
    ml = report["baseline_comparison"]["existing_gbt_synthetic_holdout"]
    if ml.get("evaluated"):
        assert ml["real_world_performance"] is False
    assert after["flood_model_joblib"] == before["flood_model_joblib"]
    assert after["flood_risk_py"] == before["flood_risk_py"]
