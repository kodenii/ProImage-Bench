import time
from typing import Callable
from typing import Optional
import requests
from utils import RateLimitError,BadRequestError,GeneralAPIError,get_model_params,image_to_data_url
# Send a multimodal (text + image) request to Azure OpenAI
MAX_RETRIES = 5
def chat_with_image(
        image_url: str,
        text_prompt: str,
        system: str = "",
        model_type: str = "4o",
        image_list=[],
        validate_response_function: Optional[Callable] = None
) -> Optional[str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = chat_with_image_request(image_url, text_prompt, system=system,model_type=model_type,image_list=image_list)
            if validate_response_function:
                response=validate_response_function(response)
            return response

        except RateLimitError as e:
            if attempt < MAX_RETRIES:
                print(f"️RateLimitError triggered: sleeping for {60*attempt}s", e)
                time.sleep(60*attempt)
            else:
                raise
        except BadRequestError as e:
            print("Maximum retry attempts reached. Stopping execution.")
            raise
        except GeneralAPIError as e:
            if attempt < MAX_RETRIES:
                print(f"GeneralAPIError triggered: sleeping for 10s", e)
                time.sleep(10)
            else:
                raise
        except requests.exceptions.Timeout as e:
            if attempt < MAX_RETRIES:
                print(f"️ requests.exceptions.Timeout triggered: sleeping for {2 ** (attempt - 1)}s", e)
                time.sleep(2 ** (attempt - 1))
            else:
                raise
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                print(f"requests.exceptions.RequestException triggered: sleeping for 10s", e)
                time.sleep(10)
            else:
                raise

        except ValueError as e:
            if attempt < MAX_RETRIES:
                print(f"️Attempt {attempt}: model response parsing failed", e)
                print("Response:", response)
            else:
                print("Maximum retry attempts reached. Stopping execution.")
                raise

        except Exception as e:
            print(f"️Error", e)
            raise

def chat_with_image_request(
        image_url: str,
        text_prompt: str,
        system: str = "",
        model_type: str = "",
        image_list=[],
        max_completion_tokens: int = 4096,
        timeout: int = 60

) -> Optional[str]:
    api_key, azure_endpoint, deployment_name = get_model_params(model_type)

    if not image_list:
        image_data = image_to_data_url(image_url)
        image_messages=[{"type": "image_url", "image_url": {"url": image_data}}]
    else :
        image_data_list=[]
        timeout=200+timeout
        for image in image_list:
            image_data_list.append(image_to_data_url(image))
            image_messages = [{"type": "image_url", "image_url": {"url": image_data}} for image_data in image_data_list]

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        "model": deployment_name,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                ] + image_messages
            }
        ],
        "max_completion_tokens": max_completion_tokens
    }

    url = f"{azure_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version=2024-12-01-preview"

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout+240)

        if response.status_code == 429:
            raise RateLimitError("Request limit exceeded. Please try again later.")
        elif response.status_code == 400:
            raise BadRequestError("Invalid request. The parameters may be incorrect.")
        elif response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            raise GeneralAPIError(f"API request failed with status code: {response.status_code}, error message: {response.text}")
    except requests.exceptions.Timeout as e:
        raise e

    except requests.exceptions.RequestException as e:
        raise e


if __name__ == "__main__":
    print()






