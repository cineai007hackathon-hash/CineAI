"""Open-source Location / Geocoding MCP (OpenStreetMap Nominatim)."""
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

def get_location_mcp_toolset() -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uvx",
                args=["geocode-mcp"],  # or "mcp-geo" from webcoderz/MCP-Geo
            ),
            timeout=20,
        ),
        # tool_filter=["mcp_geocoding_get_coordinates", "geocode_location", "reverse_geocode"],
    )