"""
MCP tools for file search, file metadata, UPnP discovery, and playback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

import aiohttp
import httpx
import jieba
from dotenv import load_dotenv
from fastmcp.server.server import FastMCP
from pydantic import BaseModel, Field

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.search import async_search

__all__ = [
    "build_manifest",
    "manifest",
    "search_files",
    "get_file_info",
    "search_upnp_clients",
    "play_file",
]

MANIFEST_NAME = "file_upnp_mcp"
MANIFEST_VERSION = "1.0"
MANIFEST_DESCRIPTION = (
    "MCP tools for searching files, fetching file metadata, discovering UPnP clients, "
    "and playing media via UPnP/DLNA."
)

load_dotenv()

API_BASE = os.getenv("XZM_API_BASE")
API_LOGIN = "/api/auth/login"
API_SEARCH = "/api/fs/search"
API_GET = "/api/fs/get"

DEFAULT_USERNAME = os.getenv("XZM_USERNAME")
DEFAULT_PASSWORD = os.getenv("XZM_PASSWORD")
RUNTIME_DIR = Path.home() / ".xiaozhi_mcp_music"
TOKEN_PATH = RUNTIME_DIR / "token.json"
LOG_PATH = RUNTIME_DIR / "api.log"

if not API_BASE:
    raise RuntimeError("XZM_API_BASE must be set (export an env var or add it to .env)")
if not DEFAULT_USERNAME or not DEFAULT_PASSWORD:
    raise RuntimeError("XZM_USERNAME and XZM_PASSWORD must be set (export env vars or add to .env)")

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("XZM_API")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_PATH)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

class SearchItem(BaseModel):
    parent: str = Field(description="Parent directory path.")
    name: str = Field(description="File or directory name.")
    is_dir: bool = Field(description="Whether the item is a directory.")
    size: int = Field(description="Size in bytes (0 for directories when unknown).")
    type: int = Field(description="Type code from API response.")


class FileInfo(BaseModel):
    id: str = Field(description="File identifier.")
    path: str = Field(description="Full path of the file.")
    name: str = Field(description="File name.")
    size: int = Field(description="File size in bytes.")
    is_dir: bool = Field(description="Whether the item is a directory.")
    modified: str = Field(description="Modified timestamp.")
    created: str = Field(description="Created timestamp.")
    sign: str = Field(description="Signature token used by the backend.")
    thumb: str = Field(description="Thumbnail URL, if any.")
    type: int = Field(description="Type code from API response.")
    raw_url: str = Field(description="Playable raw URL for the file.")
    provider: str = Field(description="Provider name (e.g. Quark).")


class UpnpClientInfo(BaseModel):
    name: str = Field(description="Friendly name of the UPnP device.")
    location: str = Field(description="Device description URL.")
    udn: str = Field(description="Unique device name (UDN).")
    st: str = Field(description="Search target (ST) reported by SSDP.")

manifest = FastMCP(name=MANIFEST_NAME, instructions=MANIFEST_DESCRIPTION)


def _read_token() -> Optional[str]:
    if not TOKEN_PATH.exists():
        return None
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except json.JSONDecodeError:
        return None
    token = data.get("token") if isinstance(data, dict) else None
    return token if token else None


def _save_token(token: str) -> None:
    TOKEN_PATH.write_text(json.dumps({"token": token}, ensure_ascii=False))
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        # Best effort: chmod may fail on some platforms.
        pass


def _segment_keywords(keywords: str) -> List[str]:
    if not keywords:
        return []
    terms = [term.strip() for term in jieba.lcut(keywords) if term.strip()]
    return terms if terms else [keywords]


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_mapping(data: Dict[str, Any]) -> Dict[str, Any]:
    sensitive = {"password", "token", "authorization"}
    redacted = {}
    for key, value in data.items():
        if key.lower() in sensitive:
            redacted[key] = "***"
        else:
            redacted[key] = _redact_value(value)
    return redacted


async def _login(client: httpx.AsyncClient) -> str:
    payload = {"username": DEFAULT_USERNAME, "password": DEFAULT_PASSWORD}
    logger.info("POST %s%s payload=%s", API_BASE, API_LOGIN, _redact_mapping(payload))
    response = await client.post(API_LOGIN, json=payload)
    logger.info("RESP %s%s status=%s", API_BASE, API_LOGIN, response.status_code)
    response.raise_for_status()
    data = response.json()
    logger.info("RESP %s%s body=%s", API_BASE, API_LOGIN, _redact_value(data))
    if data.get("code") != 200:
        message = data.get("message", "login failed")
        raise RuntimeError(f"login failed: {message}")
    token = data.get("data", {}).get("token")
    if not token:
        raise RuntimeError("login failed: token missing")
    _save_token(token)
    return token


async def _authorized_post(client: httpx.AsyncClient, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    token = _read_token()
    if not token:
        token = await _login(client)
    headers = {"Authorization": token, "Content-Type": "application/json"}
    logger.info("POST %s%s headers=%s payload=%s", API_BASE, endpoint, _redact_mapping(headers), _redact_value(payload))
    response = await client.post(endpoint, json=payload, headers=headers)
    logger.info("RESP %s%s status=%s", API_BASE, endpoint, response.status_code)
    response.raise_for_status()
    data = response.json()
    logger.info("RESP %s%s body=%s", API_BASE, endpoint, _redact_value(data))
    if data.get("code") == 401:
        token = await _login(client)
        headers["Authorization"] = token
        logger.info("POST %s%s headers=%s payload=%s", API_BASE, endpoint, _redact_mapping(headers), _redact_value(payload))
        response = await client.post(endpoint, json=payload, headers=headers)
        logger.info("RESP %s%s status=%s", API_BASE, endpoint, response.status_code)
        response.raise_for_status()
        data = response.json()
        logger.info("RESP %s%s body=%s", API_BASE, endpoint, _redact_value(data))
    return data


def _join_path(parent: str, name: str) -> str:
    if not parent or parent == "/":
        return f"/{name.lstrip('/')}" if name else parent
    return f"{parent.rstrip('/')}/{name.lstrip('/')}"


@manifest.tool(description="Search files by keywords and return items.")
async def search_files(
    keywords: Annotated[str, Field(description="Search keywords; will be segmented with jieba.")],
    parent: Annotated[str, Field(description="Parent directory path.")] = "/",
    scope: Annotated[int, Field(description="Search scope (0 for current, 1 for recursive).")]=0,
    page: Annotated[int, Field(description="Page number (1-indexed).")]=1,
    per_page: Annotated[int, Field(description="Results per page.")] = 30,
) -> List[Dict[str, Any]]:
    if not keywords:
        raise ValueError("keywords is required for search_files")
    terms = _segment_keywords(keywords)
    payload = {
        "parent": parent,
        "keywords": "",
        "scope": scope,
        "page": max(page, 1),
        "per_page": max(per_page, 1),
    }

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        data = {}
        for idx in range(len(terms), 0, -1):
            payload["keywords"] = " ".join(terms[:idx])
            data = await _authorized_post(client, API_SEARCH, payload)
            if data.get("code") != 200:
                message = data.get("message", "search failed")
                raise RuntimeError(f"search failed: {message}")
            content = data.get("data", {}).get("content", [])
            if content:
                break

    content = data.get("data", {}).get("content", [])
    results = []
    for item in content:
        try:
            results.append(SearchItem(**item).dict())
        except Exception:
            results.append(item)
    return results


@manifest.tool(description="Get file metadata by path (or parent + name).")
async def get_file_info(
    path: Annotated[str, Field(description="Full file path.")] = "",
    parent: Annotated[str, Field(description="Parent directory path.")] = "",
    name: Annotated[str, Field(description="File name.")] = "",
    password: Annotated[str, Field(description="Password for protected items.")] = "",
) -> Dict[str, Any]:
    resolved_path = path or _join_path(parent, name)
    if not resolved_path:
        raise ValueError("path or parent+name is required for get_file_info")

    payload = {"path": resolved_path, "password": password}
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        data = await _authorized_post(client, API_GET, payload)

    if data.get("code") != 200:
        message = data.get("message", "get file info failed")
        raise RuntimeError(f"get file info failed: {message}")

    raw_info = data.get("data") or {}
    raw_info.setdefault("path", resolved_path)
    try:
        return FileInfo(**raw_info).dict()
    except Exception:
        return raw_info


@manifest.tool(description="Discover UPnP clients on the local network.")
async def search_upnp_clients(
    timeout: Annotated[int, Field(description="Discovery timeout in seconds.")] = 5,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    session = aiohttp.ClientSession()
    requester = AiohttpSessionRequester(session)
    factory = UpnpFactory(requester)

    try:
        async def _on_response(response) -> None:
            location = response.get("location")
            if not location:
                return
            name = ""
            udn = ""
            try:
                device = await factory.async_create_device(location)
                name = getattr(device, "friendly_name", "") or ""
                udn = getattr(device, "udn", "") or ""
            except Exception:
                # Best effort: include device location even if fetch fails.
                pass
            try:
                results.append(
                    UpnpClientInfo(
                        name=name or "Unknown Device",
                        location=location,
                        udn=udn,
                        st=response.get("st", ""),
                    ).dict()
                )
            except Exception:
                results.append(
                    {
                        "name": name or "Unknown Device",
                        "location": location,
                        "udn": udn,
                        "st": response.get("st", ""),
                    }
                )

        await async_search(_on_response, timeout=timeout, loop=asyncio.get_running_loop())
    finally:
        await session.close()

    return results


@manifest.tool(description="Play a media URL on a UPnP/DLNA client.")
async def play_file(
    url: Annotated[str, Field(description="Playable media URL.")],
    device_location: Annotated[str, Field(description="UPnP device description URL.")] = "",
    device_index: Annotated[int, Field(description="Index from search_upnp_clients results.")] = 0,
) -> Dict[str, Any]:
    if not url:
        raise ValueError("url is required for play_file")

    target_location = device_location
    if not target_location:
        clients = await search_upnp_clients()
        if not clients:
            raise RuntimeError("no UPnP clients found")
        idx = max(device_index, 0)
        if idx >= len(clients):
            raise ValueError("device_index out of range")
        target_location = clients[idx].get("location", "")

    if not target_location:
        raise RuntimeError("UPnP device location is missing")

    session = aiohttp.ClientSession()
    requester = AiohttpSessionRequester(session)
    factory = UpnpFactory(requester)

    try:
        device = await factory.async_create_device(target_location)
        dmr = DmrDevice(device, None)
        await dmr.async_set_transport_uri(url)
        await dmr.async_play()
    finally:
        await session.close()

    return {"status": "playing", "device_location": target_location, "url": url}


def build_manifest(manifest_path: Path | str = "file_upnp_mcp_manifest.json") -> None:
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
