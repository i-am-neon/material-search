from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalEvalCase:
    name: str
    expected_family: str
    returned_families: list[str]


def test_retrieval_quality_eval_tracks_top_k_family_hit_rate_and_empty_rate():
    cases = [
        RetrievalEvalCase(
            name="green upholstery",
            expected_family="textile",
            returned_families=["textile", "wood", "stone"],
        ),
        RetrievalEvalCase(
            name="terrazzo floor",
            expected_family="stone",
            returned_families=["tile", "stone", "textile"],
        ),
        RetrievalEvalCase(
            name="walnut paneling",
            expected_family="wood",
            returned_families=[],
        ),
    ]

    metrics = retrieval_family_metrics(cases, top_k=2)

    assert metrics == {
        "case_count": 3,
        "top_k_family_hit_rate": 2 / 3,
        "empty_match_rate": 1 / 3,
    }


def retrieval_family_metrics(cases: list[RetrievalEvalCase], *, top_k: int) -> dict:
    hits = 0
    empty = 0
    for case in cases:
        families = case.returned_families[:top_k]
        if not families:
            empty += 1
        if case.expected_family in families:
            hits += 1
    return {
        "case_count": len(cases),
        "top_k_family_hit_rate": hits / len(cases),
        "empty_match_rate": empty / len(cases),
    }
