"""MCP smoke test: starts app/mcp/server.py over stdio and calls every tool."""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


async def main():
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(ROOT, "app/mcp/server.py")], cwd="/tmp")
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tools:", [t.name for t in tools.tools])
            for name, args in [("search_drawings", {"query": "3 bedrooms and a sauna", "limit": 2}),
                               ("ask_drawing", {"drawing_id": "swiss_dwellings~site3634_bldg5596_floor24203", "question": "Wie viele Wohnungen sind auf diesem Grundriss dargestellt?"}),
                               ("get_drawing_context", {"drawing_id": "finna~hka.139879309684900_166878548098200"})]:
                res = await s.call_tool(name, args)
                txt = res.content[0].text if res.content else str(res.structured_content)
                print(f"== {name}: {txt[:400]}")

asyncio.run(main())
