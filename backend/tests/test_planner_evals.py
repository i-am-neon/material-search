import json

from app.model_services.planning import GeminiMaterialPlannerClient
from app.search.schemas import SegmentMatchRequest

# Future planner evals to add after the demo set:
# - vague intent, such as "materials with this warm hospitality feel"
# - negative constraints, such as "like the floor but less glossy"
# - non-material intent, such as "match the lamp shape"
# - stricter over-segmentation guards across larger target plans
# - prompt-quality checks for short, visual, segmentable SAM3 prompts
# - stable target_id checks for repeated or overlapping labels


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
    gemini_payload = _gemini_payload(
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
        }
    )

    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    monkeypatch.setattr(
        "app.model_services.planning.httpx.post",
        lambda *args, **kwargs: FakeResponse(payload=gemini_payload),
    )

    plan = GeminiMaterialPlannerClient(api_key="key").plan_material_search(
        SegmentMatchRequest(
            image_url="https://example.com/room.png",
            prompt="Find materials like the green chair upholstery.",
            max_regions=2,
        )
    )

    assert plan.user_intent_summary == "Find upholstery like the green chair."
    assert plan.avoid == []
    assert len(plan.targets) == 1
    assert plan.targets[0].target_id == "green_chair_upholstery"
    assert plan.targets[0].sam3_prompt == "green woven chair upholstery"
    assert plan.targets[0].material_family_hint == "textile"
    assert plan.targets[0].max_regions == 2


def test_planner_eval_multiple_targets_respects_region_budget(monkeypatch):
    gemini_payload = _gemini_payload(
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
        }
    )

    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    monkeypatch.setattr(
        "app.model_services.planning.httpx.post",
        lambda *args, **kwargs: FakeResponse(payload=gemini_payload),
    )

    plan = GeminiMaterialPlannerClient(api_key="key").plan_material_search(
        SegmentMatchRequest(
            image_url="https://example.com/room.png",
            prompt="Find materials like the green chair upholstery and the stone floor.",
            max_regions=3,
        )
    )

    assert [target.target_id for target in plan.targets] == [
        "terrazzo_stone_floor",
        "green_chair_upholstery",
    ]
    assert [target.priority for target in plan.targets] == [1, 2]
    assert [target.max_regions for target in plan.targets] == [2, 1]
    assert sum(target.max_regions for target in plan.targets) == 3


def _fake_image_get(*args, **kwargs):
    return FakeResponse()


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
