import asyncio


def test_content_part_completion_is_translated_for_parser():
    try:
        from scripts.sam_spike import stream_events
    except ModuleNotFoundError:
        assert False, "SAM event translation is not implemented yet"

    async def events():
        yield {
            "type": "response.content_part.done",
            "item_id": "item",
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "example"},
        }

    async def collect():
        return [event async for event in stream_events(events())]

    result = asyncio.run(collect())

    assert result[-1]["type"] == "response.output_text.done"
    assert result[-1]["text"] == "example"
