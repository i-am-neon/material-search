from app.core.config import Settings
from app.core.observability import configure_observability, search_source_kind, span


def test_observability_can_be_disabled_without_logfire_side_effects():
    configure_observability(Settings(LOGFIRE_ENABLED=False))

    with span("material_search.test", run_id="run-123") as active_span:
        active_span.set_attribute("ok", True)
        active_span.set_attributes({"count": 1})


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
