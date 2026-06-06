import json
import re

import pytest

from app.model_services.planning import GeminiMaterialPlannerClient
from app.search.schemas import SegmentMatchRequest

# Future planner eval:
# - non-material intent, such as "match the lamp shape"; the current plan schema
#   requires at least one material target, so unsupported intent needs a product
#   response shape before this can become a passing eval.


class FakeResponse:
    def __init__(self, *, payload=None, content=b"image-bytes", headers=None):
        self.payload = payload
        self.content = content
        self.headers = headers or {"content-type": "image/png"}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_planner_eval_single_target_material_plan(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find upholstery like the green chair.",
            "avoid": [],
            "targets": [
                {
                    "target_id": "green_chair_upholstery",
                    "label": "Green Chair Upholstery",
                    "sam3_prompt": "green woven chair upholstery",
                    "material_family_hint": "textile",
                    "reason": "The user asked for the green chair fabric.",
                    "priority": 1,
                    "max_regions": 2,
                }
            ],
        },
        prompt="Find materials like the green chair upholstery.",
        max_regions=2,
    )

    assert plan.user_intent_summary == "Find upholstery like the green chair."
    assert plan.avoid == []
    assert len(plan.targets) == 1
    assert plan.targets[0].target_id == "green_chair_upholstery"
    assert plan.targets[0].sam3_prompt == "green woven chair upholstery"
    assert plan.targets[0].material_family_hint == "textile"
    assert plan.targets[0].max_regions == 2
    assert_segmentable_prompt(plan.targets[0].sam3_prompt)


def test_planner_eval_multiple_targets_respects_region_budget(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find the green upholstery and stone floor.",
            "avoid": [],
            "targets": [
                {
                    "target_id": "green_chair_upholstery",
                    "label": "Green Chair Upholstery",
                    "sam3_prompt": "green woven chair upholstery",
                    "material_family_hint": "textile",
                    "reason": "The chair fabric is a requested material.",
                    "priority": 2,
                    "max_regions": 2,
                },
                {
                    "target_id": "terrazzo_stone_floor",
                    "label": "Terrazzo Stone Floor",
                    "sam3_prompt": "light terrazzo stone floor",
                    "material_family_hint": "stone",
                    "reason": "The floor is a requested material.",
                    "priority": 1,
                    "max_regions": 2,
                },
            ],
        },
        prompt="Find materials like the green chair upholstery and the stone floor.",
        max_regions=3,
    )

    assert [target.target_id for target in plan.targets] == [
        "terrazzo_stone_floor",
        "green_chair_upholstery",
    ]
    assert [target.priority for target in plan.targets] == [1, 2]
    assert [target.max_regions for target in plan.targets] == [2, 1]
    assert sum(target.max_regions for target in plan.targets) == 3
    for target in plan.targets:
        assert_segmentable_prompt(target.sam3_prompt)


def test_planner_eval_vague_intent_still_returns_concrete_material_targets(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find warm hospitality materials from the scene.",
            "avoid": [],
            "targets": [
                {
                    "target_id": "warm_wood_paneling",
                    "label": "Warm Wood Paneling",
                    "sam3_prompt": "warm walnut wall paneling",
                    "material_family_hint": "wood",
                    "reason": "Wood paneling anchors the warm hospitality feel.",
                    "priority": 1,
                    "max_regions": 2,
                },
                {
                    "target_id": "soft_green_upholstery",
                    "label": "Soft Green Upholstery",
                    "sam3_prompt": "soft green upholstered chair",
                    "material_family_hint": "textile",
                    "reason": "The upholstered seating contributes softness.",
                    "priority": 2,
                    "max_regions": 1,
                },
            ],
        },
        prompt="Find materials with this warm hospitality feel.",
        max_regions=3,
    )

    assert [target.material_family_hint for target in plan.targets] == ["wood", "textile"]
    assert all("feel" not in target.sam3_prompt for target in plan.targets)
    for target in plan.targets:
        assert_segmentable_prompt(target.sam3_prompt)


def test_planner_eval_negative_constraints_are_preserved(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find a floor material but avoid glossy finishes.",
            "avoid": [" too glossy ", "mirror finish", ""],
            "targets": [
                {
                    "target_id": "matte_stone_floor",
                    "label": "Matte Stone Floor",
                    "sam3_prompt": "matte light stone floor",
                    "material_family_hint": "stone",
                    "reason": "The user asked for the floor material.",
                    "priority": 1,
                    "max_regions": 2,
                }
            ],
        },
        prompt="Find something like the floor but less glossy.",
        max_regions=2,
    )

    assert plan.avoid == ["too glossy", "mirror finish"]
    assert plan.targets[0].material_family_hint == "stone"
    assert_segmentable_prompt(plan.targets[0].sam3_prompt)


@pytest.mark.xfail(
    reason="Unsupported non-material intent needs a planner response shape with zero targets.",
    strict=True,
)
def test_planner_eval_non_material_intent_declines_unsupported_retrieval(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "The request is about lamp shape, not material matching.",
            "avoid": [],
            "targets": [],
        },
        prompt="Match the lamp shape.",
        max_regions=2,
    )

    assert plan.targets == []


def test_planner_eval_over_segmentation_guard_limits_targets(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find several visible materials.",
            "avoid": [],
            "targets": [
                _target_payload(index, max_regions=2)
                for index in range(1, 7)
            ],
        },
        prompt="Find all the main materials in this room.",
        max_regions=3,
    )

    assert len(plan.targets) == 2
    assert [target.max_regions for target in plan.targets] == [2, 1]
    assert sum(target.max_regions for target in plan.targets) == 3


def test_planner_eval_stable_target_ids_for_overlapping_labels(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find two green seating materials.",
            "avoid": [],
            "targets": [
                {
                    "target_id": "Green Seating!!",
                    "label": "Green Seating",
                    "sam3_prompt": "green woven chair upholstery",
                    "material_family_hint": "textile",
                    "reason": "First green seating surface.",
                    "priority": 1,
                    "max_regions": 1,
                },
                {
                    "target_id": "green seating",
                    "label": "Green Seating",
                    "sam3_prompt": "green barstool upholstery",
                    "material_family_hint": "textile",
                    "reason": "Second green seating surface.",
                    "priority": 2,
                    "max_regions": 1,
                },
            ],
        },
        prompt="Find the green seating materials.",
        max_regions=2,
    )

    assert [target.target_id for target in plan.targets] == [
        "green_seating",
        "green_seating_2",
    ]
    assert len({target.target_id for target in plan.targets}) == len(plan.targets)


def _fake_image_get(*args, **kwargs):
    return FakeResponse()


def _plan_from_model_payload(
    monkeypatch,
    plan_payload: dict,
    *,
    prompt: str,
    max_regions: int,
):
    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    monkeypatch.setattr(
        "app.model_services.planning.httpx.post",
        lambda *args, **kwargs: FakeResponse(payload=_gemini_payload(plan_payload)),
    )

    return GeminiMaterialPlannerClient(api_key="key").plan_material_search(
        SegmentMatchRequest(
            image_url="https://example.com/room.png",
            prompt=prompt,
            max_regions=max_regions,
        )
    )


def _target_payload(index: int, *, max_regions: int) -> dict:
    return {
        "target_id": f"material_{index}",
        "label": f"Material {index}",
        "sam3_prompt": f"visible material surface {index}",
        "material_family_hint": "stone",
        "reason": f"Visible material target {index}.",
        "priority": index,
        "max_regions": max_regions,
    }


def _gemini_payload(plan: dict) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(plan),
                        }
                    ]
                }
            }
        ]
    }


def assert_segmentable_prompt(prompt: str) -> None:
    assert 3 <= len(prompt) <= 80
    assert prompt == prompt.lower()
    assert re.search(r"(wood|stone|floor|upholster|woven|chair|panel)", prompt)
    assert not re.search(r"\b(find|match|similar|catalog|product|feel)\b", prompt)
