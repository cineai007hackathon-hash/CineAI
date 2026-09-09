"""Open-source Weather MCP (Open-Meteo – zero cost)."""

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def get_weather_mcp_toolset() -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uvx",
                args=[
                    "--from",
                    "git+https://github.com/agentic-forge/mcp-weather.git",
                    "python",
                    "-m",
                    "forge_mcp_weather",
                ],
            ),
            timeout=30,
        ),
    )
