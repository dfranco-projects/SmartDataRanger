"""Tests for smartdataranger.paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdataranger.errors import SmartDataRangerError
from smartdataranger.paths import WorkspacePaths, relative_source, resolve_workspace


class TestResolveWorkspace:
    def test_happy_path(self, tmp_path: Path) -> None:
        ws = resolve_workspace(tmp_path)
        assert isinstance(ws, WorkspacePaths)
        assert ws.root == tmp_path.resolve()
        assert ws.output_dir == ws.root / ".smartdataranger"
        assert ws.metadata_file == ws.output_dir / "metadata.json"
        assert ws.extracted_dir == ws.output_dir / "extracted"

    def test_accepts_str(self, tmp_path: Path) -> None:
        ws = resolve_workspace(str(tmp_path))
        assert ws.root == tmp_path.resolve()

    def test_no_mkdir(self, tmp_path: Path) -> None:
        ws = resolve_workspace(tmp_path)
        assert not ws.output_dir.exists()

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        with pytest.raises(SmartDataRangerError, match="does not exist"):
            resolve_workspace(tmp_path / "missing")

    def test_file_not_dir(self, tmp_path: Path) -> None:
        file = tmp_path / "data.csv"
        file.write_text("a,b\n1,2\n")
        with pytest.raises(SmartDataRangerError, match="not a directory"):
            resolve_workspace(file)


class TestRelativeSource:
    def test_direct_child(self, tmp_path: Path) -> None:
        assert relative_source(tmp_path / "sales.csv", tmp_path) == "sales.csv"

    def test_nested(self, tmp_path: Path) -> None:
        nested = tmp_path / "sub" / "dir" / "sales.csv"
        assert relative_source(nested, tmp_path) == "sub/dir/sales.csv"

    def test_out_of_root_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "elsewhere" / "sales.csv"
        with pytest.raises(SmartDataRangerError, match="not under root"):
            relative_source(outside, root)

    def test_dotdot_escape_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        sneaky = root / ".." / "escape.csv"
        with pytest.raises(SmartDataRangerError, match="not under root"):
            relative_source(sneaky, root)
