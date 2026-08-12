"""
File system tools — read, write, and list local files and directories for Boss.
"""

import os
from pathlib import Path


def register(mcp):

    @mcp.tool()
    def read_file(path: str) -> str:
        """
        Read the contents of a text file on the local host machine.
        Use this when Boss asks to read, inspect, or check a local file.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return f"File does not exist: {path}"
            if not file_path.is_file():
                return f"Path is a directory, not a file: {path}"
            
            content = file_path.read_text(encoding="utf-8", errors="replace")
            # Limit returned content size to avoid overwhelming voice LLM context
            if len(content) > 4000:
                return content[:4000] + f"\n\n...[Truncated: Total length {len(content)} characters]"
            return content
        except Exception as e:
            return f"Error reading file {path}: {str(e)}"

    @mcp.tool()
    def write_file(path: str, content: str) -> str:
        """
        Write or overwrite a text file on the local host machine.
        Use this when Boss asks to create, write, or save content to a local file.
        """
        try:
            file_path = Path(path).expanduser().resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to {file_path.name}, Boss."
        except Exception as e:
            return f"Error writing file {path}: {str(e)}"

    @mcp.tool()
    def list_directory(path: str = ".") -> str:
        """
        List files and folders in a local directory.
        Use this when Boss asks to view or list files in a folder.
        """
        try:
            dir_path = Path(path).expanduser().resolve()
            if not dir_path.exists():
                return f"Directory does not exist: {path}"
            if not dir_path.is_dir():
                return f"Path is not a directory: {path}"
            
            entries = []
            for entry in dir_path.iterdir():
                kind = "DIR " if entry.is_dir() else "FILE"
                entries.append(f"[{kind}] {entry.name}")
            
            if not entries:
                return f"Directory {dir_path.name} is empty, Boss."
            
            return f"Contents of {dir_path.name}:\n" + "\n".join(entries[:30])
        except Exception as e:
            return f"Error listing directory {path}: {str(e)}"
