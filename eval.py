import os
import json
import time
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from judger import judgement as judge

CHECKPOINT_FILE = "./check/check.json"
RESULTS_FILE = "./results/results.json"


# checkpoint tools
def load_checkpoint() -> set:
    if not os.path.exists(CHECKPOINT_FILE):
        return set()
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        done = set(data.get("done", []))
        return done
    except Exception:
        return set()

def upsert_result(results_path, entry):
    os.makedirs(os.path.dirname(results_path), exist_ok=True)

    try:
        if os.path.exists(results_path):
            with open(results_path, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
        else:
            existing_results = []
    except Exception:
        existing_results = []

    # 1. 更新或追加
    updated = False
    for i, item in enumerate(existing_results):
        if item.get("task_id") == entry.get("task_id"):
            existing_results[i] = entry
            updated = True
            break

    if not updated:
        existing_results.append(entry)


    existing_results.sort(key=lambda x: x.get("task_id", ""))
    tmp = results_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing_results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, results_path)
def save_checkpoint(done_set: set):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    tmp = CHECKPOINT_FILE + ".tmp"
    data = {"done": sorted(list(done_set))}
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CHECKPOINT_FILE)


def process_all(task_ids, max_workers: int | None = None):
    done = load_checkpoint()
    # Filter out completed tasks
    to_run = [fn for fn in task_ids if fn not in done]

    print(f"Total tasks: {len(task_ids)}, Completed: {len(done)}, Pending: {len(to_run)}")
    if not to_run:
        return

    max_workers = max_workers or os.cpu_count() or 4

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            future_map = {ex.submit(_worker, fn): fn for fn in to_run}

            for i, fut in enumerate(as_completed(future_map), 1):
                fn = future_map[fut]
                try:
                    # Get results from the worker (contextual_entry, general_entry)
                    result = fut.result()

                    contextual_entry = result["contextual"]
                    general_entry = result["general"]
                    upsert_result(RESULTS_FILE, contextual_entry)
                    upsert_result(RESULTS_FILE, general_entry)

                    # Mark as completed and save the checkpoint
                    done.add(fn)
                    save_checkpoint(done)

                    progress = i / len(to_run)
                    bar_len = 30
                    filled = int(bar_len * progress)
                    bar = "#" * filled + "-" * (bar_len - filled)

                    print(f"\r[{bar}] {progress * 100:5.1f}% ({i}/{len(to_run)})  Now: {fn}", end="", flush=True)

                except Exception as e:
                    print(f"[Error] {fn}: {e}")
    finally:
        save_checkpoint(done)
        print("Processing completed.")


def _worker(task_id, retries=3):
    for attempt in range(1, retries + 1):
        try:
            return judge(task_id)
        except Exception as e:
            print(f"[Retry {attempt}/{retries}] {task_id}: {e}")
            time.sleep(1)

    raise RuntimeError(f"{task_id} failed")
def load_task_ids(json_path: str, prefix: str):
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    EXCLUDE_TASK_IDS = {"general_rubric"}

    task_ids = [
        item["task_id"]
        for item in data
        if "task_id" in item
        and item["task_id"].startswith(prefix)
        and item["task_id"] not in EXCLUDE_TASK_IDS
    ]
    return task_ids

def main():
    parser = argparse.ArgumentParser(
        description="Run ProImageBench evaluation with specific domain and workers."
    )

    # Positional argument: domain (bio / engineering / general)
    parser.add_argument(
        "domain",
        help="Domain type: bio / engineering / general",
    )

    # Optional argument: number of worker processes
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)",
    )

    args = parser.parse_args()

    # Validate the domain argument
    domain = args.domain.lower()
    prefix_map = {
        "bio": "bio_",
        "engineering": "engineering_",
        "general": "general_",
    }

    if domain not in prefix_map:
        print("Invalid argument: domain must be 'bio', 'engineering', or 'general'")
        return

    prefix = prefix_map[domain]

    json_path = "./ProImageBench/ProImageBench.json"

    task_ids = load_task_ids(json_path, prefix)

    if not task_ids:
        print(f"No task_id with prefix '{prefix}' found in {json_path}")
        return

    print(f"Found {len(task_ids)} tasks (prefix: {prefix}). Starting evaluation...")
    process_all(task_ids, max_workers=args.max_workers)


if __name__ == "__main__":
    main()
    """
# bio domain, default 4 processes
python eval.py bio

# engineering domain, specify 8 processes
python eval.py engineering --max-workers 8

# general domain, 3 processes
python eval.py general --max-workers 3

    """