import json
from pathlib import Path
from typing import Dict, Any, List


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def compare_one_run(cases: List[Dict[str, Any]], run: Dict[str, Any]) -> Dict[str, Any]:
    total = len(cases)
    matched = 0
    mismatches = []

    for case in cases:
        cid = case["id"]
        expected = case.get("expected")
        got = run.get(cid)
        if got == expected:
            matched += 1
        else:
            mismatches.append({"id": cid, "expected": expected, "got": got})

    accuracy = matched / total if total else 0.0
    return {"total": total, "matched": matched, "accuracy": accuracy, "mismatches": mismatches}


def compare_two_runs(cases: List[Dict[str, Any]],
                     run_a: Dict[str, Any],
                     run_b: Dict[str, Any]) -> Dict[str, Any]:
    metrics_a = compare_one_run(cases, run_a)
    metrics_b = compare_one_run(cases, run_b)
    delta = metrics_b["accuracy"] - metrics_a["accuracy"]
    return {"run_a": metrics_a, "run_b": metrics_b, "delta_accuracy": delta}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="A/B compare LLM command parses.")
    parser.add_argument("--cases", required=True, help="JSON file with cases: [{id, expected}, ...]")
    parser.add_argument("--run-a", required=True, help="JSON file with baseline results keyed by id")
    parser.add_argument("--run-b", required=True, help="JSON file with candidate results keyed by id")
    args = parser.parse_args()

    cases = load_json(args.cases)
    run_a = load_json(args.run_a)
    run_b = load_json(args.run_b)

    result = compare_two_runs(cases, run_a, run_b)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
