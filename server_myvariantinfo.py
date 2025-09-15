import sys
from fastmcp import FastMCP
import httpx

print("Starting MCP server...", file=sys.stderr)
# Create an HTTP client for your API
client = httpx.AsyncClient(base_url="https://myvariant.info/v1")

# Load your OpenAPI spec 
openapi_spec = httpx.get("https://smart-api.info/api/metadata/09c8782d9f4027712e65b95424adba79?format=json").json()

# Create the MCP server
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="MyVariant.info Server"
)

if __name__ == "__main__":
    mcp.run()
