"""
MCP Prompts — reusable prompt templates exposed to the client.
"""

from prompts import templates


def register_all_prompts(mcp):
    templates.register(mcp)
