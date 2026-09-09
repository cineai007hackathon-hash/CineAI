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
                    "--from", "git+https://github.com/agentic-forge/mcp-weather.git",
                    "python", "-m", "forge_mcp_weather"
                ],
                # Alternative pure no-deps option:
                # command="uvx",
                # args=["--from", "git+https://github.com/microagents/mcp-servers.git#subdirectory=mcp-weather-free", "mcp-weather-free"],
            ),
            timeout=30,
        ),
        # Optional: only expose what you need
        # tool_filter=["get_current_weather", "get_forecast", "geocode"],
    )