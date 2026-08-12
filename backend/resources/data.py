"""
Data resources — expose static content or dynamic data via MCP resources.
"""


def register(mcp):

    @mcp.resource("missminutes://info")
    def server_info() -> str:
        """Returns basic info about this MCP server."""
        return (
            "Miss Minutes MCP Server\n"
            "A TVA-inspired AI assistant.\n"
            "Built with FastMCP."
        )
