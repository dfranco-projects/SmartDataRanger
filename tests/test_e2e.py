"""End-to-end pipeline tests. These exercise the full public surface
(import_dataset, load_dataset, metadata.json, the `ranger` CLI) and only pass
once every work unit is merged."""

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import smartdataranger
from smartdataranger import import_dataset, load_dataset
from smartdataranger.models import ImportReport, Severity

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[1]

_DF = pd.DataFrame(
    {
        "id": [1, 2, 3],
        "name": ["ada", "grace", "alan"],
        "score": [9.5, 8.0, 7.0],
    }
)

MESSY_CONTENT = (
    "ciudad;país;población\nBogotá;Colombia;8000000\nSão Paulo;Brasil\nMéxico DF;México;9000000\n"
)


def _write_clean_files(root: Path) -> None:
    _DF.to_csv(root / "data.csv", index=False)
    _DF.to_json(root / "data.json", orient="records")
    _DF.to_csv(root / "data.txt", index=False, sep="\t")


def _write_zip(root: Path, tmp_path: Path) -> None:
    inner = tmp_path / "inner_a.csv"
    _DF.to_csv(inner, index=False)
    with zipfile.ZipFile(root / "archive.zip", "w") as zf:
        zf.write(inner, "inner_a.csv")
    inner.unlink()


def _build_mixed_dataset(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    root.mkdir()
    _write_clean_files(root)
    _write_zip(root, tmp_path)
    (root / "messy.csv").write_bytes(MESSY_CONTENT.encode("latin-1"))
    return root


def _run_import(root: Path) -> tuple[dict[str, pd.DataFrame], ImportReport]:
    result, report = import_dataset(root)
    assert isinstance(result, dict)
    assert isinstance(report, ImportReport)
    return result, report


class TestImportDataset:
    def test_mixed_folder_returns_expected_frames(self, tmp_path: Path) -> None:
        root = _build_mixed_dataset(tmp_path)
        frames, report = _run_import(root)

        expected_keys = {"data.csv", "data.json", "data.txt", "inner_a.csv", "messy.csv"}
        assert expected_keys <= set(frames)
        # The zip archive itself must not appear as a loaded frame.
        assert "archive.zip" not in frames

        for key in ("data.csv", "data.txt", "inner_a.csv"):
            frame = frames[key]
            assert list(frame.columns) == ["id", "name", "score"]
            assert len(frame) == 3
            assert list(frame["name"]) == ["ada", "grace", "alan"]
        assert list(frames["data.json"].columns) == ["id", "name", "score"]
        assert len(frames["data.json"]) == 3

        # The messy latin-1 semicolon file must be decoded and split correctly.
        messy = frames["messy.csv"]
        assert list(messy.columns) == ["ciudad", "país", "población"]
        assert "Bogotá" in set(messy["ciudad"].astype(str))

    def test_messy_file_diagnostics_reported(self, tmp_path: Path) -> None:
        root = _build_mixed_dataset(tmp_path)
        _, report = _run_import(root)
        messy_codes = {d.code for d in report.all_diagnostics if d.file == "messy.csv"}
        assert "ENCODING_NON_UTF8" in messy_codes
        assert "DELIMITER_SNIFFED" in messy_codes

    def test_profiles_present_for_every_file(self, tmp_path: Path) -> None:
        root = _build_mixed_dataset(tmp_path)
        _, report = _run_import(root)
        assert report.files
        for file_report in report.files:
            assert file_report.column_profiles, f"no profiles for {file_report.metadata.file_name}"
            names = {p.name for p in file_report.column_profiles}
            assert names == set(file_report.metadata.columns)

    def test_single_file_returns_bare_dataframe(self, tmp_path: Path) -> None:
        root = tmp_path / "single"
        root.mkdir()
        _DF.to_csv(root / "only.csv", index=False)
        result, report = import_dataset(root)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["id", "name", "score"]
        assert not report.has_errors()

    def test_empty_folder_reports_empty_dataset(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()
        result, report = import_dataset(root)
        assert result == {}
        assert "EMPTY_DATASET" in {d.code for d in report.diagnostics}


class TestMetadataRoundTrip:
    def test_metadata_written_and_load_dataset_reproduces_frames(self, tmp_path: Path) -> None:
        root = _build_mixed_dataset(tmp_path)
        frames, _ = _run_import(root)

        metadata_file = root / ".smartdataranger" / "metadata.json"
        assert metadata_file.is_file()
        # metadata.json itself must be valid JSON.
        json.loads(metadata_file.read_text(encoding="utf-8"))

        loaded = load_dataset(metadata_file)
        assert set(loaded) == set(frames)
        for key, frame in frames.items():
            pd.testing.assert_frame_equal(loaded[key], frame)

    def test_write_metadata_false_writes_nothing(self, tmp_path: Path) -> None:
        root = tmp_path / "nometa"
        root.mkdir()
        _write_clean_files(root)
        import_dataset(root, write_metadata=False)
        assert not (root / ".smartdataranger" / "metadata.json").exists()


class TestCliSmoke:
    def _run_ranger(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "ranger", "scan", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def test_scan_exit_code_and_output(self, tmp_path: Path) -> None:
        root = tmp_path / "clean"
        root.mkdir()
        _write_clean_files(root)
        result = self._run_ranger(str(root))
        assert result.returncode == 0, result.stderr
        for name in ("data.csv", "data.json", "data.txt"):
            assert name in result.stdout

    def test_scan_json_output_parses(self, tmp_path: Path) -> None:
        root = tmp_path / "clean_json"
        root.mkdir()
        _write_clean_files(root)
        result = self._run_ranger(str(root), "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert set(payload) >= {"root", "files", "diagnostics"}
        file_names = {entry["metadata"]["file_name"] for entry in payload["files"]}
        assert {"data.csv", "data.json", "data.txt"} <= file_names


def test_public_api_exports() -> None:
    assert smartdataranger.__version__ == "0.2.0"
    assert callable(smartdataranger.import_dataset)
    assert callable(smartdataranger.load_dataset)
    assert Severity.ERROR in Severity
