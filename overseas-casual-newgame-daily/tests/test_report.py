from pathlib import Path

from src.report import write_markdown


def test_markdown_report_groups_by_company(tmp_path: Path) -> None:
    output = tmp_path / "report.md"
    write_markdown(
        [
            {"canonical_company": "Homa", "product_name": "Art Layers", "store_url": "https://example.com/a"},
            {"canonical_company": "Voodoo", "product_name": "Match Trip", "store_url": "https://example.com/b"},
        ],
        "2026-06-02",
        output,
        "2026-05-30 至 2026-06-01",
    )
    text = output.read_text(encoding="utf-8")
    assert "海外休闲新品日报 (2026-06-02)" in text
    assert "扫描范围：2026-05-30 至 2026-06-01" in text
    assert "Homa (新增 1 个)" in text
    assert "Match Trip：https://example.com/b" in text
