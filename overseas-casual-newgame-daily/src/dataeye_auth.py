from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataeye_browser import safe_page_text


LOGIN_SIGNALS = ("新品发现", "素材筛选", "搜索产品名", "搜索公司名", "我的收藏", "产品")
LOGIN_FORM_SIGNALS = ("帐号", "账号", "密码", "验证码", "忘记密码", "立即注册")
LOGIN_URL_HINTS = ("login", "signin", "sign-in")


@dataclass(frozen=True)
class DataEyeSettings:
    email: str
    password: str
    home_url: str
    storage_state: Path


def _load_dotenv(env_path: Path) -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings(project_root: Path | str = ".") -> DataEyeSettings:
    root = Path(project_root).resolve()
    _load_dotenv(root / ".env")
    home_url = os.getenv("DATAEYE_HOME_URL", "https://oversea-v2.dataeye.com/dashboard/home")
    storage_state = Path(os.getenv("DATAEYE_STORAGE_STATE", ".auth/dataeye-state.json"))
    if not storage_state.is_absolute():
        storage_state = root / storage_state
    email = os.getenv("DATAEYE_EMAIL", "").strip()
    password = os.getenv("DATAEYE_PASSWORD", "").strip()
    if not email or not password:
        raise RuntimeError("DATAEYE_EMAIL and DATAEYE_PASSWORD must be set in .env")
    return DataEyeSettings(
        email=email,
        password=password,
        home_url=home_url,
        storage_state=storage_state,
    )


def is_login_page(url: str) -> bool:
    lowered = (url or "").lower()
    return any(hint in lowered for hint in LOGIN_URL_HINTS)


def is_logged_in(page: Any, timeout_ms: int = 12_000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        try:
            url = page.url
        except Exception:
            url = ""
        if is_login_page(url):
            page.wait_for_timeout(500)
            continue

        body = safe_page_text(page, limit=80_000)
        if "登录" in body and sum(1 for signal in LOGIN_FORM_SIGNALS if signal in body) >= 2:
            page.wait_for_timeout(500)
            continue
        if any(signal in body for signal in LOGIN_SIGNALS):
            return True
        page.wait_for_timeout(500)
    return False


def _first_fillable(page: Any, selectors: tuple[str, ...]) -> Any | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=2_000):
                return locator
        except Exception:
            continue
    return None


def _fill_login_form(page: Any, settings: DataEyeSettings) -> bool:
    email_selectors = (
        'input[type="email"]',
        'input[name*="email" i]',
        'input[name*="account" i]',
        'input[name*="user" i]',
        'input[placeholder*="邮箱"]',
        'input[placeholder*="账号"]',
        'input[placeholder*="Email" i]',
        'input[placeholder*="Account" i]',
        'input[type="text"]',
    )
    password_selectors = (
        'input[type="password"]',
        'input[name*="password" i]',
        'input[placeholder*="密码"]',
        'input[placeholder*="Password" i]',
    )
    email_input = _first_fillable(page, email_selectors)
    password_input = _first_fillable(page, password_selectors)
    if not email_input or not password_input:
        return False
    email_input.fill(settings.email)
    password_input.fill(settings.password)
    return True


def _click_login_button(page: Any) -> None:
    button_texts = ("登录", "登 录", "Login", "Log in", "Sign in")
    for text in button_texts:
        try:
            page.get_by_role("button", name=text).first.click(timeout=2_000)
            return
        except Exception:
            pass
        try:
            page.get_by_text(text, exact=False).first.click(timeout=2_000)
            return
        except Exception:
            pass
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass


def _accept_terms_if_present(page: Any) -> None:
    for selector in ('input[type="checkbox"]', '.ant-checkbox-input', '[role="checkbox"]'):
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=1_000):
                locator.check(timeout=1_000)
                return
        except Exception:
            pass
        try:
            locator = page.locator(selector).first
            if locator.count():
                locator.click(timeout=1_000)
                return
        except Exception:
            pass
    try:
        page.get_by_text("已阅读并同意", exact=False).click(timeout=1_000)
    except Exception:
        pass


def perform_login(page: Any, settings: DataEyeSettings, wait_timeout_ms: int = 300_000) -> None:
    page.goto(settings.home_url, wait_until="domcontentloaded")
    page.wait_for_timeout(1_000)
    if is_logged_in(page, timeout_ms=5_000):
        return

    form_filled = _fill_login_form(page, settings)
    if form_filled:
        _accept_terms_if_present(page)
        _click_login_button(page)

    if is_logged_in(page, timeout_ms=20_000):
        return

    print("DataEye login needs manual completion. Finish CAPTCHA/verification in the opened browser.")
    if not is_logged_in(page, timeout_ms=wait_timeout_ms):
        raise TimeoutError("Timed out waiting for DataEye login to complete.")


class DataEyeSession:
    def __init__(self, settings: DataEyeSettings, headed: bool = False) -> None:
        self.settings = settings
        self.headed = headed

    def open(self, playwright: Any) -> tuple[Any, Any, Any]:
        if self.settings.storage_state.exists():
            browser = playwright.chromium.launch(headless=not self.headed)
            context = browser.new_context(storage_state=str(self.settings.storage_state))
            page = context.new_page()
            page.goto(self.settings.home_url, wait_until="domcontentloaded")
            if is_logged_in(page):
                return browser, context, page
            context.close()
            browser.close()

        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        perform_login(page, self.settings)
        self.settings.storage_state.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(self.settings.storage_state))
        return browser, context, page
