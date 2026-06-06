import base64
import json
import re
from abc import ABC, abstractmethod
from pathlib import PurePath
from urllib.parse import quote

import httpx

from app.search.schemas import MaterialSearchPlan, SegmentMatchRequest

GEMINI_MODEL_ID = "gemini-3.5-flash"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class MaterialPlannerClient(ABC):
    @abstractmethod
    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        raise NotImplementedError


class GeminiMaterialPlannerClient(MaterialPlannerClient):
    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = GEMINI_MODEL_ID,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        uploaded_image_bucket: str = "uploaded-images",
        timeout_seconds: float = 120.0,
    ):
        self.api_key = api_key
        self.model_id = model_id
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else None
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket
        self.timeout_seconds = timeout_seconds

    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        image_bytes, mime_type = self._load_image(request)
        response = httpx.post(
            GEMINI_GENERATE_URL.format(model=self.model_id),
            params={"key": self.api_key},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": _planner_prompt(request.prompt, request.max_regions)},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": base64.b64encode(image_bytes).decode("ascii"),
                                }
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        text = _first_text_part(payload)
        plan = MaterialSearchPlan.model_validate_json(_strip_json_fence(text))
        return _normalize_plan(plan, max_regions=request.max_regions)

    def _load_image(self, request: SegmentMatchRequest) -> tuple[bytes, str]:
        if request.image_url:
            response = httpx.get(str(request.image_url), timeout=30.0, follow_redirects=True)
        elif request.image_object_key:
            if self.supabase_url is None or not self.service_role_key:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required "
                    "to plan searches from uploaded image object keys"
                )
            response = httpx.get(
                self._object_url(request.image_object_key),
                headers=self._auth_headers(),
                timeout=30.0,
                follow_redirects=True,
            )
        else:
            raise ValueError("Either image_object_key or image_url is required")

        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0]
        return response.content, _image_mime_type(content_type, request)

    def _object_url(self, object_key: str) -> str:
        quoted_key = quote(object_key.lstrip("/"), safe="/")
        return f"{self.supabase_url}/storage/v1/object/{self.uploaded_image_bucket}/{quoted_key}"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key or "",
            "authorization": f"Bearer {self.service_role_key}",
        }


class MissingMaterialPlannerClient(MaterialPlannerClient):
    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        raise RuntimeError("GEMINI_API_KEY is required to plan material search intent")


def _planner_prompt(user_prompt: str, max_regions: int) -> str:
    return f"""
You are planning a material search over an interior/product reference image.

Interpret the user's natural-language request and the image. Return JSON only.
Plan concrete material targets that should be segmented with SAM3 and later matched
against a product catalog. Preserve explicit negative constraints such as "avoid
anything too glossy" in the avoid array.

User request:
{user_prompt}

Rules:
- Produce 1 to 5 targets, with the most important first.
- Across all targets, expect at most {max_regions} final regions.
- sam3_prompt must be short and visual, such as "green woven upholstery" or
  "matte gray stone floor".
- Do not invent product IDs, boxes, similarity scores, or catalog matches.
- Use code-friendly target_id values like "floor_tile" or "green_seating".

JSON shape:
{{
  "user_intent_summary": "short summary",
  "avoid": ["constraint or attribute to avoid"],
  "targets": [
    {{
      "target_id": "short_snake_case",
      "label": "human label",
      "sam3_prompt": "visual segmentation prompt",
      "material_family_hint": "tile|textile|wood|stone|wallcovering|null",
      "reason": "why this target matters",
      "priority": 1,
      "max_regions": 2
    }}
  ]
}}
""".strip()


def _first_text_part(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
    raise RuntimeError("Gemini did not return a text plan")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    json.loads(stripped)
    return stripped


def _normalize_plan(plan: MaterialSearchPlan, *, max_regions: int) -> MaterialSearchPlan:
    seen: set[str] = set()
    targets = []
    remaining_regions = max_regions
    for index, target in enumerate(sorted(plan.targets, key=lambda item: item.priority), start=1):
        target_id = _slug_target_id(target.target_id or target.label)
        if target_id in seen:
            target_id = f"{target_id}_{index}"
        seen.add(target_id)
        target_regions = max(1, min(target.max_regions, remaining_regions))
        remaining_regions = max(0, remaining_regions - target_regions)
        targets.append(
            target.model_copy(
                update={
                    "target_id": target_id,
                    "priority": index,
                    "max_regions": target_regions,
                    "material_family_hint": target.material_family_hint or None,
                }
            )
        )
        if remaining_regions == 0:
            break

    return plan.model_copy(
        update={
            "avoid": [item.strip() for item in plan.avoid if item.strip()],
            "targets": targets,
        }
    )


def _slug_target_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "target"


def _image_mime_type(content_type: str, request: SegmentMatchRequest) -> str:
    if content_type in {"image/jpeg", "image/png", "image/webp"}:
        return content_type
    suffix = PurePath(request.image_object_key or str(request.image_url or "")).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
