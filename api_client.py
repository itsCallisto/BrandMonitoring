"""Small HTTPX client for Streamlit integrations with the FastAPI service."""

import httpx


class BrandMonitorClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=20, transport=transport
        )
        if token:
            self._client.headers["Authorization"] = f"Bearer {token}"

    def register(self, email: str, password: str) -> str:
        response = self._client.post(
            "/auth/register", json={"email": email, "password": password}
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def login(self, email: str, password: str) -> str:
        response = self._client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def list_mentions(self, brand: str | None = None) -> list[dict]:
        response = self._client.get("/mentions", params={"brand": brand})
        response.raise_for_status()
        return response.json()

    def create_mention(self, mention: dict) -> dict:
        response = self._client.post("/mentions", json=mention)
        if response.status_code == httpx.codes.CONFLICT:
            return {}
        response.raise_for_status()
        return response.json()

    def update_mention(
        self,
        mention_id: int,
        sentiment: str,
        topic: str,
        urgency: str,
    ) -> dict:
        response = self._client.patch(
            f"/mentions/{mention_id}",
            params={
                "sentiment": sentiment,
                "topic": topic,
                "urgency": urgency,
            },
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
