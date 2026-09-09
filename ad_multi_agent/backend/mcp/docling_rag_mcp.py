"""IBM Docling MCP (document understanding) + optional watsonx.data Document Library Retrieval."""
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams, StreamableHTTPConnectionParams
from mcp import StdioServerParameters
import os

def get_docling_mcp_toolset() -> McpToolset:
    """Primary: open-source Docling MCP (local or remote Docling Serve)."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uvx",
                args=["--from", "docling-mcp", "docling-mcp-server"],
                env={
                    # Optional: point to a remote Docling Serve or IBM managed Docling
                    # "DOCLING_SERVICE_URL": "https://your-docling-serve.example.com",
                    # "DOCLING_CONVERSION_MODE": "remote",
                    # "DOCLING_FALLBACK_TO_LOCAL": "true",
                },
            ),
            timeout=60,
        ),
        # Useful tools for screenplay / production docs:
        # tool_filter=[
        #     "convert_document_into_docling_document",
        #     "export_docling_document_to_markdown",
        #     "search_documents",               # if llama-index-rag enabled
        #     "insert_document_to_vectordb",
        # ],
    )


def get_watsonx_dl_retrieval_mcp() -> McpToolset | None:
    """Optional managed RAG over watsonx.data Document Libraries (requires credentials)."""
    if not os.getenv("WATSONX_DATA_API_KEY"):
        return None

    # Local stdio version
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=["run", "ibm-watsonxdata-dl-retrieval-mcp-server", "--transport", "stdio"],
                env={
                    "WATSONX_DATA_API_KEY": os.getenv("WATSONX_DATA_API_KEY"),
                    "WATSONX_DATA_RETRIEVAL_ENDPOINT": os.getenv("WATSONX_DATA_RETRIEVAL_ENDPOINT"),
                    "DOCUMENT_LIBRARY_API_ENDPOINT": os.getenv("DOCUMENT_LIBRARY_API_ENDPOINT"),
                    "WATSONX_DATA_TOKEN_GENERATION_ENDPOINT": os.getenv("WATSONX_DATA_TOKEN_GENERATION_ENDPOINT", "https://iam.cloud.ibm.com"),
                    "LH_CONTEXT": "SAAS",
                },
            ),
            timeout=45,
        ),
    )