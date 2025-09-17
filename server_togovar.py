import sys
from fastmcp import FastMCP
import httpx

print("Starting MCP server...", file=sys.stderr)
# Create an HTTP client for your API
client = httpx.AsyncClient(base_url="https://grch38.togovar.org/api")

# Load your OpenAPI spec 
openapi_spec = httpx.get("https://raw.githubusercontent.com/mitsuhashi/mcp-server-togovar/refs/heads/main/togovar_api.json").json()

# Create the MCP server
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="TogoVar API Server"
)

if __name__ == "__main__":
    mcp.run()
