from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def is_retryable_http_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


def _extract_token(payload: Any) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if not isinstance(payload, dict):
        raise RuntimeError("HRworks authentication response did not contain a token")
    for key in ("token", "accessToken", "access_token", "bearerToken"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise RuntimeError("HRworks authentication response did not contain a token")


def _encode_query_value(
    value: str,
    safe: str = "",
    encoding: str | None = None,
    errors: str | None = None,
) -> str:
    """URL-encode query values but keep @ literal for HRworks person emails."""
    return quote(value, safe="@", encoding=encoding, errors=errors)


def build_working_times_query(
    *,
    begin_date: str,
    end_date: str,
    person_emails: list[str],
) -> str:
    pairs: list[tuple[str, str]] = [
        ("beginDate", begin_date),
        ("endDate", end_date),
        ("interval", "months"),
    ]
    pairs.extend(("persons", email) for email in person_emails)
    return urlencode(pairs, quote_via=_encode_query_value)


class HrworksClient:
    def __init__(
        self,
        base_url: str,
        access_key: str,
        secret_access_key: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_key = access_key.strip()
        self.secret_access_key = secret_access_key.strip()
        self._token: str | None = None
        self.client = httpx.Client(timeout=timeout_seconds, follow_redirects=True)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> HrworksClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(is_retryable_http_exception),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: list[tuple[str, str]] | None = None,
        auth: bool = True,
    ) -> Any:
        headers: dict[str, str] = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.authenticate()}"
        url = f"{self.base_url}{path}"
        if params:
            query = urlencode(params, quote_via=_encode_query_value)
            url = f"{url}?{query}"
            params = None
        response = self.client.request(method, url, headers=headers, json=json_body, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if is_retryable_http_exception(exc):
                raise
            raise RuntimeError(
                f"HRworks API request failed: {exc.response.status_code} {url}"
            ) from exc
        if not response.content:
            return None
        return response.json()

    def authenticate(self) -> str:
        if self._token:
            return self._token
        if not self.access_key or not self.secret_access_key:
            raise RuntimeError("HRworks credentials are not configured")
        payload = self._request(
            "POST",
            "/authentication",
            json_body={
                "accessKey": self.access_key,
                "secretAccessKey": self.secret_access_key,
            },
            auth=False,
        )
        self._token = _extract_token(payload)
        logger.info("HRworks authentication succeeded")
        return self._token

    def fetch_all_person_master_data(self, *, only_active: bool = False) -> list[dict[str, Any]]:
        persons: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self._request(
                "GET",
                "/persons/master-data",
                params=[
                    ("onlyActive", "true" if only_active else "false"),
                    ("page", str(page)),
                ],
            )
            if not isinstance(payload, dict):
                break
            batch = payload.get("persons")
            if not isinstance(batch, list) or not batch:
                break
            persons.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 50:
                break
            page += 1
        return persons

    def fetch_working_times(
        self,
        *,
        begin_date: str,
        end_date: str,
        person_emails: list[str],
    ) -> Any:
        if not person_emails:
            return []
        query = build_working_times_query(
            begin_date=begin_date,
            end_date=end_date,
            person_emails=person_emails,
        )
        return self._request("GET", f"/working-times?{query}")
