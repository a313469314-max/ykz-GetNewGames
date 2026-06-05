from src.history import dedupe_products, product_dedupe_keys, remove_history_duplicates


def test_product_keys_prefer_store_identity() -> None:
    keys = product_dedupe_keys(
        {"store_url": "https://play.google.com/store/apps/details?id=com.example.game&hl=en"}
    )
    assert keys[0] == "package:com.example.game"


def test_dedupe_products_removes_duplicate_in_scan_window() -> None:
    kept, duplicates = dedupe_products(
        [
            {"product_name": "A", "package": "com.example.a"},
            {"product_name": "A copy", "store_url": "https://play.google.com/store/apps/details?id=com.example.a"},
        ]
    )
    assert len(kept) == 1
    assert duplicates[0]["ignore_reason"] == "duplicate_in_scan_window"


def test_remove_history_duplicates() -> None:
    kept, duplicates = remove_history_duplicates(
        [{"product_name": "A", "app_id": "123"}, {"product_name": "B", "app_id": "456"}],
        [{"product_name": "Old A", "store_url": "https://apps.apple.com/app/id123"}],
    )
    assert [row["product_name"] for row in kept] == ["B"]
    assert duplicates[0]["ignore_reason"] == "duplicate_in_history"
