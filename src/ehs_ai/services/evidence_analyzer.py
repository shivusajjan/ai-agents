from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError
from openai import AsyncOpenAI

from ehs_ai.config import get_settings
from ehs_ai.utils.logger import get_logger

logger = get_logger(__name__)


class EvidenceAnalyzer:
    """Performs AI-assisted analysis on uploaded evidence files."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set for evidence analysis.")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def analyse(self, path: Path) -> str:
        if not path.exists():
            logger.warning("Evidence path %s does not exist.", path)
            return "Evidence file missing."
        try:
            with Image.open(path) as image:
                return await self._analyse_image(path, image)
        except UnidentifiedImageError:
            return "Unsupported evidence type (non-image)."
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to analyse evidence %s: %s", path, exc)
            return "Error processing evidence."

    async def _analyse_image(self, path: Path, image: Image.Image) -> str:
        width, height = image.size
        fmt = image.format or "unknown"

        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        data_url = f"data:image/{fmt.lower()};base64,{encoded}"
        system_prompt = (
            "You are an Environmental Health & Safety investigator. "
            "Identify visible objects, PPE usage, hazards, and likely contributions to the reported incident."
        )
        user_prompt = (
            "Analyse this evidence image. List key objects, potential safety risks, and any mitigating or aggravating factors."
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                max_tokens=300,
            )
            analysis_text = response.choices[0].message.content.strip()
            if not analysis_text:
                analysis_text = "Vision model returned no commentary."
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("OpenAI vision analysis failed for %s: %s", path.name, exc)
            analysis_text = "Unable to complete AI analysis."

        return (
            f"Image {fmt} {width}x{height}px. "
            f"Analysis: {analysis_text}"
        )
