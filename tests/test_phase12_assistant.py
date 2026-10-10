from fastapi.testclient import TestClient

from fsp_market.main import app

client = TestClient(app)


def ask(q: str, role: str | None = None) -> dict:
    r = client.post("/api/assistant/ask", json={"question": q, "role": role})
    assert r.status_code == 200
    return r.json()


def test_assistant_answers_core_topics_without_ai():
    assert "Core" in ask("Как проходит оценка?", "candidate")["answer"] or "11 заданий" in ask("Как проходит оценка?")["answer"]
    assert "7 дней" in ask("Что если я не прошёл тест, можно пересдать?")["answer"]
    assert "приглашен" in ask("Когда откроются контакты кандидата?")["answer"].lower()
    assert ask("Что значит соответствие этой потребности?", "employer")["topic"].startswith("Почему")
    assert ask("подуровни M2")["topic"] == "Подуровни J1–S3"


def test_assistant_fallback_and_validation():
    out = ask("квантовая хромодинамика")
    assert out["matched"] is False and out["related"] == []
    assert client.post("/api/assistant/ask", json={"question": "x"}).status_code == 422
    assert client.get("/api/assistant/suggestions?role=employer").json()["suggestions"]
