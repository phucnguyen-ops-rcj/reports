from __future__ import annotations

from pathlib import Path

from src.scripts.alt_bb_ata.spot_order_book_imbalance import _resolve_output_path


def test_resolve_output_path_uses_passed_directory() -> None:
    output_path = _resolve_output_path(
        Path("/tmp/x/2026-05-18/ALT"),
        "ALT",
        "2026-05-18",
    )

    assert output_path == Path("/tmp/x/2026-05-18/ALT/spot_order_book_imbalance.png")
