#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from typing import Any, Dict, List

import httpx
import yaml
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from fastmcp import FastMCP


def log(*args: Any) -> None:
    print(*args, file=sys.stderr)


# --- 送信直前に pretty を確実に削除（同期 httpx 用） ---
def remove_pretty_query_param(request: httpx.Request) -> None:
    try:
        if not request.url.path.startswith("/api/"):
            return
        parts = urlsplit(str(request.url))
        q = parse_qsl(parts.query, keep_blank_values=True)
        new_q = [(k, v) for (k, v) in q if k != "pretty"]
        new_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(new_q, doseq=True), parts.fragment)
        )
        request.url = httpx.URL(new_url)
    except Exception as e:
        log(f"[WARN] remove_pretty_query_param failed: {e}")


def strip_pretty_parameter(openapi_spec: Dict[str, Any]) -> None:
    # components.parameters.Pretty を削除
    comps = openapi_spec.get("components", {})
    params = comps.get("parameters", {})
    if "Pretty" in params:
        params.pop("Pretty", None)
    # 各 operation の parameters から Pretty の $ref を除去
    paths = openapi_spec.get("paths", {}) or {}
    for path, node in paths.items():
        for method, op in (node or {}).items():
            if not isinstance(op, dict):
                continue
            if "parameters" in op and isinstance(op["parameters"], list):
                op["parameters"] = [
                    p for p in op["parameters"]
                    if not (isinstance(p, dict) and p.get("$ref", "").endswith("/Pretty"))
                ]


MINIMAL_EMBEDDED_SPEC = """
openapi: 3.0.3
info:
  title: TogoVar API (minimal)
  version: "0.0.1"
servers:
  - url: https://grch38.togovar.org/api
paths:
  /search/gene:
    get:
      parameters:
        - in: query
          name: term
          required: true
          schema:
            type: string
      responses:
        '200':
          description: OK
          content: { application/json: { schema: { type: array, items: { type: object } } } }
  /search/variant:
    post:
      requestBody:
        required: true
        content:
          application/json: { schema: { type: object } }
      responses:
        '200':
          description: OK
          content: { application/json: { schema: { type: object } } }
"""


def load_openapi_with_fallback(spec_url: str) -> Dict[str, Any]:
    # 1) 環境変数で指定があれば取りに行く（失敗しても落とさない）
    if spec_url:
        try:
            log(f"[BOOT] Fetching OpenAPI from {spec_url}")
            r = httpx.get(spec_url, timeout=15.0)
            r.raise_for_status()
            return yaml.safe_load(r.text)
        except Exception as e:
            log(f"[WARN] Failed to fetch SPEC_URL: {e}")
    # 2) 同梱ファイルにフォールバック
    local_path = os.getenv("LOCAL_SPEC_PATH", "api_v1.yml")
    if os.path.exists(local_path):
        try:
            log(f"[BOOT] Loading OpenAPI from local file: {local_path}")
            with open(local_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f.read())
        except Exception as e:
            log(f"[WARN] Failed to load local spec {local_path}: {e}")
    # 3) 最小埋め込み
    log("[BOOT] Falling back to embedded minimal OpenAPI spec.")
    return yaml.safe_load(MINIMAL_EMBEDDED_SPEC)


def main() -> None:
    try:
        log("[BOOT] Starting MCP server...")

        SPEC_URL = os.getenv("SPEC_URL", "https://grch38.togovar.org/api/v1.yml")
        BASE_URL = os.getenv("BASE_URL", "https://grch38.togovar.org/api")

        # OpenAPI ロード（外部→ローカル→埋め込みの順でフォールバック）
        openapi_spec = load_openapi_with_fallback(SPEC_URL)

        # Pretty を spec から物理削除
        strip_pretty_parameter(openapi_spec)

        # 同期クライアントで生成（送信直前に pretty を除去）
        client = httpx.Client(
            base_url=BASE_URL,
            timeout=15.0,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            event_hooks={"request": [remove_pretty_query_param]},
        )

        # FastMCP インスタンス
        mcp = FastMCP.from_openapi(
            openapi_spec=openapi_spec,
            client=client,
            name="TogoVar API Server",
        )

        log("[BOOT] FastMCP created. Running...")
        mcp.run()  # ブロッキング

    except Exception as e:
        # 起動失敗の理由を必ずログに出す（pre-flight で見える）
        log("[FATAL] MCP server failed to start:", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
