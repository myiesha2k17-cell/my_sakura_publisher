"""Optional AI scene images via the OpenAI Images REST API (portrait 1024x1536)."""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from shorts.models import Book
from shorts.providers.base import ProviderError

API = "https://api.openai.com/v1/images/generations"
STYLE = ("Cinematic illustrated book-aesthetic scene, soft film grain, moody lighting, vertical composition. "
         "No text, no letters, no logos, no watermarks.")


class OpenAIImages:
    def __init__(self, api_key: str, model: str = "gpt-image-1"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, out_path: Path, book: Book) -> Path:
        try:
            response = requests.post(
                API,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "prompt": f"{prompt}\n\n{STYLE}", "size": "1024x1536", "n": 1},
                timeout=180,
            )
        except requests.RequestException as e:
            raise ProviderError("Could not reach the image service. Check the network and try again.") from e
        if response.status_code != 200:
            raise ProviderError(f"Image service returned an error ({response.status_code}).")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(response.json()["data"][0]["b64_json"]))
        return out_path
