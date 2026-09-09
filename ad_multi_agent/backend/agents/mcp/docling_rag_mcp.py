"""IBM Docling MCP (document understanding) + optional watsonx Document Library Retrieval."""

from __future__ import annotations

import os

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def get_docling_mcp_toolset() -> McpToolset:
    """Primary: open-source Docling MCP (local or remote Docling Serve)."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uvx",
                args=["--from", "docling-mcp", "docling-mcp-server"],
                env={},
            ),
            timeout=60,
        ),
    )


def get_watsonx_dl_retrieval_mcp() -> McpToolset | None:
    """Optional managed RAG over watsonx.data Document Libraries."""
    if not os.getenv("WATSONX_DATA_API_KEY"):
        return None

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=["run", "ibm-watsonxdata-dl-retrieval-mcp-server", "--transport", "stdio"],
                env={
                    "WATSONX_DATA_API_KEY": os.getenv("WATSONX_DATA_API_KEY"),
                    "WATSONX_DATA_RETRIEVAL_ENDPOINT": os.getenv("WATSONX_DATA_RETRIEVAL_ENDPOINT"),
                    "DOCUMENT_LIBRARY_API_ENDPOINT": os.getenv("DOCUMENT_LIBRARY_API_ENDPOINT"),
                    "WATSONX_DATA_TOKEN_GENERATION_ENDPOINT": os.getenv(
                        "WATSONX_DATA_TOKEN_GENERATION_ENDPOINT",
                        "https://iam.cloud.ibm.com",
                    ),
                    "LH_CONTEXT": "SAAS",
                },
            ),
            timeout=45,
        ),
    )
