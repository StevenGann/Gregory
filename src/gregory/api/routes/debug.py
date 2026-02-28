"""Debug routes: log streaming and config editing for the debug UI."""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from gregory.config import get_config_file_path, get_settings
from gregory.log_buffer import get_log_buffer

router = APIRouter(prefix="/debug", tags=["debug"])

# Keys whose values are masked in GET and preserved on PATCH when client sends placeholder
_SECRET_KEYS = frozenset({"anthropic_api_key", "gemini_api_key", "ha_access_token", "api_key"})
MASKED_PLACEHOLDER = "[SET]"
MASKED_EMPTY = "[NOT SET]"


def _mask_secrets(obj: dict) -> dict:
    """Return a copy with secret values replaced by placeholders."""
    out = {}
    for k, v in obj.items():
        if k in _SECRET_KEYS:
            if v and isinstance(v, str) and len(v) > 4:
                out[k] = MASKED_PLACEHOLDER
            else:
                out[k] = MASKED_EMPTY if v is None or v == "" else v
        elif isinstance(v, dict):
            out[k] = _mask_secrets(v)
        elif isinstance(v, list):
            out[k] = [
                _mask_secrets(x) if isinstance(x, dict) else x
                for x in v
            ]
        else:
            out[k] = v
    return out


def _restore_secrets(payload: dict, existing: dict) -> dict:
    """Use payload as base; for secret keys with placeholder, copy from existing."""
    out = {}
    for k, v in payload.items():
        if k in _SECRET_KEYS:
            if v in (MASKED_PLACEHOLDER, "[MASKED]", ""):
                out[k] = existing.get(k)
            else:
                out[k] = v
        elif isinstance(v, dict):
            exist_sub = existing.get(k) if isinstance(existing.get(k), dict) else {}
            out[k] = _restore_secrets(v, exist_sub)
        elif isinstance(v, list):
            exist_list = existing.get(k) if isinstance(existing.get(k), list) else []
            out[k] = [
                _restore_secrets(pv, exist_list[i]) if isinstance(pv, dict) and i < len(exist_list) and isinstance(exist_list[i], dict) else pv
                for i, pv in enumerate(v)
            ]
        else:
            out[k] = v
    return out


def _matches_filters(
    entry: dict,
    levels: set[str] | None,
    substring: str | None,
) -> bool:
    if levels and entry.get("level") not in levels:
        return False
    if substring:
        sub = substring.lower()
        msg = (entry.get("message") or "").lower()
        lgr = (entry.get("level") or "").lower()
        if sub not in msg and sub not in lgr and sub not in (entry.get("logger") or "").lower():
            return False
    return True


@router.get("/logs")
async def get_logs(
    levels: str | None = Query(None, description="Comma-separated: DEBUG,INFO,WARNING,ERROR"),
    substring: str | None = Query(None, description="Filter messages containing this string"),
    limit: int = Query(500, ge=1, le=2000),
) -> list[dict]:
    """Return recent log entries. Filter by levels and/or substring."""
    buf = get_log_buffer()
    entries = buf.get_recent(limit=limit)

    level_set = None
    if levels:
        level_set = {s.strip().upper() for s in levels.split(",") if s.strip()}
        level_set &= {"DEBUG", "INFO", "WARNING", "ERROR"}

    return [
        e
        for e in entries
        if _matches_filters(e, level_set, substring)
    ]


@router.get("/logs/stream")
async def stream_logs(request: Request) -> StreamingResponse:
    """Server-Sent Events stream of new log entries."""
    buf = get_log_buffer()
    buf.set_event_loop(asyncio.get_running_loop())
    queue = buf.subscribe()

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            buf.unsubscribe(queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/config")
async def get_config() -> dict:
    """Return config.json contents with secrets masked. For debug UI."""
    path = get_config_file_path()
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"_error": "Invalid JSON in config file"}
    return _mask_secrets(data if isinstance(data, dict) else {})


@router.patch("/config")
async def patch_config(request: Request) -> dict:
    """Update config.json with request body. Secrets sent as [SET] are preserved. Clears settings cache."""
    path = get_config_file_path()
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except json.JSONDecodeError:
            pass
    try:
        payload = await request.json()
    except Exception:
        return {"_error": "Invalid JSON body"}
    if not isinstance(payload, dict):
        return {"_error": "Body must be a JSON object"}
    merged = _restore_secrets(payload, existing)
    try:
        path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    except OSError as e:
        return {"_error": f"Failed to write config: {e}"}
    get_settings.cache_clear()
    return _mask_secrets(merged)
