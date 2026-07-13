"""plugins/tool_kit/datetime_tool.py — DateTimeTool."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ooagent.adapters.tools.base import BaseTool
from ooagent.core.protocols import JSONSchema


class DateTimeTool(BaseTool):
    name = "datetime"
    description = "Returns the current UTC date and time in ISO 8601 format."

    def input_schema(self) -> JSONSchema:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        'IANA timezone string (e.g. "America/New_York"). Defaults to UTC.'
                    ),
                },
            },
            "required": [],
        }

    async def execute(self, args: dict[str, Any]) -> Any:
        tz = args.get("timezone")
        if tz is None:
            tz = "UTC"
        try:
            now = datetime.now(ZoneInfo(tz))
            if tz == "UTC":
                iso = now.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            else:
                iso = now.isoformat(timespec="seconds")
            return {"iso": iso, "timezone": tz}
        except Exception:
            now_utc = datetime.now(UTC)
            iso = now_utc.strftime("%Y-%m-%dT%H:%M:%S.") + (
                f"{now_utc.microsecond // 1000:03d}Z"
            )
            return {"iso": iso, "timezone": "UTC"}
