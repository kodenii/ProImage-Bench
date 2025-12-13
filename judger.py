import time
import concurrent.futures
import json
import os
import concurrent.futures
from API.chat import chat_with_image

MAX_RETRIES = 5

def validate_yes_no_response(response):

    cleaned = response.strip()
    if cleaned == "Yes":
        return cleaned
    elif cleaned == "No":
        return cleaned
    else:
        raise ValueError(f"Invalid response: {response}. Expected 'Yes' or 'No'.")

def check_image_exists(img_path):
    """Check whether the image file exists; raise an exception if it does not."""
    if not os.path.exists(img_path) or not os.path.isfile(img_path):
        raise FileNotFoundError(f"Image not found: {img_path}")

    return True


def judgement(task_id):
    system = """
     You are a hyper-conservative evaluator of professional images.
     Your task is to judge whether an image completely satisfies a professional constraint.
     You will receive:
     1. A professional image.
     2. A question: a yes-or-no question checking whether the image meets a given rubric.
     3. Detailed description : a detailed description of the professional image content.
           """


    pro_json_path = "./ProImageBench/ProImageBench.json"
    with open(pro_json_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    task_item = None
    general_item = None

    for item in all_data:
        tid = item.get("task_id")
        if tid == task_id:
            task_item = item
        elif tid == "general_rubric":
            general_item = item

    if task_item is None:
        raise ValueError(f"task_id {task_id} not found in ProImageBench.json")
    if general_item is None:
        general_item = {"rubrics": []}

    detailed_description = task_item.get("detailed_description", "")
    img_url = task_item.get("image_path", "")
    check_image_exists(img_url)

    # Structure of `rubrics`:
    # "rubrics": [
    #   { "Criterion A": ["GP1 for A", "GP2 for A"] },
    #   { "Criterion B": ["GP1 for B", "GP2 for B"] }
    # ]

    def extract_rubrics(task):
        res = []
        for rubric in task.get("rubrics", []):
            if not rubric:
                continue
            (crit_name, gp_list), = rubric.items()
            res.append((crit_name, gp_list))
        return res

    contextual_rubrics = extract_rubrics(task_item)
    general_rubrics = extract_rubrics(general_item)

    # Prepare a score array for each criterion (length = number of corresponding GPs)
    contextual_scores = [
        [0] * len(gp_list) for _, gp_list in contextual_rubrics
    ]
    general_scores = [
        [0] * len(gp_list) for _, gp_list in general_rubrics
    ]

    def process_prompt(criteria_name, grading_prompt, score_matrix, crit_idx, gp_idx):

        prompt = f"""
                    You are a hyper-conservative evaluator of professional images.
                      Your task is to judge whether an image completely satisfies a professional constraint.
                      You will receive:
                      1. A professional image.
                      2. A question: a yes-or-no question checking whether the image meets a given rubric.
                      3. Detailed description : a detailed description of the professional image content.

                      Evaluation principles:
                      1. Begin with the assumption that the image does not meet the question.
                      2. Only answer “Yes” if every detail required by the question is explicitly and accurately shown in the image.
                      3. If any element related to question is missing, unclear, partially visible, inconsistent, approximate, or uncertain, then the answer must be “No”.
                      4. Visual accuracy includes correct position, size, direction, color, proportion, and labeling.
                      5. Do not guess or assume, if evidence is insufficient, treat it as not satisfied.


                      Be completely objective and conservative in your decision.
                      Any small deviation counts as not meeting the requirement.

                      Your response must be exactly one of the following:
                      1. Yes
                      2. No

                   Question: {grading_prompt}
                   Detailed descption: {detailed_description}

                 """

        try:
            response = chat_with_image(
                img_url,
                prompt,
                system,
                model_type="o4-mini",
                validate_response_function=validate_yes_no_response
            )
        except Exception as e:
            print("error", e)
            raise e

        scored = 1 if response == "Yes" else 0

        score_matrix[crit_idx][gp_idx] = scored

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # contextual rubrics
        for crit_idx, (crit_name, gp_list) in enumerate(contextual_rubrics):
            for gp_idx, gp in enumerate(gp_list):
                futures.append(
                    executor.submit(
                        process_prompt,
                        crit_name,
                        gp,
                        contextual_scores,
                        crit_idx,
                        gp_idx
                    )
                )

        for crit_idx, (crit_name, gp_list) in enumerate(general_rubrics):
            for gp_idx, gp in enumerate(gp_list):
                futures.append(
                    executor.submit(
                        process_prompt,
                        crit_name,
                        gp,
                        general_scores,
                        crit_idx,
                        gp_idx
                    )
                )

        concurrent.futures.wait(futures)
        for fut in concurrent.futures.as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                print(f"Thread error occurred: {e}")
                raise e


    contextual_entry = {
        "task_id": task_item.get("task_id"),
        "detailed_description": detailed_description,
        "image_path": img_url,
        "rubrics": []
    }

    for (crit_name, _), scores in zip(contextual_rubrics, contextual_scores):
        contextual_entry["rubrics"].append({crit_name: scores})

    general_entry = {
        "task_id": task_item.get("task_id"),
        "detailed_description": detailed_description,
        "image_path": img_url,
        "rubrics": []
    }

    for (crit_name, _), scores in zip(general_rubrics, general_scores):
        general_entry["rubrics"].append({crit_name: scores})
    general_entry["task_id"] = f"{task_item.get('task_id')}_general"
    return {
        "contextual": contextual_entry,
        "general": general_entry
    }


if __name__=="__main__":
    start=time.time()
    end = time.time()
    print(end-start)













