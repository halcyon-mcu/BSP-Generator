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
            # Handle both StreamingBody (old) and bytes (new cached format)
            if hasattr(body, "read"):
                payload = json.loads(body.read())
            elif isinstance(body, bytes):
                payload = json.loads(body.decode('utf-8'))
            else:
                payload = json.loads(body)
        else:
            payload = resp
    except Exception as e:
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


def extract_usage_from_bedrock_response(resp) -> dict:
    """
    Extract usage statistics (input_tokens, output_tokens) from Bedrock response.
    Returns dict with 'input_tokens' and 'output_tokens', or zeros if not available.
    """
    try:
        if hasattr(resp, "get"):
            body = resp.get("body")
            # Handle both StreamingBody (old) and bytes (new cached format)
            if hasattr(body, "read"):
                payload = json.loads(body.read())
            elif isinstance(body, bytes):
                payload = json.loads(body.decode('utf-8'))
            else:
                payload = json.loads(body)
        else:
            payload = resp if isinstance(resp, dict) else {}

        usage = payload.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0)
        }
    except Exception:
        return {"input_tokens": 0, "output_tokens": 0}
