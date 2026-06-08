import json
import re
from types import SimpleNamespace

from app.model_services.planning import GeminiMaterialPlannerClient, gemini_response_attributes
from app.search.schemas import SegmentMatchRequest


class FakeResponse:
    def __init__(self, *, payload=None, content=b"image-bytes", headers=None):
        self.payload = payload
        self.content = content
        self.headers = headers or {"content-type": "image/png"}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text
        self.candidates = []
        self.usage_metadata = None


class FakeGeminiModels:
    def __init__(self, response: FakeGeminiResponse | list):
        self.responses = response if isinstance(response, list) else [response]
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeGeminiClient:
    def __init__(self, response: FakeGeminiResponse | list):
        self.models = FakeGeminiModels(response)


class FakeGeminiError(Exception):
    def __init__(self, message: str, *, code: int | None = None, status: str | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


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
                    "material_family_hint": "paneling",
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

    assert [target.material_family_hint for target in plan.targets] == ["paneling", "textile"]
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


def test_planner_eval_non_material_intent_declines_unsupported_retrieval(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "The request is about lamp shape, not material matching.",
            "is_material_search": False,
            "unsupported_reason": "Lamp shape matching is not a material search.",
            "avoid": [],
            "targets": [],
        },
        prompt="Match the lamp shape.",
        max_regions=2,
    )

    assert plan.is_material_search is False
    assert plan.unsupported_reason == "Lamp shape matching is not a material search."
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


def test_planner_eval_mood_board_preserves_distinct_material_samples(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Identify materials across the mood board.",
            "avoid": [],
            "targets": [
                _mood_board_target(
                    1,
                    "rose_linen_swatch",
                    "Rose Linen Swatch",
                    "rose woven linen fabric swatch",
                    "textile",
                ),
                _mood_board_target(
                    2,
                    "olive_boucle_swatch",
                    "Olive Boucle Swatch",
                    "olive green boucle fabric square",
                    "textile",
                ),
                _mood_board_target(
                    3,
                    "rust_woven_fabric",
                    "Rust Woven Fabric",
                    "rust red woven fabric swatch",
                    "textile",
                ),
                _mood_board_target(
                    4,
                    "white_textile_swatch",
                    "White Textile Swatch",
                    "white textured textile swatch",
                    "textile",
                ),
                _mood_board_target(
                    5,
                    "large_oak_wood_sample",
                    "Large Oak Wood Sample",
                    "large light oak wood board",
                    "paneling",
                ),
                _mood_board_target(
                    6,
                    "dark_wood_panel_sample",
                    "Dark Wood Panel Sample",
                    "dark warm wood panel sample",
                    "paneling",
                ),
                _mood_board_target(
                    7,
                    "small_oak_block",
                    "Small Oak Block",
                    "small light oak wood block",
                    "surface",
                ),
                _mood_board_target(
                    8,
                    "olive_paint_chip",
                    "Olive Paint Chip",
                    "olive green paint chip",
                    "paint",
                ),
                _mood_board_target(
                    9,
                    "gray_stone_tile",
                    "Gray Stone Tile",
                    "gray veined stone tile sample",
                    "stone",
                ),
                _mood_board_target(
                    10,
                    "wood_bowl_finish",
                    "Wood Bowl Finish",
                    "round wood bowl with amber finish",
                    "paint",
                ),
            ],
        },
        prompt="Identify the different material samples in this mood board.",
        max_regions=12,
    )

    assert len(plan.targets) == 10
    assert [target.max_regions for target in plan.targets] == [1] * 10
    assert plan.targets[-1].target_id == "wood_bowl_finish"
    assert {target.material_family_hint for target in plan.targets} >= {
        "textile",
        "paneling",
        "surface",
        "paint",
        "stone",
    }
    for target in plan.targets:
        assert_segmentable_prompt(target.sam3_prompt)


def test_planner_eval_mood_board_3_includes_missed_edge_samples_and_categories(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Identify all material samples on the mood board.",
            "avoid": [],
            "targets": [
                _mood_board_target(
                    1,
                    "cream_linen_folded_swatch",
                    "Cream Linen Folded Swatch",
                    "folded cream linen fabric swatch on left",
                    "textile",
                ),
                _mood_board_target(
                    2,
                    "brass_hardware",
                    "Brass Hardware",
                    "small brass knob and handle on right",
                    "hardware",
                ),
                _mood_board_target(
                    3,
                    "white_tile_grid",
                    "White Tile Grid",
                    "small white square tile grid on lower right",
                    "tile",
                ),
                _mood_board_target(
                    4,
                    "black_stone_sample",
                    "Black Stone Sample",
                    "round black stone sample on lower right",
                    "stone",
                ),
            ],
        },
        prompt="Identify the different material samples in this mood board.",
        max_regions=12,
    )

    targets = {target.target_id: target for target in plan.targets}
    assert targets["cream_linen_folded_swatch"].material_family_hint == "textile"
    assert targets["brass_hardware"].material_family_hint == "hardware"
    assert targets["white_tile_grid"].material_family_hint == "tile"
    assert targets["black_stone_sample"].material_family_hint == "stone"
    assert [target.max_regions for target in plan.targets] == [1, 1, 1, 1]
    for target in plan.targets:
        assert_segmentable_prompt(target.sam3_prompt)


def test_planner_drops_invalid_free_text_catalog_filter_values(monkeypatch):
    plan = _plan_from_model_payload(
        monkeypatch,
        {
            "user_intent_summary": "Find the brass hardware sample.",
            "avoid": [],
            "targets": [
                _mood_board_target(
                    1,
                    "brass_hardware",
                    "Brass Hardware",
                    "small brass knob and handle on right",
                    "brass hardware pull",
                ),
            ],
        },
        prompt="Find the brass hardware sample.",
        max_regions=1,
    )

    assert plan.targets[0].material_family_hint is None


def test_planner_prompt_guides_mood_board_enumeration(monkeypatch):
    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    genai_client = FakeGeminiClient(
        FakeGeminiResponse(
            json.dumps(
                {
                    "user_intent_summary": "Identify mood board samples.",
                    "avoid": [],
                    "targets": [
                        _mood_board_target(
                            1,
                            "olive_paint_chip",
                            "Olive Paint Chip",
                            "olive green paint chip",
                            "paint",
                        )
                    ],
                }
            )
        ),
    )

    GeminiMaterialPlannerClient(
        api_key="key",
        genai_client=genai_client,
    ).plan_material_search(
        SegmentMatchRequest(
            image_url="https://example.com/mood-board.png",
            prompt="Find every material on this mood board.",
            max_regions=12,
        )
    )

    prompt = genai_client.models.requests[0]["contents"][0]
    compact_prompt = " ".join(prompt.split())
    assert "Produce 1 to 12 targets" in prompt
    assert "mood board, sample board, material palette, or flat-lay" in prompt
    assert "Available catalog filters for material_family_hint" in prompt
    assert "tile, paint, surface, flooring, textile, leather" in prompt
    assert "hardware" in prompt
    assert "material_family_hint must be one exact value" in compact_prompt
    assert "enumerate distinct visible material items as separate targets" in compact_prompt
    assert "return 8 to 12 targets" in compact_prompt
    assert "Do not stop at eight targets" in compact_prompt
    assert "Do not group separate board pieces" in compact_prompt
    assert "small square wood sample" in compact_prompt
    assert "visible paint, stain, glaze, resin, or finish sample" in compact_prompt
    assert "Include it as its own target when visible" in compact_prompt
    assert "folded cream linen swatch" in compact_prompt
    assert "white tile grids" in compact_prompt
    assert "black stone pucks or slabs" in compact_prompt
    assert "lower-right clusters" in compact_prompt
    assert "include both as separate targets" in compact_prompt
    assert 'use material_family_hint "hardware"' in compact_prompt
    assert "paint chips" in prompt
    assert "max_regions: 1" in prompt


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


def test_planner_repairs_failed_sam3_prompt(monkeypatch):
    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    genai_client = FakeGeminiClient(
        FakeGeminiResponse(
            json.dumps(
                {
                    "target_id": "green_shower_tile",
                    "failed_prompt": "green square tile",
                    "alternate_prompts": [
                        "green square tile",
                        " dark green tiled shower wall ",
                        "green ceramic tile wall",
                    ],
                    "reason": "The wall surface is more segmentable than one tile.",
                }
            )
        ),
    )

    repair = GeminiMaterialPlannerClient(
        api_key="key",
        genai_client=genai_client,
    ).repair_segmentation_prompts(
        request=SegmentMatchRequest(
            image_url="https://example.com/room.png",
            prompt="Find the green shower tile.",
            max_regions=1,
        ),
        target=_planned_target(
            target_id="green_shower_tile",
            label="Green Shower Tile",
            sam3_prompt="green square tile",
            material_family_hint="tile",
            reason="The user asked for the shower tile.",
        ),
        failed_prompt="green square tile",
        max_alternates=2,
    )

    assert repair.target_id == "green_shower_tile"
    assert repair.failed_prompt == "green square tile"
    assert repair.alternate_prompts == [
        "dark green tiled shower wall",
        "green ceramic tile wall",
    ]
    assert repair.reason == "The wall surface is more segmentable than one tile."


def test_planner_retries_transient_gemini_errors(monkeypatch):
    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    sleep_delays = []
    genai_client = FakeGeminiClient(
        [
            FakeGeminiError(
                "503 UNAVAILABLE. This model is currently experiencing high demand.",
                code=503,
                status="UNAVAILABLE",
            ),
            FakeGeminiError(
                "503 UNAVAILABLE. This model is currently experiencing high demand.",
                code=503,
                status="UNAVAILABLE",
            ),
            FakeGeminiResponse(
                json.dumps(
                    {
                        "user_intent_summary": "Find green upholstery.",
                        "avoid": [],
                        "targets": [
                            {
                                "target_id": "green_chair_upholstery",
                                "label": "Green Chair Upholstery",
                                "sam3_prompt": "green woven chair upholstery",
                                "material_family_hint": "textile",
                                "reason": "The user asked for the green chair fabric.",
                                "priority": 1,
                                "max_regions": 1,
                            }
                        ],
                    }
                )
            ),
        ],
    )

    plan = GeminiMaterialPlannerClient(
        api_key="key",
        genai_client=genai_client,
        retry_attempts=3,
        retry_base_delay_seconds=0.5,
        retry_max_delay_seconds=1.0,
        retry_sleep=sleep_delays.append,
    ).plan_material_search(
        SegmentMatchRequest(
            image_url="https://example.com/room.png",
            prompt="Find materials like the green chair upholstery.",
            max_regions=1,
        )
    )

    assert plan.targets[0].target_id == "green_chair_upholstery"
    assert len(genai_client.models.requests) == 3
    assert sleep_delays == [0.5, 1.0]


def test_planner_does_not_retry_non_transient_gemini_errors(monkeypatch):
    monkeypatch.setattr("app.model_services.planning.httpx.get", _fake_image_get)
    sleep_delays = []
    genai_client = FakeGeminiClient(
        [
            FakeGeminiError(
                "400 INVALID_ARGUMENT. Request payload is invalid.",
                code=400,
                status="INVALID_ARGUMENT",
            ),
        ],
    )

    try:
        GeminiMaterialPlannerClient(
            api_key="key",
            genai_client=genai_client,
            retry_attempts=3,
            retry_sleep=sleep_delays.append,
        ).plan_material_search(
            SegmentMatchRequest(
                image_url="https://example.com/room.png",
                prompt="Find materials like the green chair upholstery.",
                max_regions=1,
            )
        )
    except FakeGeminiError:
        pass
    else:
        raise AssertionError("Expected non-transient Gemini error to be raised")

    assert len(genai_client.models.requests) == 1
    assert sleep_delays == []


def test_gemini_response_attributes_include_tool_and_thought_metadata():
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            text='{"ok": true}',
                            thought=True,
                            thought_signature=b"opaque-signature",
                            function_call={"name": "search_catalog"},
                        )
                    ]
                )
            )
        ],
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=20,
            thoughts_token_count=30,
            total_token_count=60,
        ),
    )

    assert gemini_response_attributes(response) == {
        "gemini_candidate_count": 1,
        "gemini_function_call_count": 1,
        "gemini_thought_part_count": 1,
        "gemini_thought_signature_count": 1,
        "gemini_thought_signature_lengths": [16],
        "gemini_prompt_token_count": 10,
        "gemini_candidates_token_count": 20,
        "gemini_thoughts_token_count": 30,
        "gemini_total_token_count": 60,
    }


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
    genai_client = FakeGeminiClient(
        FakeGeminiResponse(json.dumps(plan_payload)),
    )

    return GeminiMaterialPlannerClient(
        api_key="key",
        genai_client=genai_client,
    ).plan_material_search(
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


def _mood_board_target(
    priority: int,
    target_id: str,
    label: str,
    sam3_prompt: str,
    material_family_hint: str,
) -> dict:
    return {
        "target_id": target_id,
        "label": label,
        "sam3_prompt": sam3_prompt,
        "material_family_hint": material_family_hint,
        "reason": f"The mood board includes the {label.lower()}.",
        "priority": priority,
        "max_regions": 2,
    }


def _planned_target(
    *,
    target_id: str,
    label: str,
    sam3_prompt: str,
    material_family_hint: str,
    reason: str,
):
    from app.search.schemas import PlannedMaterialTarget

    return PlannedMaterialTarget(
        target_id=target_id,
        label=label,
        sam3_prompt=sam3_prompt,
        material_family_hint=material_family_hint,
        reason=reason,
        priority=1,
        max_regions=1,
    )


def assert_segmentable_prompt(prompt: str) -> None:
    assert 3 <= len(prompt) <= 80
    assert prompt == prompt.lower()
    assert re.search(
        r"(wood|stone|floor|upholster|woven|chair|panel|fabric|textile|paint|chip|tile|boucle|linen|brass|knob|handle)",
        prompt,
    )
    assert not re.search(r"\b(find|match|similar|catalog|product|feel)\b", prompt)
