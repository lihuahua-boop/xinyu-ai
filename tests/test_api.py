# -*- coding: utf-8 -*-
"""HTTP 接口测试。"""


def test_health(client):
    """健康检查。"""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_meta_endpoints(client):
    """前端需要的可选项都要能拿到。"""
    assert client.get("/api/meta/templates").json()["items"]
    assert client.get("/api/meta/relation-types").json()["items"]
    assert client.get("/api/meta/persona-params").json()["items"]
    assert client.get("/api/meta/interview").json()["items"]
    assert client.get("/api/meta/appearance").json()["style"]
    assert client.get("/api/meta/stages").json()["items"]
    config = client.get("/api/meta/config").json()
    assert config["app_name"]


def test_user_flow(client):
    """注册 → 读回 → 更新画像。"""
    created = client.post("/api/users", json={"nickname": "阿念", "age_verified": True})
    assert created.status_code == 200
    user_id = created.json()["id"]

    fetched = client.get("/api/users/%s" % user_id)
    assert fetched.json()["nickname"] == "阿念"

    updated = client.patch("/api/users/%s/profile" % user_id,
                           json={"display_name": "念念", "call_me": "念念"})
    assert updated.json()["profile"]["call_me"] == "念念"


def test_missing_user_returns_404(client):
    """不存在的用户返回结构化错误。"""
    response = client.get("/api/users/user_not_exist")
    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


def test_character_creation_and_detail(client, character):
    """创建后能看到人格标签、记忆统计与关系状态。"""
    assert character["name"] == "沈屿"
    assert character["persona_tags"]
    assert character["relationship"]["stage"] == "stranger"
    assert character["memory"]["total"] == 0

    detail = client.get("/api/characters/%s" % character["id"]).json()
    assert detail["template_label"] == "温柔治愈型"
    assert detail["avatar_url"].endswith("avatar.svg")


def test_character_list(client, user, character):
    """列表按用户过滤。"""
    response = client.get("/api/characters", params={"user_id": user["id"]})
    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


def test_update_persona_sliders(client, character):
    """调参要真的写进去。"""
    response = client.patch("/api/characters/%s" % character["id"],
                            json={"persona": {"humor": 90, "preachiness": 5}})
    assert response.status_code == 200
    assert response.json()["persona"]["humor"] == 90
    assert response.json()["persona"]["preachiness"] == 5


def test_avatar_is_svg(client, character):
    """头像是生成的 SVG。"""
    response = client.get("/api/characters/%s/avatar.svg" % character["id"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text


def test_interview_flow(client, character, user):
    """访谈问答要能改人格，并推进到下一题。"""
    response = client.post("/api/characters/%s/interview" % character["id"], json={
        "user_id": user["id"],
        "question_key": "comfort_style",
        "option_key": "comfort",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["interview"]["applied"]["key"] == "comfort"
    assert data["interview"]["progress"]["answered"] == 1
    assert data["interview"]["next_question"]["key"] == "tone"
    assert data["persona"]["preachiness"] < 50


def test_interview_bad_option(client, character, user):
    """非法选项要被拒绝。"""
    response = client.post("/api/characters/%s/interview" % character["id"], json={
        "user_id": user["id"],
        "question_key": "comfort_style",
        "option_key": "not_exists",
    })
    assert response.status_code == 400


def test_chat_endpoint(client, character, user):
    """聊天接口返回完整的结构化结果，前端靠它驱动界面。"""
    response = client.post("/api/characters/%s/chat" % character["id"], json={
        "user_id": user["id"],
        "text": "今天好累，感觉撑不住了",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["reply"]
    assert data["emotion"]["label"]
    assert "relationship" in data and "progress" in data["relationship"]
    assert data["meta"]["provider"]


def test_chat_rejects_empty(client, character, user):
    """空消息返回 400。"""
    response = client.post("/api/characters/%s/chat" % character["id"], json={
        "user_id": user["id"], "text": "",
    })
    assert response.status_code in (400, 422)


def test_messages_endpoint(client, character, user):
    """聊天记录按时间正序返回，并带上用到的记忆。"""
    client.post("/api/characters/%s/chat" % character["id"],
                json={"user_id": user["id"], "text": "我喜欢猫"})
    response = client.get("/api/characters/%s/messages" % character["id"])
    items = response.json()["items"]
    assert len(items) >= 2
    assert items[0]["role"] == "user"
    assert items[-1]["role"] == "assistant"


def test_history_expands_recalled_memories(client, character, user):
    """回看聊天记录时，「他想起」的卡片要有内容，不能只剩空壳。"""
    client.post("/api/characters/%s/chat" % character["id"],
                json={"user_id": user["id"], "text": "记住我下周三要面试，我很紧张"})
    client.post("/api/characters/%s/chat" % character["id"],
                json={"user_id": user["id"], "text": "你还记得我说过什么吗"})
    items = client.get("/api/characters/%s/messages" % character["id"]).json()["items"]
    assistant = [item for item in items if item["role"] == "assistant"]
    used = [memory for message in assistant for memory in message["memories_used"]]
    assert used
    assert all(memory.get("content") for memory in used)


def test_memory_endpoints(client, character, user):
    """记忆列表、手动添加、删除。"""
    client.post("/api/characters/%s/chat" % character["id"],
                json={"user_id": user["id"], "text": "我在上海工作，喜欢猫"})

    listing = client.get("/api/characters/%s/memories" % character["id"]).json()
    assert listing["stats"]["total"] >= 1
    assert listing["labels"]["basic"]

    created = client.post("/api/characters/%s/memories" % character["id"],
                          json={"category": "basic", "content": "用户养了一只叫团子的猫", "importance": 0.9})
    memory_id = created.json()["id"]
    assert created.json()["stats"]["total"] >= 2

    deleted = client.delete("/api/memories/%s" % memory_id)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_memory_bad_category(client, character):
    """非法类别要被拒绝。"""
    response = client.post("/api/characters/%s/memories" % character["id"],
                           json={"category": "unknown", "content": "x"})
    assert response.status_code == 400


def test_proactive_endpoint(client, character):
    """主动陪伴接口可用（是否真的有消息取决于时间与频控）。"""
    response = client.get("/api/characters/%s/proactive" % character["id"],
                          params={"materialize_now": 1})
    assert response.status_code == 200
    body = response.json()
    assert "history" in body and "created" in body


def test_relationship_endpoint(client, character):
    """关系接口。"""
    response = client.get("/api/characters/%s/relationship" % character["id"])
    body = response.json()
    assert body["stage_label"]
    assert body["progress"]["next_label"]


def test_static_index_served(client):
    """网页客户端要被挂载到根路径。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "心屿" in response.text
