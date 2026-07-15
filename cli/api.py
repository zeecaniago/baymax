from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


DEFAULT_API_URL = "http://127.0.0.1:8000"


class BaymaxApiError(RuntimeError):
    """Raised when the CLI cannot complete an API request."""


class BaymaxApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        configured_url = base_url or os.environ.get("BAYMAX_API_URL") or DEFAULT_API_URL
        self.base_url = configured_url.rstrip("/")
        self.timeout = timeout

    def parse_expense(self, raw_text: str) -> dict[str, Any]:
        return self._post_json("/expenses/parse", {"raw_text": raw_text})

    def create_expense(
        self,
        *,
        amount: float,
        description: str,
        category: str | None = None,
        flags: list[str] | None = None,
        goals: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "amount": amount,
            "description": description,
            "category": category,
            "flags": flags or [],
            "goals": goals or [],
            "notes": notes,
        }
        return self._post_json("/expenses", payload)

    def update_expense(
        self,
        expense_id: str,
        *,
        amount: float | None = None,
        description: str | None = None,
        category: str | None = None,
        flags: list[str] | None = None,
        goals: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "amount": amount,
            "description": description,
            "category": category,
            "flags": flags,
            "goals": goals,
            "notes": notes,
        }
        updates = {key: value for key, value in payload.items() if value is not None}
        return self._request_json("PATCH", f"/expenses/{expense_id}", updates)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", path, payload)

    def _request_json(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = self._extract_error_detail(exc)
            raise BaymaxApiError(f"Baymax API error ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise BaymaxApiError(
                f"Couldn't reach Baymax API at {self.base_url}. Start the server and retry."
            ) from exc

        if not response_body:
            return {}
        return json.loads(response_body)

    def _extract_error_detail(self, exc: error.HTTPError) -> str:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            return exc.reason or "Unknown error"

        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        return json.dumps(payload)
