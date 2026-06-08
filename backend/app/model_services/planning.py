import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import PurePath
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.core.observability import search_source_kind, span
from app.search.schemas import MaterialSearchPlan, PlannedMaterialTarget, SegmentMatchRequest

GEMINI_MODEL_ID = "gemini-3.5-flash"
DEFAULT_GEMINI_RETRY_ATTEMPTS = 4
DEFAULT_GEMINI_RETRY_BASE_DELAY_SECONDS = 1.0
DEFAULT_GEMINI_RETRY_MAX_DELAY_SECONDS = 12.0
RETRYABLE_GEMINI_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_GEMINI_STATUSES = {"RESOURCE_EXHAUSTED", "UNAVAILABLE"}


class MaterialPlannerClient(ABC):
    @abstractmethod
    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        raise NotImplementedError

    def repair_segmentation_prompts(
        self,
        *,
        request: SegmentMatchRequest,
        target: PlannedMaterialTarget,
        failed_prompt: str,
        max_alternates: int = 3,
    ) -> "SegmentationPromptRepair":
        return SegmentationPromptRepair(
            target_id=target.target_id,
            failed_prompt=failed_prompt,
            alternate_prompts=[],
            reason="Prompt repair is not configured.",
        )


class SegmentationPromptRepair(BaseModel):
    target_id: str
    failed_prompt: str
    alternate_prompts: list[str] = []
    reason: str


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
        genai_client: Any | None = None,
        retry_attempts: int = DEFAULT_GEMINI_RETRY_ATTEMPTS,
        retry_base_delay_seconds: float = DEFAULT_GEMINI_RETRY_BASE_DELAY_SECONDS,
        retry_max_delay_seconds: float = DEFAULT_GEMINI_RETRY_MAX_DELAY_SECONDS,
        retry_sleep: Any = time.sleep,
    ):
        self.api_key = api_key
        self.model_id = model_id
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else None
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket
        self.timeout_seconds = timeout_seconds
        self._genai_client = genai_client
        self.retry_attempts = max(1, retry_attempts)
        self.retry_base_delay_seconds = max(0.0, retry_base_delay_seconds)
        self.retry_max_delay_seconds = max(0.0, retry_max_delay_seconds)
        self.retry_sleep = retry_sleep

    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        image_bytes, mime_type = self._load_image(request)
        client, types = self._client_and_types()
        with span(
            "material_search.gemini_generate_plan",
            run_id=str(request.run_id) if request.run_id else None,
            source_kind=search_source_kind(
                image_object_key=request.image_object_key,
                image_url=request.image_url,
            ),
            model_id=self.model_id,
            prompt_length=len(request.prompt),
            max_regions=request.max_regions,
            image_mime_type=mime_type,
            image_size_bytes=len(image_bytes),
        ) as active_span:
            response, attempt_count = self._generate_content_with_retries(
                client=client,
                model=self.model_id,
                contents=[
                    _planner_prompt(request.prompt, request.max_regions),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
                ),
            )
            active_span.set_attributes(
                {
                    **gemini_response_attributes(response),
                    "gemini_attempt_count": attempt_count,
                }
            )
            text = _first_text_part(response)
            plan = MaterialSearchPlan.model_validate_json(_strip_json_fence(text))
            normalized = _normalize_plan(plan, max_regions=request.max_regions)
            active_span.set_attributes(
                {
                    "is_material_search": normalized.is_material_search,
                    "target_count": len(normalized.targets),
                    "target_ids": [target.target_id for target in normalized.targets],
                    "target_labels": [target.label for target in normalized.targets],
                    "sam3_prompts": [target.sam3_prompt for target in normalized.targets],
                    "avoid_count": len(normalized.avoid),
                    "unsupported": not normalized.is_material_search,
                    "unsupported_reason": normalized.unsupported_reason,
                }
            )
            return normalized

    def repair_segmentation_prompts(
        self,
        *,
        request: SegmentMatchRequest,
        target: PlannedMaterialTarget,
        failed_prompt: str,
        max_alternates: int = 3,
    ) -> SegmentationPromptRepair:
        image_bytes, mime_type = self._load_image(request)
        client, types = self._client_and_types()
        with span(
            "material_search.gemini_repair_sam3_prompt",
            run_id=str(request.run_id) if request.run_id else None,
            source_kind=search_source_kind(
                image_object_key=request.image_object_key,
                image_url=request.image_url,
            ),
            model_id=self.model_id,
            target_id=target.target_id,
            target_label=target.label,
            failed_prompt=failed_prompt,
            max_alternates=max_alternates,
            image_mime_type=mime_type,
            image_size_bytes=len(image_bytes),
        ) as active_span:
            response, attempt_count = self._generate_content_with_retries(
                client=client,
                model=self.model_id,
                contents=[
                    _repair_prompt(
                        user_prompt=request.prompt,
                        target=target,
                        failed_prompt=failed_prompt,
                        max_alternates=max_alternates,
                    ),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
                ),
            )
            active_span.set_attributes(
                {
                    **gemini_response_attributes(response),
                    "gemini_attempt_count": attempt_count,
                }
            )
            text = _first_text_part(response)
            repair = SegmentationPromptRepair.model_validate_json(_strip_json_fence(text))
            normalized = _normalize_prompt_repair(
                repair,
                target=target,
                failed_prompt=failed_prompt,
                max_alternates=max_alternates,
            )
            active_span.set_attributes(
                {
                    "alternate_prompt_count": len(normalized.alternate_prompts),
                    "alternate_prompts": normalized.alternate_prompts,
                    "repair_reason": normalized.reason,
                }
            )
            return normalized

    def _client_and_types(self) -> tuple[Any, Any]:
        from google import genai
        from google.genai import types

        if self._genai_client is None:
            self._genai_client = genai.Client(api_key=self.api_key)
        return self._genai_client, types

    def _generate_content_with_retries(
        self,
        *,
        client: Any,
        model: str,
        contents: list[Any],
        config: Any,
    ) -> tuple[Any, int]:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                return response, attempt
            except Exception as exc:
                if not _is_retryable_gemini_error(exc) or attempt == self.retry_attempts:
                    raise
                last_error = exc
                self.retry_sleep(self._retry_delay_seconds(attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError("Gemini request failed before any retry attempt ran")

    def _retry_delay_seconds(self, completed_attempt: int) -> float:
        delay = self.retry_base_delay_seconds * (2 ** (completed_attempt - 1))
        return min(delay, self.retry_max_delay_seconds)

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
- If the user request is not asking for material search or material matching,
  set is_material_search to false, explain unsupported_reason, and return no targets.
- sam3_prompt must be short and visual. It is a SAM3 segmentation prompt, not
  a search query.
- Describe the visible region SAM3 should segment: color + material + surface
  or object + location when helpful.
- For repeated small materials such as tile, target the larger visible surface,
  not one individual unit. Prefer "dark green tiled shower wall" over
  "green square tile".
- Prefer prompts like "green woven chair upholstery", "matte gray stone floor",
  "dark green ceramic tile wall", or "patterned bath mat rug".
- Avoid abstract search words in sam3_prompt, such as "find", "match",
  "similar", "product", "catalog", or "material feel".
- Do not invent product IDs, boxes, similarity scores, or catalog matches.
- Use code-friendly target_id values like "floor_tile" or "green_seating".

JSON shape:
{{
  "user_intent_summary": "short summary",
  "is_material_search": true,
  "unsupported_reason": null,
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


def _repair_prompt(
    *,
    user_prompt: str,
    target: PlannedMaterialTarget,
    failed_prompt: str,
    max_alternates: int,
) -> str:
    return f"""
You are repairing a SAM3 segmentation prompt for a material-search workflow.

SAM3 returned zero regions for the failed prompt. Look at the image and return
JSON only with better segmentation prompts for the same target.

Original user request:
{user_prompt}

Target:
- target_id: {target.target_id}
- label: {target.label}
- material_family_hint: {target.material_family_hint}
- reason: {target.reason}
- failed_sam3_prompt: {failed_prompt}

SAM3 prompt guide:
- Describe a visible region SAM3 should segment, not a product search.
- Use color + material + surface or object + location when useful.
- For repeated small materials such as tile, target the larger visible surface,
  not one individual unit.
- Prefer prompts like "dark green tiled shower wall", "green ceramic tile wall",
  "matte gray stone floor", "green woven chair upholstery", or
  "patterned bath mat rug".
- Avoid abstract words such as "find", "match", "similar", "product",
  "catalog", or "material feel".

Return 1 to {max_alternates} alternate prompts. Do not return the failed prompt.

JSON shape:
{{
  "target_id": "{target.target_id}",
  "failed_prompt": "{failed_prompt}",
  "alternate_prompts": ["better visual SAM3 prompt"],
  "reason": "why these prompts are more segmentable"
}}
""".strip()


def _first_text_part(response: Any) -> str:
    try:
        text = getattr(response, "text", None)
    except ValueError:
        text = None
    if isinstance(text, str) and text.strip():
        return text

    candidates = _get_value(response, "candidates") or []
    for candidate in candidates:
        content = _get_value(candidate, "content") or {}
        for part in _get_value(content, "parts") or []:
            text = _get_value(part, "text")
            if isinstance(text, str) and text.strip():
                return text
    raise RuntimeError("Gemini did not return a text plan")


def gemini_response_attributes(response: Any) -> dict[str, Any]:
    candidates = _get_value(response, "candidates") or []
    thought_signature_lengths: list[int] = []
    thought_part_count = 0
    function_call_count = 0

    for candidate in candidates:
        content = _get_value(candidate, "content") or {}
        for part in _get_value(content, "parts") or []:
            if _get_value(part, "thought"):
                thought_part_count += 1
            thought_signature = _get_value(part, "thought_signature")
            if thought_signature:
                thought_signature_lengths.append(len(thought_signature))
            if _get_value(part, "function_call") or _get_value(part, "functionCall"):
                function_call_count += 1

    usage_metadata = _get_value(response, "usage_metadata") or _get_value(
        response, "usageMetadata"
    )
    return {
        "gemini_candidate_count": len(candidates),
        "gemini_function_call_count": function_call_count,
        "gemini_thought_part_count": thought_part_count,
        "gemini_thought_signature_count": len(thought_signature_lengths),
        "gemini_thought_signature_lengths": thought_signature_lengths,
        "gemini_prompt_token_count": _get_value(usage_metadata, "prompt_token_count"),
        "gemini_candidates_token_count": _get_value(usage_metadata, "candidates_token_count"),
        "gemini_thoughts_token_count": _get_value(usage_metadata, "thoughts_token_count"),
        "gemini_total_token_count": _get_value(usage_metadata, "total_token_count"),
    }


def _is_retryable_gemini_error(exc: Exception) -> bool:
    code = _get_value(exc, "code")
    if isinstance(code, int) and code in RETRYABLE_GEMINI_STATUS_CODES:
        return True

    response = _get_value(exc, "response")
    status_code = _get_value(response, "status_code")
    if isinstance(status_code, int) and status_code in RETRYABLE_GEMINI_STATUS_CODES:
        return True

    status = _get_value(exc, "status")
    if isinstance(status, str) and status.upper() in RETRYABLE_GEMINI_STATUSES:
        return True

    text = str(exc).upper()
    return any(status in text for status in RETRYABLE_GEMINI_STATUSES)


def _get_value(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    json.loads(stripped)
    return stripped


def _normalize_prompt_repair(
    repair: SegmentationPromptRepair,
    *,
    target: PlannedMaterialTarget,
    failed_prompt: str,
    max_alternates: int,
) -> SegmentationPromptRepair:
    prompts: list[str] = []
    seen = {failed_prompt.strip().lower()}
    for prompt in repair.alternate_prompts:
        normalized = " ".join(prompt.strip().split())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        prompts.append(normalized[:160])
        if len(prompts) >= max_alternates:
            break
    return SegmentationPromptRepair(
        target_id=target.target_id,
        failed_prompt=failed_prompt,
        alternate_prompts=prompts,
        reason=(repair.reason or "Generated alternate SAM3 prompts.").strip()[:500],
    )


def _normalize_plan(plan: MaterialSearchPlan, *, max_regions: int) -> MaterialSearchPlan:
    if not plan.is_material_search:
        return plan.model_copy(
            update={
                "avoid": [item.strip() for item in plan.avoid if item.strip()],
                "targets": [],
            }
        )

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
