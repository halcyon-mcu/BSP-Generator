"""
Sync generated BSP output into an external CCS workspace project.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Dict, List


@dataclass(frozen=True)
class WorkspaceLayout:
    workspace_path: Path
    project_path: Path
    configuration_path: Path


_SYNC_MANIFEST = ".bsp_generator_sync_manifest.json"


def resolve_workspace_layout(
    external_workspace_path: str,
    project_name: str,
    configuration: str = "Debug",
) -> WorkspaceLayout:
    workspace = Path(external_workspace_path).expanduser().resolve()
    project = (workspace / project_name).resolve()
    if not project.exists() or not project.is_dir():
        raise FileNotFoundError(
            f"CCS project path not found: {project} (workspace={workspace}, project={project_name})"
        )

    config_dir = (project / configuration).resolve()
    return WorkspaceLayout(
        workspace_path=workspace,
        project_path=project,
        configuration_path=config_dir,
    )


def sync_generated_to_project(
    output_dir: Path,
    project_path: Path,
    clean_stale_generated_files: bool = True,
) -> Dict[str, List[str]]:
    """
    Copy generated files into project root by basename.

    Source precedence is newest-by-mtime across:
      - output_dir/*
      - output_dir/include/*
      - output_dir/source/*
    """
    output_dir = Path(output_dir).resolve()
    project_path = Path(project_path).resolve()
    if not output_dir.exists():
        raise FileNotFoundError(f"Generated output directory does not exist: {output_dir}")
    if not project_path.exists():
        raise FileNotFoundError(f"CCS project directory does not exist: {project_path}")

    allowed_ext = {".c", ".h", ".s", ".asm", ".cmd", ".ld"}
    pools = [output_dir, output_dir / "include", output_dir / "source"]
    selected: Dict[str, Path] = {}

    for folder in pools:
        if not folder.exists():
            continue
        for entry in folder.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in allowed_ext:
                continue
            prior = selected.get(entry.name)
            if prior is None or entry.stat().st_mtime >= prior.stat().st_mtime:
                selected[entry.name] = entry

    copied: List[str] = []
    removed: List[str] = []
    source_hashes: Dict[str, str] = {}
    dest_hashes: Dict[str, str] = {}
    mismatches: List[str] = []

    selected_names = set(selected.keys())
    manifest_path = project_path / _SYNC_MANIFEST
    prior_managed = _load_sync_manifest(manifest_path)
    stale_prior = sorted(name for name in prior_managed if name not in selected_names)
    for stale_name in stale_prior:
        stale_path = project_path / stale_name
        if stale_path.exists() and stale_path.is_file():
            stale_path.unlink()
            removed.append(str(stale_path))

    if clean_stale_generated_files:
        for entry in sorted(project_path.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_file():
                continue
            if entry.name in selected_names:
                continue
            if entry.name == _SYNC_MANIFEST:
                continue
            if entry.suffix.lower() not in allowed_ext:
                continue
            if _looks_like_generated_bsp_file(entry.name):
                entry.unlink()
                removed.append(str(entry))
    for basename, src_path in sorted(selected.items(), key=lambda item: item[0]):
        dst_path = project_path / basename
        shutil.copy2(src_path, dst_path)
        src_hash = _sha256_file(src_path)
        dst_hash = _sha256_file(dst_path)
        source_hashes[basename] = src_hash
        dest_hashes[basename] = dst_hash
        if src_hash != dst_hash:
            mismatches.append(basename)
        copied.append(str(dst_path))

    _write_sync_manifest(manifest_path, sorted(selected_names))
    source_aggregate = _hash_aggregate(source_hashes)
    dest_aggregate = _hash_aggregate(dest_hashes)
    return {
        "copied_files": copied,
        "removed_files": sorted(set(removed)),
        "fingerprint": {
            "algorithm": "sha256",
            "source_aggregate": source_aggregate,
            "dest_aggregate": dest_aggregate,
            "matches": (source_aggregate == dest_aggregate) and (len(mismatches) == 0),
            "mismatch_files": sorted(mismatches),
            "file_count": len(source_hashes),
        },
    }


def _load_sync_manifest(manifest_path: Path) -> List[str]:
    if not manifest_path.exists():
        return []
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    managed = raw.get("managed_files", [])
    if not isinstance(managed, list):
        return []
    return [name for name in managed if isinstance(name, str) and name]


def _write_sync_manifest(manifest_path: Path, managed_files: List[str]) -> None:
    manifest = {"managed_files": managed_files}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _hash_aggregate(hashes: Dict[str, str]) -> str:
    hasher = hashlib.sha256()
    for name in sorted(hashes.keys()):
        hasher.update(name.encode("utf-8"))
        hasher.update(b":")
        hasher.update(hashes[name].encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _looks_like_generated_bsp_file(filename: str) -> bool:
    lower = filename.lower()
    if lower.endswith("_driver.c") or lower.endswith("_driver.h"):
        return True
    if lower.startswith("reg_") and lower.endswith(".h"):
        return True
    generated_names = {
        "system.c",
        "system.h",
        "entry.c",
        "main.c",
        "start.s",
        "start.asm",
        "linker.cmd",
        "bsp_validate.c",
        "bsp_validate.h",
        "vim.c",
        "vim.h",
        "pll_driver.c",
        "pll_driver.h",
        "iomm_driver.c",
        "iomm_driver.h",
        "pcr_driver.c",
        "pcr_driver.h",
        "sci_driver.c",
        "sci_driver.h",
        "lin_driver.c",
        "lin_driver.h",
        "gio_driver.c",
        "gio_driver.h",
    }
    return lower in generated_names
