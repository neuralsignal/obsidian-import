"""Tests for the file-size guard at the extraction entry points.

extract_file() and extract_text() must reject files exceeding
extraction.max_file_size_mb immediately, before any backend dispatch.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import import extract_file, extract_text
from obsidian_import.config import ImportConfig, config_from_overrides
from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult

_ONE_MB = 1024 * 1024


def _small_limit_config() -> ImportConfig:
    return config_from_overrides({"extraction": {"max_file_size_mb": 1}})


def _write_file(path: Path, size_bytes: int) -> None:
    path.write_bytes(b"\0" * size_bytes)


class TestSizeGuard:
    def test_extract_file_rejects_oversized_before_dispatch(self, tmp_path: Path) -> None:
        config = _small_limit_config()
        oversized = tmp_path / "big.pdf"
        _write_file(oversized, 2 * _ONE_MB)

        with (
            patch("obsidian_import.extract_with_backend") as mock_backend,
            pytest.raises(ExtractionError) as exc_info,
        ):
            extract_file(oversized, config)

        mock_backend.assert_not_called()
        message = str(exc_info.value)
        assert "big.pdf" in message
        assert "2.0 MB" in message
        assert "1 MB" in message

    def test_extract_text_rejects_oversized_before_dispatch(self, tmp_path: Path) -> None:
        config = _small_limit_config()
        oversized = tmp_path / "big.csv"
        _write_file(oversized, 2 * _ONE_MB)

        with (
            patch("obsidian_import.extract_with_backend") as mock_backend,
            pytest.raises(ExtractionError) as exc_info,
        ):
            extract_text(oversized, config)

        mock_backend.assert_not_called()
        assert "big.csv" in str(exc_info.value)

    def test_extract_text_under_limit_dispatches(self, tmp_path: Path) -> None:
        config = _small_limit_config()
        small = tmp_path / "small.csv"
        _write_file(small, 1024)

        fake_result = ExtractionResult(markdown="ok", media_files=())
        with patch("obsidian_import.extract_with_backend", return_value=fake_result):
            assert extract_text(small, config) == "ok"

    def test_extract_file_missing_file_raises_extraction_error(self, tmp_path: Path) -> None:
        """A vanished file must fail as ExtractionError (an ObsidianImportError),
        not a raw OSError — the CLI batch loop only contains ObsidianImportError."""
        config = _small_limit_config()
        missing = tmp_path / "missing.pdf"
        with pytest.raises(ExtractionError, match="missing.pdf"):
            extract_file(missing, config)

    @settings(max_examples=30, deadline=None)
    @given(delta=st.integers(min_value=-4096, max_value=4096))
    def test_size_boundary_property(self, delta: int) -> None:
        """Files are rejected iff size strictly exceeds max_file_size_mb.

        Same boundary as discover_files by construction: both call the shared
        ExtractionConfig.exceeds_max_file_size predicate.
        """
        config = _small_limit_config()
        size = _ONE_MB + delta

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "boundary.csv"
            _write_file(target, size)
            assert target.stat().st_size == size

            fake_result = ExtractionResult(markdown="ok", media_files=())
            with patch("obsidian_import.extract_with_backend", return_value=fake_result):
                if delta > 0:
                    with pytest.raises(ExtractionError):
                        extract_text(target, config)
                else:
                    assert extract_text(target, config) == "ok"


class TestSizeGuardIntegrationXlsx:
    def test_oversized_xlsx_rejected_instantly(self, tmp_path: Path) -> None:
        """A real multi-sheet xlsx beyond the limit is rejected immediately.

        Before the guard, such a file would run into the extraction timeout
        (120s default) inside the xlsx backend. The guard must reject it at
        the entry point, well before any backend work.
        """
        from openpyxl import Workbook

        xlsx_path = tmp_path / "huge_workbook.xlsx"
        wb = Workbook()
        wb.remove(wb.active)
        # Random hex is incompressible, so the zipped xlsx stays large.
        for sheet_idx in range(3):
            ws = wb.create_sheet(f"Sheet{sheet_idx}")
            for _ in range(2000):
                ws.append([os.urandom(24).hex() for _ in range(10)])
        wb.save(str(xlsx_path))

        size_bytes = xlsx_path.stat().st_size
        assert size_bytes > _ONE_MB, f"fixture too small: {size_bytes} bytes"

        config = _small_limit_config()
        start = time.monotonic()
        with pytest.raises(ExtractionError) as exc_info:
            extract_file(xlsx_path, config)
        elapsed = time.monotonic() - start

        assert elapsed < 5, f"rejection took {elapsed:.1f}s, expected instant"
        message = str(exc_info.value)
        assert "huge_workbook.xlsx" in message
        assert "1 MB" in message
