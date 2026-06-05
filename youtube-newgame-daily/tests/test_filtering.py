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
from app_store_enricher import extract_html_title
from app_storage import connect_database, save_store_title_cache


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
            "【手遊試玩】全新冒險抓寵RPG手遊，開啟馴獸新徵程",
            "My New Game https://play.google.com/store/apps/details?id=com.example.game",
        )
        games = extract_games_from_video(video)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].link_type, "google_play")
        self.assertEqual(games[0].confidence, "low")
        self.assertEqual(games[0].reject_reason, "store_title_required")

    def test_app_store_link_kept(self) -> None:
        video = build_video(
            "Vehicle Masters #shorts #vehicles #vehicle 🚗🚓🚕",
            "https://apps.apple.com/app/id6444705312",
        )
        games = extract_games_from_video(video)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].link_type, "app_store")
        self.assertEqual(games[0].confidence, "low")
        self.assertEqual(games[0].game_name, "Vehicle Masters")

    def test_support_google_play_filtered(self) -> None:
        result = classify_url("https://support.google.com/googleplay/answer/1626831")
        self.assertTrue(result["reject"])

    def test_apkpure_package_id_extracted_from_url_path(self) -> None:
        result = classify_url(
            "https://apkpure.com/cn/%E6%8B%89%E8%92%82%E4%BA%9E%E7%9A%84%E9%AA%B0%E5%AD%90%E4%B9%8B%E6%97%85-%E7%99%82%E7%99%92%E7%B3%BB%E5%86%92%E9%9A%AArpg/com.sanctumstudio.poly"
        )
        self.assertEqual(result["package_id"], "com.sanctumstudio.poly")

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

    def test_chinese_promo_sentence_not_used_as_game_name(self) -> None:
        self.assertFalse(is_valid_game_name("只需擲出骰子，即可展開一段輕鬆的冒險。"))
        self.assertFalse(is_valid_game_name("忘掉你對傳統防禦遊戲的既有印象！"))

    def test_metadata_names_filtered(self) -> None:
        for name in [
            "Size: 1,94 GB",
            "Size: 714 MB",
            "PC",
            "IOS",
            "️ IOS",
            "Android",
            "Version: 1.0",
            "iOS: TBA",
            "Android: TBA",
            "Online/Offline: Online",
            "Early Access",
        ]:
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
            self.assertEqual(enriched.extracted_from, "store_page_title")
            self.assertEqual(enriched.confidence, "high")
            conn.close()

    def test_failed_app_store_title_rejects_video_title_fallback(self) -> None:
        video = build_video(
            "【手遊試玩】全新冒險抓寵RPG手遊，開啟馴獸新徵程",
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
            rows = collect_current_report_rows([asdict(enriched)], set())
            self.assertEqual(rows, [])
            self.assertEqual(enriched.confidence, "rejected")
            self.assertEqual(enriched.reject_reason, "store_title_required")
            conn.close()

    def test_failed_app_store_title_rejects_size_context(self) -> None:
        video = build_video(
            "Dragon Village 3 | Gameplay Android Ios",
            "Size: 1,94 GB https://apps.apple.com/us/app/dragon-village-3/id6499562253",
        )
        game = extract_games_from_video(video)[0]
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect_database(Path(tmp) / "test.db")
            enricher = AppStoreEnricher(conn)
            with patch.object(
                enricher,
                "_fetch_page_title",
                return_value=("iPhone 版“Today” - App Store", "", "failed"),
            ):
                enriched = enricher.enrich_game(game)
            rows = collect_current_report_rows([asdict(enriched)], set())
            self.assertEqual(rows, [])
            self.assertEqual(enriched.confidence, "rejected")
            conn.close()

    def test_failed_store_title_can_keep_description_context_as_medium(self) -> None:
        video = build_video(
            "【手遊試玩】全新冒險抓寵RPG手遊，開啟馴獸新徵程",
            "Beast Quest https://play.google.com/store/apps/details?id=com.example.beast",
        )
        game = extract_games_from_video(video)[0]
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect_database(Path(tmp) / "test.db")
            enricher = AppStoreEnricher(conn)
            with patch.object(
                enricher,
                "_fetch_page_title",
                return_value=("", "", "failed"),
            ):
                enriched = enricher.enrich_game(game)
            self.assertEqual(enriched.game_name, "Beast Quest")
            self.assertEqual(enriched.confidence, "medium")
            self.assertEqual(enriched.reject_reason, "store_title_unavailable_context_fallback")
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
        self.assertEqual(clean_page_title("‎心跳陷落 App - App Store"), "心跳陷落")
        self.assertEqual(clean_page_title("灵魂潮汐2 - 安卓官方预约 - TapTap"), "灵魂潮汐2")
        self.assertEqual(clean_page_title("遗忘之海 - 安卓官方预约 - TapTap"), "遗忘之海")
        self.assertEqual(clean_page_title("Anime TCG Merge Battle APK for Android Download"), "Anime TCG Merge Battle")
        self.assertEqual(clean_page_title("幻獸之旅：新紀元 Old Versions APK Download"), "幻獸之旅：新紀元")
        self.assertEqual(clean_page_title("拉蒂亞的骰子之旅安卓版游戏APK下载"), "拉蒂亞的骰子之旅")

    def test_extract_html_title_prefers_og_title(self) -> None:
        html = (
            '<html><head><title>Fallback - Apps on Google Play</title>'
            '<meta content="Pixel Hero: Survival - Apps on Google Play" property="og:title">'
            "</head></html>"
        )
        self.assertEqual(extract_html_title(html), "Pixel Hero: Survival - Apps on Google Play")

    def test_same_game_prefers_google_play_over_app_store(self) -> None:
        google = ExtractedGame(
            report_date=date(2026, 5, 19),
            channel_name="TestChannel",
            video_id="vid-google",
            video_title="Pixel Hero",
            game_name="Pixel Hero",
            normalized_game_name="pixelhero",
            store_url="https://play.google.com/store/apps/details?id=com.example.pixel",
            package_id="com.example.pixel",
            apple_app_id="",
            platform="google_play",
            extracted_from="store_page_title",
            link_type="google_play",
            confidence="high",
            reject_reason="",
            normalized_store_url="https://play.google.com/store/apps/details",
        )
        apple = ExtractedGame(
            report_date=date(2026, 5, 19),
            channel_name="TestChannel",
            video_id="vid-apple",
            video_title="Pixel Hero",
            game_name="Pixel Hero",
            normalized_game_name="pixelhero",
            store_url="https://apps.apple.com/app/id123456789",
            package_id="",
            apple_app_id="123456789",
            platform="app_store",
            extracted_from="store_page_title",
            link_type="app_store",
            confidence="high",
            reject_reason="",
            normalized_store_url="https://apps.apple.com/app/id123456789",
        )
        rows = collect_current_report_rows([asdict(apple), asdict(google)], set())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "google_play")

    def test_same_package_prefers_google_play_over_apkpure(self) -> None:
        google = ExtractedGame(
            report_date=date(2026, 6, 1),
            channel_name="TestChannel",
            video_id="vid-google",
            video_title="拉蒂亞的骰子之旅",
            game_name="拉蒂亞的骰子之旅 - 療癒系冒險RPG",
            normalized_game_name="拉蒂亞的骰子之旅療癒系冒險rpg",
            store_url="https://play.google.com/store/apps/details?id=com.sanctumstudio.poly&hl=zh",
            package_id="com.sanctumstudio.poly",
            apple_app_id="",
            platform="google_play",
            extracted_from="store_page_title",
            link_type="google_play",
            confidence="high",
            reject_reason="",
            normalized_store_url="https://play.google.com/store/apps/details",
        )
        apkpure = ExtractedGame(
            report_date=date(2026, 6, 1),
            channel_name="TestChannel",
            video_id="vid-apkpure",
            video_title="拉蒂亞的骰子之旅",
            game_name="拉蒂亞的骰子之旅",
            normalized_game_name="拉蒂亞的骰子之旅",
            store_url="https://apkpure.com/cn/%E6%8B%89%E8%92%82%E4%BA%9E%E7%9A%84%E9%AA%B0%E5%AD%90%E4%B9%8B%E6%97%85-%E7%99%82%E7%99%92%E7%B3%BB%E5%86%92%E9%9A%AArpg/com.sanctumstudio.poly",
            package_id="com.sanctumstudio.poly",
            apple_app_id="",
            platform="third_party_store",
            extracted_from="store_page_title",
            link_type="non_store",
            confidence="high",
            reject_reason="",
            normalized_store_url="https://apkpure.com/cn/%E6%8B%89%E8%92%82%E4%BA%9E%E7%9A%84%E9%AA%B0%E5%AD%90%E4%B9%8B%E6%97%85-%E7%99%82%E7%99%92%E7%B3%BB%E5%86%92%E9%9A%AArpg/com.sanctumstudio.poly",
        )
        rows = collect_current_report_rows([asdict(apkpure), asdict(google)], set())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "google_play")

    def test_taptap_cn_link_uses_page_title(self) -> None:
        video = build_video(
            "Crush Abyss - Official Released Gameplay",
            "Size: 714 MB https://www.taptap.cn/app/786394?os=android",
        )
        game = extract_games_from_video(video)[0]
        self.assertEqual(game.platform, "third_party_store")
        self.assertEqual(game.confidence, "low")
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect_database(Path(tmp) / "test.db")
            enricher = AppStoreEnricher(conn)
            with patch.object(
                enricher,
                "_fetch_page_title",
                return_value=("心跳陷落 - 安卓官方下载 - TapTap", "心跳陷落", "ok"),
            ):
                enriched = enricher.enrich_game(game)
            self.assertEqual(enriched.game_name, "心跳陷落")
            self.assertEqual(enriched.extracted_from, "store_page_title")
            self.assertEqual(enriched.confidence, "high")
            conn.close()

    def test_cached_apkpure_title_is_recleaned_and_used(self) -> None:
        video = build_video(
            "【手遊試玩】Anime TCG Merge Battle (Android/IOS)",
            "https://apkpure.com/anime-tcg-merge-battle/com.anime.tcg.merge.battle",
        )
        game = extract_games_from_video(video)[0]
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect_database(Path(tmp) / "test.db")
            save_store_title_cache(
                conn,
                game.store_url,
                "Anime TCG Merge Battle APK for Android Download",
                "Anime TCG Merge Battle APK for Android Download",
                "ok",
            )
            enricher = AppStoreEnricher(conn)
            enriched = enricher.enrich_game(game)
            self.assertEqual(enriched.game_name, "Anime TCG Merge Battle")
            self.assertEqual(enriched.extracted_from, "store_page_title")
            self.assertEqual(enriched.confidence, "high")
            conn.close()


if __name__ == "__main__":
    unittest.main()
