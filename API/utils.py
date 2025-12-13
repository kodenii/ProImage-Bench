from pathlib import Path
import base64
class RateLimitError(Exception):
    def __init__(self, message="Rate limit exceeded."):
        self.message = message
        super().__init__(self.message)
class BadRequestError(Exception):
    def __init__(self, message="Bad request."):
        self.message = message
        super().__init__(self.message)
class GeneralAPIError(Exception):
    def __init__(self, message="Unexpected API error."):
        self.message = message
        super().__init__(self.message)

def image_to_data_url(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }.get(ext, "image/png")  # Default to image/png if unknown

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"

def get_model_params(model_type: str):
    if model_type == "4o":
        api_key = ""
        azure_endpoint = ""
        deployment_name = "gpt-4o"
    elif model_type == "o3":
        api_key = ""
        azure_endpoint = ""
        deployment_name = "o3-DR"
    elif model_type == "o4-mini":
        api_key = ""
        azure_endpoint = ""
        deployment_name = "o4-mini"
    elif model_type in ["img","edit"] :
        api_key = ""
        azure_endpoint = ""
        deployment_name = "gpt-image-1"
    else:
        raise ValueError(f"Unsupported model type：{model_type}")

    return api_key, azure_endpoint, deployment_name