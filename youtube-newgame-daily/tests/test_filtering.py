from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app_extractors import (
    classify_url,
    cleanup_name_fragment,
    extract_games_from_video,
    fallback_game_name,
    is_valid_game_name,
)
from app_models import ExtractedGame, VideoRecord
from app_reporting import collect_current_report_rows
from app_store_enricher import AppStoreEnricher, clean_page_title, is_reject_title
from app_storage import connect_database


def build_video(title: str, description: str) -> VideoRecord:
    return VideoRecord(
        channel_name="TestChannel",
        channel_id="UC_TEST",
        video_id="vid123",
        title=title,
        description=description,
        published_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        published_date=date(2026, 5, 19),
        url="https://www.youtube.com/watch?v=vid123",
        raw_json={},
    )


class FilteringTests(unittest.TestCase):
    def test_google_play_link_kept(self) -> None:
        video = build_video(
            "My New Game Gameplay",
            "My New Game https://play.google.com/store/apps/details?id=com.example.game",
        )
        games = extract_games_from_video(video)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].link_type, "google_play")
        self.assertEqual(games[0].confidence, "high")

    def test_app_store_link_kept(self) -> None:
        video = build_video(
            "Vehicle Masters #shorts #vehicles #vehicle 🚗🚓🚕",
            "https://apps.apple.com/app/id6444705312",
        )
        games = extract_games_from_video(video)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].link_type, "app_store")
        self.assertEqual(games[0].confidence, "high")
        self.assertEqual(games[0].game_name, "Vehicle Masters")

    def test_support_google_play_filtered(self) -> None:
        result = classify_url("https://support.google.com/googleplay/answer/1626831")
        self.assertTrue(result["reject"])

    def test_terms_withhive_filtered(self) -> None:
        result = classify_url("https://terms.withhive.com/terms/policy/view/M121/T1")
        self.assertTrue(result["reject"])

    def test_superbox_terms_filtered(self) -> None:
        result = classify_url("http://superboxgo.com/termsofservice_en.php")
        self.assertTrue(result["reject"])

    def test_superbox_privacy_filtered(self) -> None:
        result = classify_url("http://superboxgo.com/privacypolicy_en.php")
        self.assertTrue(result["reject"])

    def test_cdn_policy_filtered(self) -> None:
        result = classify_url("https://cdn.endlessfrontier.io/ef2/policy/privacy_en.html")
        self.assertTrue(result["reject"])

    def test_x7game_down_not_directly_reportable(self) -> None:
        video = build_video("Random Video", "________________ https://kol4.x7game.com/tggame_13/down?tgid=122315&gid=17042")
        games = extract_games_from_video(video)
        rows = collect_current_report_rows([asdict(game) for game in games], set())
        self.assertEqual(rows, [])
        self.assertIn(games[0].confidence, {"low", "rejected"})

    def test_underscores_name_filtered(self) -> None:
        self.assertFalse(is_valid_game_name("________________________"))

    def test_generic_policy_names_filtered(self) -> None:
        for name in ["官方網站", "服務條款", "隱私權政策", "Conditions regarding the usage of this game"]:
            self.assertFalse(is_valid_game_name(name))

    def test_video_title_cleaned(self) -> None:
        self.assertEqual(fallback_game_name("Vehicle Masters #shorts #vehicles #vehicle 🚗🚓🚕"), "Vehicle Masters")

    def test_app_store_title_preferred_when_available(self) -> None:
        video = build_video(
            "Vehicle Masters #shorts #vehicles #vehicle 🚗🚓🚕",
            "https://apps.apple.com/app/id6444705312",
        )
        game = extract_games_from_video(video)[0]
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect_database(Path(tmp) / "test.db")
            enricher = AppStoreEnricher(conn)
            with patch.object(
                enricher,
                "_fetch_page_title",
                return_value=("Vehicle Masters on the App Store", "Vehicle Masters", "ok"),
            ):
                enriched = enricher.enrich_game(game)
            self.assertEqual(enriched.game_name, "Vehicle Masters")
            conn.close()

    def test_generic_app_store_title_does_not_override_fallback(self) -> None:
        video = build_video(
            "Vehicle Masters #shorts #vehicles #vehicle 🚗🚓🚕",
            "https://apps.apple.com/app/id6444705312",
        )
        game = extract_games_from_video(video)[0]
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect_database(Path(tmp) / "test.db")
            enricher = AppStoreEnricher(conn)
            with patch.object(
                enricher,
                "_fetch_page_title",
                return_value=("‎iPhone 版“Today” - App Store", "", "failed"),
            ):
                enriched = enricher.enrich_game(game)
            self.assertEqual(enriched.game_name, "Vehicle Masters")
            conn.close()

    def test_real_chinese_game_name_not_removed(self) -> None:
        self.assertEqual(cleanup_name_fragment("猫咪钓鱼场 - Google Play 上的应用"), "猫咪钓鱼场")
        self.assertTrue(is_valid_game_name("猫咪钓鱼场"))

    def test_non_store_game_link_can_be_medium_confidence(self) -> None:
        video = build_video("My New Game", "My New Game https://example.com/game/my-new-game")
        game = extract_games_from_video(video)[0]
        self.assertEqual(game.link_type, "non_store")
        self.assertEqual(game.confidence, "medium")

    def test_non_store_homepage_generic_name_rejected(self) -> None:
        video = build_video("官方網站", "官方網站 https://superboxgo.com")
        game = extract_games_from_video(video)[0]
        self.assertEqual(game.link_type, "rejected")
        self.assertEqual(game.confidence, "rejected")

    def test_reject_title_detection(self) -> None:
        self.assertTrue(is_reject_title("Privacy Policy"))
        self.assertEqual(clean_page_title("猫咪钓鱼场 - Google Play 上的应用"), "猫咪钓鱼场")


if __name__ == "__main__":
    unittest.main()
