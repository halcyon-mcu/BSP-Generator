import os
from pathlib import Path, PurePosixPath
import re
from modules.utils import _now_tag

FILE_SPLIT_RE = re.compile(r"^===== FILE: (.+) =====\s*$", re.M)

def _safe_relpath(s: str) -> str:
    """
    Normalize a model-provided path:
    - forbid absolute paths
    - collapse backslashes to forward slashes
    - forbid parent directory traversal
    """
    p = str(s).strip()
    # Normalize slashes
    p = p.replace("\\", "/")
    # Remove leading './'
    if p.startswith("./"):
        p = p[2:]
    # Forbid absolute or drive-qualified paths
    if os.path.isabs(p):
        raise ValueError(f"Refusing absolute path from model: {s!r}")
    # Forbid parent traversal
    parts = PurePosixPath(p).parts
    if any(seg == ".." for seg in parts):
        raise ValueError(f"Refusing path with '..' from model: {s!r}")
    return p

def split_and_write_files(raw_text: str, out_dir: Path) -> list[Path]:
    out_dir = out_dir.resolve()  # <-- key fix
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    ts = _now_tag()
    (artifacts / f"llm_raw_{ts}.txt").write_text(raw_text, encoding="utf-8")

    matches = list(FILE_SPLIT_RE.finditer(raw_text))
    if not matches:
        print("[warn] No file separators found. Check _artifacts/ for raw output.")
        return []

    written: list[Path] = []

    # Save any preamble before the first separator
    first = matches[0]
    if first.start() > 0:
        preamble = raw_text[: first.start()].strip()
        if preamble:
            (artifacts / f"llm_preamble_{ts}.txt").write_text(preamble, encoding="utf-8")
            print("[warn] Preamble saved to _artifacts/llm_preamble_*.txt")

    for i, m in enumerate(matches):
        raw_rel = m.group(1).strip()
        rel_norm = _safe_relpath(raw_rel)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        content = raw_text[start:end].lstrip("\n")

        target = (out_dir / rel_norm).resolve()
        # Ensure the resolved path is still under out_dir (defense in depth)
        try:
            target.relative_to(out_dir)
        except ValueError:
            raise RuntimeError(f"Refusing to write outside out_dir: {target}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)

        # Print a friendly relative path (robust across Windows)
        try:
            print("[ok] Wrote", target.relative_to(out_dir))
        except ValueError:
            # Fallback if something odd happens
            print("[ok] Wrote", os.path.relpath(str(target), str(out_dir)))
