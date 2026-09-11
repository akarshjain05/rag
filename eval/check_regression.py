import json
import sys

def check_regression(baseline_file: str, current_file: str, threshold: float = 0.10):
    with open(baseline_file) as f:
        baseline = json.load(f)
    with open(current_file) as f:
        current = json.load(f)

    baseline_cats = baseline.get("by_category", {})
    current_cats = current.get("by_category", {})
    
    failed = False
    
    for category, base_metrics in baseline_cats.items():
        curr_metrics = current_cats.get(category, {})
        for metric in ["answer_correctness", "faithfulness"]:
            base_val = base_metrics.get(metric)
            curr_val = curr_metrics.get(metric)
            if base_val is not None and curr_val is not None:
                drop = base_val - curr_val
                if drop > threshold:
                    print(f"REGRESSION in {category} {metric}: {base_val:.2f} -> {curr_val:.2f} (drop: {drop:.2f})")
                    failed = True

    if failed:
        sys.exit(1)
    else:
        print("All checks passed. No regressions detected.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python check_regression.py <baseline_json> <current_json>")
        sys.exit(1)
    check_regression(sys.argv[1], sys.argv[2])
