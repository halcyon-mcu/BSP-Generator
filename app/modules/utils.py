import inspect
import json
import os
from datetime import datetime
from typing import List
from pathlib import Path


# ---------------- Utils ----------------
def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def extract_text_from_bedrock_response(resp) -> str:
    """
    Works whether invoke_model returns the raw Bedrock response (with .body)
    or already-decoded JSON, or just a text string.
    """
    # Already plain text?
    if isinstance(resp, str):
        return resp

    # boto3 response?
    try:
        if hasattr(resp, "get"):
            body = resp.get("body")
            payload = json.loads(body.read()) if hasattr(body, "read") else json.loads(body)
        else:
            payload = resp
    except Exception:
        # last resort
        return str(resp)

    parts = []
    for item in payload.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    text = "\n".join(parts).strip()

    if not text and "output_text" in payload:
        text = str(payload["output_text"]).strip()

    return text
