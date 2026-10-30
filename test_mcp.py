
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).resolve().parent

EXPECTED_TOOLS = {
    "search_cricket_logs",
    "ask_cricket_question",
    "get_cricket_statistics",
}


def parse_tool_response(result, test_name):
    """Check whether an MCP tool call returned an error."""
    if result.isError:
        raise AssertionError(f"{test_name}: MCP tool reported an error")

    text_parts = [
        content.text
        for content in result.content
        if hasattr(content, "text")
    ]

    if not text_parts:
        raise AssertionError(f"{test_name}: Tool returned no text content")

    return "\n".join(text_parts)


async def main():
    results = []

    def record_pass(name):
        results.append((name, True))
        print(f"PASS: {name}")

    def record_fail(name, error):
        results.append((name, False))
        print(f"FAIL: {name} - {error}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=os.environ.copy(),
        cwd=str(PROJECT_ROOT),
    )

    print("Connecting to Cricket MCP Server...")

    try:
        async with stdio_client(server_params) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream, write_stream
            ) as session:
                await session.initialize()
                print("MCP connection initialized successfully!")

                # Test 1: Discover the expected tools.
                try:
                    tools_result = await session.list_tools()
                    actual_tools = {
                        tool.name for tool in tools_result.tools
                    }

                    missing_tools = EXPECTED_TOOLS - actual_tools

                    if missing_tools:
                        raise AssertionError(
                            f"Missing tools: {sorted(missing_tools)}"
                        )

                    record_pass("Discover all expected MCP tools")
                except Exception as exc:
                    record_fail("Discover all expected MCP tools", exc)

                # Test 2: Search cricket logs.
                try:
                    search_result = await session.call_tool(
                        "search_cricket_logs",
                        arguments={
                            "event": "LBW given",
                            "limit": 5,
                        },
                    )
                    search_text = parse_tool_response(
                        search_result, "Search cricket logs"
                    )

                    print("\nSearch response preview:")
                    print(search_text[:500])

                    record_pass("Search cricket logs returns a response")
                except Exception as exc:
                    record_fail("Search cricket logs returns a response", exc)

                # Test 3: Ask a RAG question.
                try:
                    chat_result = await session.call_tool(
                        "ask_cricket_question",
                        arguments={
                            "question": (
                                "What information is available about "
                                "players given out LBW?"
                            )
                        },
                    )
                    chat_text = parse_tool_response(
                        chat_result, "RAG question answering"
                    )

                    print("\nRAG response preview:")
                    print(chat_text[:500])

                    record_pass("RAG question returns a response")
                except Exception as exc:
                    record_fail("RAG question returns a response", exc)

                # Test 4: Retrieve collection statistics.
                try:
                    stats_result = await session.call_tool(
                        "get_cricket_statistics",
                        arguments={},
                    )
                    stats_text = parse_tool_response(
                        stats_result, "Collection statistics"
                    )

                    stats_data = json.loads(stats_text)

                    if stats_data.get("collection") != "cricket_logs":
                        raise AssertionError(
                            "Unexpected Qdrant collection name"
                        )

                    if not isinstance(stats_data.get("total_records"), int):
                        raise AssertionError(
                            "total_records is missing or not an integer"
                        )

                    print("\nCollection statistics:")
                    print(json.dumps(stats_data, indent=2))

                    record_pass("Collection statistics are valid")
                except Exception as exc:
                    record_fail("Collection statistics are valid", exc)

    except Exception as exc:
        record_fail("MCP connection and initialization", exc)

    print("\n" + "=" * 50)
    print("MCP TEST SUMMARY")
    print("=" * 50)

    for name, passed in results:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")

    passed_count = sum(passed for _, passed in results)
    failed_count = len(results) - passed_count

    print(f"\nPassed: {passed_count}")
    print(f"Failed: {failed_count}")

    if failed_count:
        raise SystemExit(1)

    print("All MCP checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
