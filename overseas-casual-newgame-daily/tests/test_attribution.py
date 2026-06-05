from src.attribution import MappingRow, apply_attribution, attribute_product


TARGETS = ["Homa", "Voodoo", "Rollic", "Azur", "Tapnation", "SayGames", "Supersonic"]


def test_package_mapping_wins() -> None:
    result = attribute_product(
        {"package": "com.SBG.MatchTrip"},
        [MappingRow("package", "com.SBG.MatchTrip", "Voodoo", "high", "test")],
        TARGETS,
    )
    assert result is not None
    assert result.canonical_company == "Voodoo"
    assert result.matched_by == "package"


def test_developer_mapping_wins_over_product_override() -> None:
    result = attribute_product(
        {"package": "com.example.game", "developer_name": "Example Dev"},
        [
            MappingRow("package", "com.example.game", "Voodoo", "high", "test"),
            MappingRow("developer_name", "Example Dev", "Homa", "high", "test"),
        ],
        TARGETS,
    )
    assert result is not None
    assert result.canonical_company == "Homa"
    assert result.matched_by == "developer_name"


def test_domain_mapping_handles_urls() -> None:
    result = attribute_product(
        {"privacy_url": "https://www.homagames.com/privacy"},
        [MappingRow("domain", "homagames.com", "Homa", "high", "test")],
        TARGETS,
    )
    assert result is not None
    assert result.canonical_company == "Homa"


def test_unmapped_product_goes_to_unmatched() -> None:
    kept, unmatched = apply_attribution(
        [{"product_name": "Mystery Game", "developer_name": "Unknown Studio"}],
        [],
        TARGETS,
    )
    assert kept == []
    assert unmatched[0]["ignore_reason"] == "no_company_mapping"


def test_conflict_account_can_be_kept_as_unknown_bucket() -> None:
    kept, unmatched = apply_attribution(
        [{"developer_name": "Terek Gaming"}],
        [MappingRow("developer_name", "Terek Gaming", "未知", "medium", "test")],
        TARGETS + ["未知"],
    )
    assert unmatched == []
    assert kept[0]["canonical_company"] == "未知"
