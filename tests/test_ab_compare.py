from tools.ab_compare import compare_one_run, compare_two_runs


def test_compare_one_run():
    cases = [
        {"id": "a", "expected": {"name": "open_app", "args": {"name": "code"}}},
        {"id": "b", "expected": {"name": "open_url", "args": {"url": "https://example.com"}}},
    ]
    run = {
        "a": {"name": "open_app", "args": {"name": "code"}},
        "b": {"name": "open_url", "args": {"url": "https://wrong.com"}},
    }
    metrics = compare_one_run(cases, run)
    assert metrics["total"] == 2
    assert metrics["matched"] == 1
    assert metrics["accuracy"] == 0.5
    assert metrics["mismatches"][0]["id"] == "b"


def test_compare_two_runs():
    cases = [{"id": "x", "expected": 1}, {"id": "y", "expected": 2}]
    run_a = {"x": 0, "y": 2}
    run_b = {"x": 1, "y": 2}

    result = compare_two_runs(cases, run_a, run_b)
    assert result["run_a"]["accuracy"] == 0.5
    assert result["run_b"]["accuracy"] == 1.0
    assert result["delta_accuracy"] == 0.5
