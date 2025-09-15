import sys, os
from fastmcp import FastMCP
import httpx, yaml

print("Starting MCP server...", file=sys.stderr)

SPEC_URL = os.getenv("SPEC_URL", "https://grch38.togovar.org/api/v1.yml")
client = httpx.AsyncClient(base_url="https://grch38.togovar.org/api")

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
