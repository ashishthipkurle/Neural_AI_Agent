from agent.core.architecture_conformance import build_conformance_report


def test_conformance_report_shape():
    report = build_conformance_report()

    assert isinstance(report, dict)
    assert report.get("overall") in {"implemented", "partial", "missing"}

    counts = report.get("counts", {})
    assert set(counts.keys()) == {"implemented", "partial", "missing"}

    checks = report.get("checks", [])
    assert isinstance(checks, list)
    assert len(checks) > 0

    for check in checks:
        assert "area" in check
        assert check.get("status") in {"implemented", "partial", "missing"}
