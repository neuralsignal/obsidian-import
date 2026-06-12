"""Tests for isolation-mode forwarding through extract_with_backend.

Dispatch and availability tests live in test_registry.py.
"""

import types
from pathlib import Path
from unittest.mock import patch

from conftest import make_test_media_config

from obsidian_import.config import BackendsConfig
from obsidian_import.registry import extract_with_backend

_TEST_MEDIA_CONFIG = make_test_media_config()


def _native_backends() -> BackendsConfig:
    return BackendsConfig(
        pdf="native",
        docx="native",
        pptx="native",
        xlsx="native",
        csv="native",
        json="native",
        yaml="native",
        image="native",
        html="native",
        default="native",
    )


class TestIsolationForwarding:
    def test_isolation_forwarded_when_backend_accepts_it(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n")

        received: dict = {}
        fake_module = types.ModuleType("obsidian_import.backends.native_csv")

        def fake_extract(path: Path, timeout_seconds: int, isolation: str) -> str:
            received["isolation"] = isolation
            return "extracted"

        fake_module.extract = fake_extract  # type: ignore[attr-defined]

        with patch("obsidian_import.registry.get_backend_module", return_value=fake_module):
            extract_with_backend(
                csv_file,
                backends=_native_backends(),
                timeout_seconds=30,
                media_config=_TEST_MEDIA_CONFIG,
                isolation="process",
            )

        assert received["isolation"] == "process"

    def test_isolation_skipped_when_backend_does_not_accept_it(self, tmp_path: Path) -> None:
        """Backends without a timeout wrapper (e.g. native_image) take no isolation arg."""
        png_file = tmp_path / "test.png"
        png_file.write_bytes(b"fake")

        fake_module = types.ModuleType("obsidian_import.backends.native_image")
        fake_module.extract = lambda path, timeout_seconds: "extracted"  # type: ignore[attr-defined]

        with patch("obsidian_import.registry.get_backend_module", return_value=fake_module):
            result = extract_with_backend(
                png_file,
                backends=_native_backends(),
                timeout_seconds=30,
                media_config=_TEST_MEDIA_CONFIG,
                isolation="process",
            )

        assert result.markdown == "extracted"
