import pytest

from app.search.uploads import build_upload_object_key, validate_upload_content_type


def test_validate_upload_content_type_accepts_supported_image_types():
    assert validate_upload_content_type("image/jpeg") == "image/jpeg"
    assert validate_upload_content_type("image/png") == "image/png"
    assert validate_upload_content_type("image/webp") == "image/webp"


def test_validate_upload_content_type_rejects_non_images():
    with pytest.raises(ValueError, match="JPEG, PNG, and WebP"):
        validate_upload_content_type("application/pdf")


def test_build_upload_object_key_uses_safe_extension_from_content_type():
    object_key = build_upload_object_key("reference", "image/png")

    assert object_key.startswith("uploads/")
    assert object_key.endswith("/reference.png")
