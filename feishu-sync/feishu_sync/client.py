from __future__ import annotations

import json
import time
from typing import Any
from urllib import error, parse, request


API_BASE = "https://open.feishu.cn/open-apis"


class FeishuApiError(RuntimeError):
    pass


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, app_token: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self._tenant_access_token = ""
        self._token_expires_at = 0.0

    def _tenant_token(self) -> str:
        if self._tenant_access_token and time.time() < self._token_expires_at - 60:
            return self._tenant_access_token

        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        data = self._raw_request(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            payload,
            auth=False,
        )
        token = data.get("tenant_access_token")
        if not token:
            raise FeishuApiError("Feishu did not return tenant_access_token")
        self._tenant_access_token = token
        self._token_expires_at = time.time() + int(data.get("expire", 7200))
        return token

    def _raw_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        auth: bool = True,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{API_BASE}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"

        body = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth:
            headers["Authorization"] = f"Bearer {self._tenant_token()}"
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise FeishuApiError(
                f"Feishu request failed: {method} {path}: HTTP {exc.code} {exc.reason}: {error_body}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise FeishuApiError(f"Feishu request failed: {method} {path}: {exc}") from exc

        data = json.loads(raw) if raw else {}
        if data.get("code", 0) != 0:
            raise FeishuApiError(
                f"Feishu API error {data.get('code')}: {data.get('msg')} ({method} {path})"
            )
        return data

    def list_tables(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query: dict[str, Any] = {"page_size": 100}
            if page_token:
                query["page_token"] = page_token
            data = self._raw_request(
                "GET",
                f"/bitable/v1/apps/{self.app_token}/tables",
                query=query,
            )
            payload = data.get("data", {})
            items.extend(payload.get("items", []))
            if not payload.get("has_more"):
                return items
            page_token = payload.get("page_token", "")

    def create_table(self, name: str, first_field_name: str) -> dict[str, Any]:
        data = self._raw_request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables",
            {
                "table": {
                    "name": name,
                    "default_view_name": "表格",
                    "fields": [{"field_name": first_field_name, "type": 1}],
                }
            },
        )
        payload = data.get("data", {})
        return payload.get("table", payload)

    def delete_table(self, table_id: str) -> None:
        self._raw_request(
            "DELETE",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}",
        )

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query: dict[str, Any] = {"page_size": 100}
            if page_token:
                query["page_token"] = page_token
            data = self._raw_request(
                "GET",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields",
                query=query,
            )
            payload = data.get("data", {})
            items.extend(payload.get("items", []))
            if not payload.get("has_more"):
                return items
            page_token = payload.get("page_token", "")

    def create_field(self, table_id: str, field_name: str, field_type: int) -> dict[str, Any]:
        data = self._raw_request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields",
            {"field_name": field_name, "type": field_type},
        )
        return data.get("data", {}).get("field", {})

    def update_field(self, table_id: str, field_id: str, field_name: str, field_type: int) -> dict[str, Any]:
        data = self._raw_request(
            "PUT",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields/{field_id}",
            {"field_name": field_name, "type": field_type},
        )
        return data.get("data", {}).get("field", {})

    def delete_field(self, table_id: str, field_id: str) -> None:
        self._raw_request(
            "DELETE",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields/{field_id}",
        )

    def list_views(self, table_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query: dict[str, Any] = {"page_size": 100}
            if page_token:
                query["page_token"] = page_token
            data = self._raw_request(
                "GET",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/views",
                query=query,
            )
            payload = data.get("data", {})
            items.extend(payload.get("items", []))
            if not payload.get("has_more"):
                return items
            page_token = payload.get("page_token", "")

    def create_view(self, table_id: str, view_name: str, view_type: str) -> dict[str, Any]:
        data = self._raw_request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/views",
            {"view_name": view_name, "view_type": view_type},
        )
        return data.get("data", {}).get("view", {})

    def delete_view(self, table_id: str, view_id: str) -> None:
        self._raw_request(
            "DELETE",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/views/{view_id}",
        )

    def batch_create_records(self, table_id: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []
        created: list[dict[str, Any]] = []
        for index in range(0, len(records), 500):
            chunk = records[index : index + 500]
            data = self._raw_request(
                "POST",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/batch_create",
                {"records": chunk},
            )
            created.extend(data.get("data", {}).get("records", []))
        return created

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        data = self._raw_request(
            "PUT",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}",
            {"fields": fields},
        )
        return data.get("data", {}).get("record", {})

    def delete_record(self, table_id: str, record_id: str) -> None:
        self._raw_request(
            "DELETE",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}",
        )

    def search_records(
        self,
        table_id: str,
        *,
        field_names: list[str] | None = None,
        filter_condition: dict[str, Any] | None = None,
        page_size: int = 500,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"page_size": page_size}
        if field_names:
            body["field_names"] = field_names
        if filter_condition:
            body["filter"] = filter_condition

        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query = {"page_token": page_token} if page_token else None
            data = self._raw_request(
                "POST",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/search",
                body,
                query=query,
            )
            payload = data.get("data", {})
            items.extend(payload.get("items", []))
            if not payload.get("has_more"):
                return items
            page_token = payload.get("page_token", "")
