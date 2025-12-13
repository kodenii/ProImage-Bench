# --- START OF FILE evaluation.py ---
import os
import json
import time
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from judger import judgement as judge  # 确保导入名一致

CHECKPOINT_FILE = "./check/check.json"
RESULTS_FILE = "./results/results.json"


# ========== Checkpoint 工具 (保持不变) ==========
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

    # 2. 统一排序（字典序排序）
    existing_results.sort(key=lambda x: x.get("task_id", ""))

    # 3. 写入文件
    tmp = results_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing_results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, results_path)
def save_checkpoint(done_set: set):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    tmp = CHECKPOINT_FILE + ".tmp"
    data = {"done": sorted(list(done_set))}  # set 转 list 才能 json 序列化
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CHECKPOINT_FILE)


# ========== 结果写入工具 (新增) ==========



# ========== 并行处理主逻辑 ==========
def process_all(task_ids, max_workers: int | None = None):
    done = load_checkpoint()
    # 过滤掉已完成
    to_run = [fn for fn in task_ids if fn not in done]

    print(f"总数: {len(task_ids)}，已完成: {len(done)}，待处理: {len(to_run)}")
    if not to_run:
        return

    max_workers = max_workers or os.cpu_count() or 4

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            future_map = {ex.submit(_worker, fn): fn for fn in to_run}

            for i, fut in enumerate(as_completed(future_map), 1):
                fn = future_map[fut]
                try:
                    # 获取 worker 返回的结果 (contextual_entry, general_entry)
                    result = fut.result()

                    result = fut.result()

                    contextual_entry = result["contextual"]
                    general_entry = result["general"]

                    # 全都写到同一个 ./result/result.json 里
                    upsert_result(RESULTS_FILE, contextual_entry)
                    upsert_result(RESULTS_FILE, general_entry)

                    # 标记完成并保存 checkpoint
                    done.add(fn)
                    save_checkpoint(done)

                    progress = i / len(to_run)
                    bar_len = 30  # 进度条长度
                    filled = int(bar_len * progress)
                    bar = "#" * filled + "-" * (bar_len - filled)

                    print(f"\r[{bar}] {progress * 100:5.1f}% ({i}/{len(to_run)})  当前: {fn}", end="", flush=True)

                except Exception as e:
                    print(f"[错误] {fn}: {e}")
    finally:
        save_checkpoint(done)
        print("处理结束。")


def _worker(task_id, retries=3):
    """Worker 进程只负责计算，返回数据"""
    for attempt in range(1, retries + 1):
        try:
            # 调用 judgement 并返回结果
            return judge(task_id)
        except Exception as e:
            print(f"[重试 {attempt}/{retries}] {task_id}: {e}")
            time.sleep(1)

    raise RuntimeError(f"{task_id} 失败")
def load_task_ids(json_path: str, prefix: str):
    """从 json 中读取指定前缀的 task_id 列表（排除 general_rubric 这类全局条目）。"""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON 文件不存在：{json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    EXCLUDE_TASK_IDS = {"general_rubric"}  # 需要排除的非任务条目

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

    # 位置参数：任务类型（bio / engineering / general）
    parser.add_argument(
        "domain",
        help="任务类型：bio / engineering / general",
    )

    # 可选参数：并行进程数
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="并行进程数（默认4）",
    )

    args = parser.parse_args()

    # 检查 domain 是否有效
    domain = args.domain.lower()
    prefix_map = {
        "bio": "bio_",
        "engineering": "engineering_",
        "general": "general_",
    }

    if domain not in prefix_map:
        print("参数设置错误：domain 只能是 'bio'、'engineering' 或 'general'")
        return

    prefix = prefix_map[domain]

    json_path = "./ProImageBench/ProImageBench.json"

    # 读取并过滤 task_ids
    task_ids = load_task_ids(json_path, prefix)

    if not task_ids:
        print(f"未在 {json_path} 中找到以 '{prefix}' 开头的 task_id")
        return

    print(f"共找到 {len(task_ids)} 个任务（前缀：{prefix}），开始评估……")
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