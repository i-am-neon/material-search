from app.search.orchestration import _safe_error_message


def test_safe_error_message_redacts_url_query_strings():
    message = (
        "Client error '429 Too Many Requests' for url "
        "'https://generativelanguage.googleapis.com/v1beta/models/gemini:generateContent?key=secret'"
    )

    assert _safe_error_message(message) == (
        "Client error '429 Too Many Requests' for url "
        "'https://generativelanguage.googleapis.com/v1beta/models/gemini:generateContent'"
    )
