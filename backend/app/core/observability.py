from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI

from app.core.config import Settings

_configured = False
_instrumented_fastapi_apps: set[int] = set()


class NoopSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        pass


def configure_observability(settings: Settings, *, app: FastAPI | None = None) -> None:
    if not settings.logfire_enabled:
        return

    try:
        import logfire
    except ImportError:
        return

    global _configured
    if not _configured:
        logfire.configure(
            send_to_logfire="if-token-present",
            token=settings.logfire_token or None,
            service_name=settings.logfire_service_name,
            environment=settings.environment,
            console=False,
            inspect_arguments=False,
            advanced=logfire.AdvancedOptions(base_url=settings.logfire_base_url or None),
        )
        if settings.logfire_instrument_httpx:
            logfire.instrument_httpx(
                capture_all=False,
                capture_headers=False,
                capture_request_body=False,
                capture_response_body=False,
                request_hook=_sanitize_httpx_request,
            )
        if settings.logfire_instrument_psycopg:
            logfire.instrument_psycopg()
        logfire.instrument_pydantic(record="failure")
        _configured = True

    if app is not None and id(app) not in _instrumented_fastapi_apps:
        logfire.instrument_fastapi(
            app,
            capture_headers=False,
            excluded_urls=r".*/healthz$",
            record_send_receive=False,
            extra_spans=False,
        )
        _instrumented_fastapi_apps.add(id(app))


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    if not _configured:
        yield NoopSpan()
        return

    import logfire

    clean_attributes = {
        key: value for key, value in attributes.items() if value is not None and value != ""
    }
    with logfire.span(name, attributes=clean_attributes) as active_span:
        yield active_span


def search_source_kind(*, image_object_key: str | None, image_url: Any | None) -> str:
    if image_object_key:
        return "object_key"
    if image_url:
        return "url"
    return "missing"


def _sanitize_httpx_request(span: Any, request: Any) -> None:
    sanitized_url = _strip_url_query(str(request.url))
    span.set_attribute("url.full", sanitized_url)
    span.set_attribute("http.url", sanitized_url)


def _strip_url_query(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", parsed.fragment))
