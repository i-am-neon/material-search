import re

from app.core.config import Settings
from app.core.observability import (
    _FASTAPI_EXCLUDED_URLS,
    configure_observability,
    search_source_kind,
    span,
)


def test_observability_can_be_disabled_without_logfire_side_effects():
    configure_observability(Settings(LOGFIRE_ENABLED=False))

    with span("material_search.test", run_id="run-123") as active_span:
        active_span.set_attribute("ok", True)
        active_span.set_attributes({"count": 1})


def test_psycopg_logfire_instrumentation_is_off_by_default(monkeypatch):
    monkeypatch.delenv("LOGFIRE_INSTRUMENT_PSYCOPG", raising=False)

    assert Settings(_env_file=None).logfire_instrument_psycopg is False


def test_search_source_kind_labels_material_search_inputs():
    object_key_source = search_source_kind(
        image_object_key="uploads/a/reference.jpg",
        image_url=None,
    )
    url_source = search_source_kind(
        image_object_key=None,
        image_url="https://example.test/image.jpg",
    )

    assert object_key_source == "object_key"
    assert url_source == "url"
    assert search_source_kind(image_object_key=None, image_url=None) == "missing"


def test_fastapi_observability_excludes_polling_urls():
    excluded = [re.compile(pattern) for pattern in _FASTAPI_EXCLUDED_URLS]

    assert any(pattern.match("http://testserver/healthz") for pattern in excluded)
    assert any(
        pattern.match("http://testserver/search/runs/1804cd88-f240-46f1-9cf6-2b30e4cfead2")
        for pattern in excluded
    )
    assert not any(pattern.match("http://testserver/search/runs") for pattern in excluded)
    assert not any(
        pattern.match("http://testserver/search/segment-matches") for pattern in excluded
    )
