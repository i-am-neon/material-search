from app.core.config import get_settings
from app.model_services.factory import get_sam3_client
from app.model_services.segmentation import HttpSam3Client, MissingSam3Client


def test_sam3_factory_returns_modal_client_even_when_gemini_key_is_set(monkeypatch):
    monkeypatch.setenv("SAM3_SERVICE_URL", "https://sam3.example.com")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    get_settings.cache_clear()

    try:
        client = get_sam3_client()
    finally:
        get_settings.cache_clear()

    assert isinstance(client, HttpSam3Client)
    assert client.base_url == "https://sam3.example.com"


def test_sam3_factory_requires_modal_service_url(monkeypatch):
    monkeypatch.setenv("SAM3_SERVICE_URL", "")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    get_settings.cache_clear()

    try:
        client = get_sam3_client()
    finally:
        get_settings.cache_clear()

    assert isinstance(client, MissingSam3Client)
