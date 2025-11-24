"""
Minimal Capability Pack (MCP) tools for AI clients.

The tools mirror Flask helpers so that an LLM or tooling agent can search QQ Music
or resolve playback URLs without hitting HTTP endpoints directly.
"""

import json
from pathlib import Path
from typing import Annotated, Dict, List

from fastmcp.server.server import FastMCP
from pydantic import Field

import qqmusic_service
from qqmusic_service import build_main_client, build_service_client

__all__ = ["build_manifest", "manifest", "search_music_by_lyrics", "get_music_url_by_songmid"]

MANIFEST_NAME = "qqmusic_mcp"
MANIFEST_VERSION = "1.0"
MANIFEST_DESCRIPTION = (
    "Defines MCP tools that allow AI clients to search QQ Music and resolve playback URLs."
)

manifest = FastMCP(name=MANIFEST_NAME, instructions=MANIFEST_DESCRIPTION)


def _replace_http_with_https(data):
    if isinstance(data, dict):
        return {k: _replace_http_with_https(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_replace_http_with_https(item) for item in data]
    if isinstance(data, str):
        return data.replace("http://", "https://")
    return data


@manifest.tool(description="Search QQ Music by lyric keywords and return normalized song metadata.")
async def search_music_by_lyrics(
    lyrics: Annotated[str, Field(description="Lyrics fragment or song title to search for.")],
    page: Annotated[int, Field(description="Result page number (1-indexed).")] = 1,
    limit: Annotated[int, Field(description="Maximum number of songs to return.")] = 5,
) -> List[Dict]:
    if not lyrics:
        raise ValueError("lyrics is required for search_music_by_lyrics")

    page = max(page, 1)
    limit = max(limit, 1)
    qqm = build_main_client()
    raw_songs = await qqm.search_music(lyrics, page, limit)
    normalized = []

    for song in raw_songs[:limit]:
        singers = song.get("singer") or []
        singer_name = ""
        if singers and isinstance(singers, list):
            first = singers[0]
            singer_name = first.get("name", "") if isinstance(first, dict) else ""
        normalized.append(
            {
                "songname": song.get("songname", "").replace('"', ""),
                "singer": singer_name.replace('"', ""),
                "albumname": song.get("albumname", ""),
                "duration": f"{song.get('interval', 0) // 60}:{song.get('interval', 0) % 60:02d}",
                "songmid": song.get("songmid", ""),
                "songid": song.get("songid", ""),
                "albummid": song.get("albummid", ""),
            }
        )

    return _replace_http_with_https(normalized)

@manifest.tool(description="Retrieve a playback URL for a given QQ Music songmid and quality.")
async def get_music_url_by_songmid(
    songmid: Annotated[str, Field(description="QQ Music songmid identifier.")],
    file_type: Annotated[
        str,
        Field(
            description=(
                "Desired audio quality code; available options: 'm4a', '128', "
                "'320', 'flac' (default: '128')."
            )
        ),
    ] = "128",
) -> Dict:
    if not songmid:
        raise ValueError("songmid is required for get_music_url_by_songmid")

    qqmusic = build_service_client()
    result = await qqmusic.get_music_url(songmid, file_type)

    if not result:
        raise LookupError(f"No URL available for {songmid} @ {file_type}")

    return {"songmid": songmid, "file_type": file_type, **result}


def build_manifest(manifest_path: Path | str = "qqmusic_mcp_manifest.json") -> None:
    tools = manifest._tool_manager.list_tools()
    manifest_content = {
        "name": MANIFEST_NAME,
        "version": MANIFEST_VERSION,
        "description": MANIFEST_DESCRIPTION,
        "tools": [
            {
                "id": tool.name,
                "module": tool.fn.__module__,
                "function": tool.fn.__name__,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in tools
        ],
    }

    path = Path(manifest_path)
    path.write_text(json.dumps(manifest_content, ensure_ascii=False, indent=2))


def main() -> None:
    manifest.run()


if __name__ == "__main__":
    main()
