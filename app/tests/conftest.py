"""ایزوله‌سازی دیتابیس در تست‌ها: همه سرورهای تستی به SQLite موقت می‌روند."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_db(tmp_path_factory):
    os.environ["WORKBENCH_DB"] = str(tmp_path_factory.mktemp("wb") / "test.db")
    import server
    server._STORE = None
    yield
    os.environ.pop("WORKBENCH_DB", None)
