import json

import httpx

from api_client import BrandMonitorClient


def test_login_uses_oauth_form_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/login"
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert request.read() == b"username=user%40example.com&password=password123"
        return httpx.Response(
            200, json={"access_token": "token", "token_type": "bearer"}
        )

    client = BrandMonitorClient(
        "http://test", transport=httpx.MockTransport(handler)
    )
    try:
        assert client.login("user@example.com", "password123") == "token"
    finally:
        client.close()


def test_create_mention_sends_api_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/mentions"
        assert request.headers["authorization"] == "Bearer token"
        assert json.loads(request.read())["brand"] == "OpenAI"
        return httpx.Response(201, json={"id": 1})

    client = BrandMonitorClient(
        "http://test", token="token", transport=httpx.MockTransport(handler)
    )
    try:
        assert client.create_mention(
            {
                "brand": "OpenAI",
                "source": "Reddit",
                "text": "Great product",
                "url": "https://reddit.com/post",
                "timestamp": "2026-11-14T00:00:00",
            }
        ) == {"id": 1}
    finally:
        client.close()
