# -*- coding: utf-8 -*-
"""测试夹具：用独立的数据目录，避免污染真实数据。"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_DATA_DIR = tempfile.mkdtemp(prefix="xinyu-test-")
os.environ["XINYU_DATA_DIR"] = _DATA_DIR
os.environ["XINYU_LLM_PROVIDER"] = "mock"
os.environ["XINYU_DEBUG"] = "1"

import pytest  # noqa: E402

from backend.app.db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    """建表并保证测试结束后清理。"""
    init_db()
    yield
    shutil.rmtree(_DATA_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    """FastAPI 测试客户端。"""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def user(client):
    """一个已完成年龄验证的用户。"""
    response = client.post("/api/users", json={"nickname": "小满", "age_verified": True})
    assert response.status_code == 200
    return response.json()


@pytest.fixture()
def character(client, user):
    """一个刚创建的角色。"""
    response = client.post("/api/characters", json={
        "user_id": user["id"],
        "name": "沈屿",
        "relation_type": "boyfriend",
        "template_key": "gentle_healer",
        "appearance": {"style": "白衬衫", "vibe": "温柔", "hairstyle": "soft"},
    })
    assert response.status_code == 200
    return response.json()
