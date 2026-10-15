"""لایه‌ی مرورگر Selenium؛ فقط زمانی import می‌شود که اجرای واقعی لازم باشد."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, List, Optional

from . import selectors as sel


class BaleBrowser:
    """پوشش نازک روی Selenium برای ورود و خواندن/نوشتن پیام."""

    def __init__(self, profile_dir: str = "./.bale-profile", headless: bool = False,
                 timeout: int = 25) -> None:
        self.profile_dir = Path(profile_dir)
        self.headless = headless
        self.timeout = timeout
        self.driver: Any = None

    def start(self) -> Any:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise RuntimeError("Selenium نصب نیست: pip install selenium") from exc

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument(f"--user-data-dir={self.profile_dir.resolve()}")
        opts.add_argument("--no-first-run")
        opts.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(options=opts)
        self.driver.get(sel.LOGIN_URL)
        return self.driver

    def wait_login(self, poll: int = 5) -> None:
        """منتظر ورود دستی می‌ماند؛ وقتی صفحه‌ی چت آمد ادامه می‌دهد."""
        print("مرورگر باز شد. اگر لازم است، وارد حساب بله‌ات شو.")
        while True:
            try:
                if self.driver.find_elements("css selector", sel.MESSAGE_INPUT):
                    print("ورود تشخیص داده شد؛ شروع پردازش.")
                    return
            except Exception:
                pass
            time.sleep(poll)

    def open_chat(self, chat_name: str) -> bool:
        for el in self.driver.find_elements("css selector", sel.CHAT_LIST_ITEM):
            try:
                if chat_name in (el.text or ""):
                    el.click()
                    time.sleep(1)
                    return True
            except Exception:
                continue
        return False

    def read_messages(self, limit: int = 20) -> List[dict]:
        out: List[dict] = []
        for row in self.driver.find_elements("css selector", sel.MESSAGE_ROW)[-limit:]:
            try:
                text_el = row.find_elements("css selector", sel.MESSAGE_TEXT)
                text = (text_el[0].text if text_el else row.text) or ""
                if text.strip():
                    out.append({"text": text.strip(), "raw": row})
            except Exception:
                continue
        return out

    def send(self, text: str) -> bool:
        try:
            box = self.driver.find_elements("css selector", sel.MESSAGE_INPUT)[0]
            box.click()
            box.send_keys(text)
            buttons = self.driver.find_elements("css selector", sel.SEND_BUTTON)
            if buttons:
                buttons[0].click()
            else:
                from selenium.webdriver.common.keys import Keys
                box.send_keys(Keys.ENTER)
            return True
        except Exception as exc:
            print(f"ارسال ناموفق: {type(exc).__name__}: {exc}")
            return False

    def stop(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
