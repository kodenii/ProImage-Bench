#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
import argparse
import sys
import re
def get_base_task_id(task_id: str) -> str:

    return re.sub(r"_general$", "", task_id)

def compute_total_metrics(results_dir="./results", mode="all"):
    prefix_map = {
        "bio": "bio_",
        "engineering": "engineering_",
        "general": "general_",
        "all": None,
    }
    if mode not in prefix_map:
        raise ValueError(f"Unknown mode: {mode}")

    prefix = prefix_map[mode]

    results_path = Path(results_dir) / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"Result file not found: {results_path}")


    with results_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict) and "results" in data:
            all_entries = data["results"]
        elif isinstance(data, list):
            all_entries = data
        else:
            all_entries = [data]

    merged_tasks = {}

    for entry in all_entries:
        task_id = entry.get("task_id", "")

        if prefix is not None and not task_id.startswith(prefix):
            continue

        base_id = get_base_task_id(task_id)

        if base_id not in merged_tasks:
            merged_tasks[base_id] = {"rubrics": []}

        merged_tasks[base_id]["rubrics"].extend(entry.get("rubrics", []))

    # Compute metrics
    total_rubric_count = 0
    total_rubric_ones = 0
    criteria_score_sum = 0.0
    criteria_count = 0

    for base_id, task in merged_tasks.items():
        for crit_obj in task["rubrics"]:
            if not isinstance(crit_obj, dict):
                continue

            for criterion, scores in crit_obj.items():
                if not isinstance(scores, list):
                    continue

                total_rubric_count += len(scores)
                total_rubric_ones += sum(1 for s in scores if s == 1)

                num_zero = sum(1 for s in scores if s == 0)
                criterion_score = 0.5 ** num_zero
                criteria_score_sum += criterion_score
                criteria_count += 1

    acc = total_rubric_ones / total_rubric_count if total_rubric_count else 0.0
    score = criteria_score_sum / criteria_count if criteria_count else 0.0

    return {
        "mode": mode,
        "Acc": acc,
        "Score": score,
        "rubric_total": total_rubric_count,
        "rubric_ones": total_rubric_ones,
        "criteria_total": criteria_count,
        "base_task_total": len(merged_tasks)
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute overall metrics (Acc & Score) from results.json (merged contextual + general)."
    )
    parser.add_argument(
        "mode",
        choices=["bio", "engineering", "general", "all"],
        help="Scope of statistics"
    )
    parser.add_argument(
        "--results_dir",
        default="./results",
        help="Results directory"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()

    try:
        results = compute_total_metrics(
            results_dir=args.results_dir,
            mode=args.mode
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(results, ensure_ascii=False, indent=2))
