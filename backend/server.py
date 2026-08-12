"""
Miss Minutes MCP Server — Entry Point
Run with: python server.py
"""

from mcp.server.fastmcp import FastMCP
from tools import register_all_tools
from prompts import register_all_prompts
from resources import register_all_resources
from config import config

# ---------------------------------------------------------------------------
# Server Setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name=config.SERVER_NAME,
    instructions=(
        "You are a professional executive voice assistant serving Boss. "
        "You have access to web search, news feeds, and system tools to execute tasks quickly. "
        "Always address the user as Boss, and maintain a concise, respectful, professional tone."
    ),
)

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register_all_tools(mcp)
register_all_prompts(mcp)
register_all_resources(mcp)

def main():
    mcp.run(transport='sse')

if __name__ == "__main__":
    main()