from agent.core.conformance_checker import ConformanceChecker


def test_conformance_report_has_pipeline_requirements():
    report = ConformanceChecker('.').report()
    assert report["pipeline_stage_count"] == 13
    assert report["required_count"] >= 30
    assert "checks" in report
