import sys, os
from fastmcp import FastMCP
import httpx, yaml

def _fix_pretty(request: httpx.Request):
    # 対象パスのみ（任意）
    if not request.url.path.startswith("/api/"):
        return
    parts = urlsplit(str(request.url))
    q = parse_qsl(parts.query, keep_blank_values=True)
    new_q = []
    for k, v in q:
        if k == "pretty":
            continue
        else:
            new_q.append((k, v))
    new_url = urlunsplit((parts.scheme, parts.netloc, parts.path,
                        urlencode(new_q, doseq=True), parts.fragment))
    request.url = httpx.URL(new_url)

print("Starting MCP server...", file=sys.stderr)

SPEC_URL = os.getenv("SPEC_URL", "https://grch38.togovar.org/api/v1.yml")

client = httpx.AsyncClient(
    base_url="https://grch38.togovar.org/api",
    timeout=15.0,
    follow_redirects=True,
    headers={"Accept":"application/json","Content-Type":"application/json"},
    event_hooks={"request": [_fix_pretty]},
)

# YAML を取得して Python dict に
resp = httpx.get(SPEC_URL, timeout=30)
resp.raise_for_status()
openapi_spec = yaml.safe_load(resp.text)   # ← ここで参照解決はしない

# そのまま渡す（未解決の $ref を含んでいて OK）
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="TogoVar API Server"
)

if __name__ == "__main__":
    mcp.run()
