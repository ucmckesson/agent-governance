from __future__ import annotations

from google.adk.tools.function_tool import FunctionTool


def web_lookup(query: str) -> dict:
    """Mock web lookup for research queries."""
    data = {
        "capital of france": "Paris",
        "gdp of japan": "Japan GDP (2023) ~ $4.2T",
    }
    key = query.lower()
    if "france" in key:
        result = "Paris"
    elif "japan" in key and "gdp" in key:
        result = "Japan GDP (2023) ~ $4.2T"
    else:
        result = data.get(key, f"Mocked lookup result for: {query}")
    return {"query": query, "result": result}


class WebLookupTool(FunctionTool):
    def __init__(self) -> None:
        super().__init__(func=web_lookup)
