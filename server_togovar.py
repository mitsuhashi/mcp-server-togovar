#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import asyncio
from typing import Any, Dict, List

import httpx
import yaml
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from fastmcp import FastMCP


def log(*args: Any) -> None:
    print(*args, file=sys.stderr)


# ---------- 送信直前にクエリから pretty を完全除去するフック ----------
def _remove_pretty_query_param(request: httpx.Request) -> None:
    """
    /api/ 配下への全リクエストで、クエリの pretty パラメータを強制的に削除する。
    （FastMCP や上位が付けても送信直前に必ず消える）
    """
    try:
        # base_url を使っているので path 先頭は基本 / になる。/api/ のみに適用。
        if not request.url.path.startswith("/api/"):
            return

        parts = urlsplit(str(request.url))
        q = parse_qsl(parts.query, keep_blank_values=True)

        # pretty を除去
        new_q = [(k, v) for (k, v) in q if k != "pretty"]

        new_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(new_q, doseq=True), parts.fragment)
        )
        request.url = httpx.URL(new_url)
    except Exception as e:
        # フックで例外を投げない（ログだけ）
        log(f"[WARN] _remove_pretty_query_param failed: {e}")


# ---------- OpenAPI から Pretty を物理削除するユーティリティ ----------
def strip_pretty_parameter(openapi_spec: Dict[str, Any]) -> None:
    """
    components.parameters.Pretty を削除し、
    paths.*.*.parameters から Pretty の $ref を取り除く。
    """
    comps = openapi_spec.get("components", {})
    params = comps.get("parameters", {})
    if "Pretty" in params:
        params.pop("Pretty", None)

    paths = openapi_spec.get("paths", {}) or {}
    for path, node in paths.items():
        for method in list(node.keys()):
            op = node.get(method)
            if not isinstance(op, dict):
                continue
            if "parameters" in op and isinstance(op["parameters"], list):
                new_params: List[Any] = []
                for p in op["parameters"]:
                    if isinstance(p, dict) and p.get("$ref", "").endswith("/Pretty"):
                        # skip Pretty
                        continue
                    new_params.append(p)
                op["parameters"] = new_params


async def build_client(base_url: str) -> httpx.AsyncClient:
    """
    httpx.AsyncClient を生成。送信前フックで pretty を必ず除去する。
    """
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=15.0,
        follow_redirects=True,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        event_hooks={"request": [_remove_pretty_query_param]},
    )


def load_openapi(spec_url: str) -> Dict[str, Any]:
    """
    SPEC_URL から OpenAPI を取得して dict にロード。
    """
    log(f"Fetching OpenAPI: {spec_url}")
    resp = httpx.get(spec_url, timeout=30.0)
    resp.raise_for_status()
    spec = yaml.safe_load(resp.text)
    if not isinstance(spec, dict):
        raise ValueError("Loaded OpenAPI spec is not a mapping/dict.")
    return spec


def main() -> None:
    log("Starting MCP server...")

    SPEC_URL = os.getenv("SPEC_URL", "https://grch38.togovar.org/api/v1.yml")
    BASE_URL = os.getenv("BASE_URL", "https://grch38.togovar.org/api")

    # OpenAPI をロード
    openapi_spec = load_openapi(SPEC_URL)

    # Pretty を完全削除（components & paths）
    strip_pretty_parameter(openapi_spec)

    # httpx client を用意（送信直前にも pretty を除去）
    client = asyncio.run(build_client(BASE_URL))

    # FastMCP インスタンス作成
    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="TogoVar API Server",
    )

    # 実行（ブロッキング）
    mcp.run()


if __name__ == "__main__":
    main()
