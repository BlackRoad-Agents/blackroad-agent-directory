"""Tests for BlackRoad Agent Directory."""
import os, sys, pytest, json
from pathlib import Path

os.environ["DIR_DB"] = "/tmp/test_dir.db"
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from agent_directory import (
    get_conn, seed_demo, register_agent, find_by_capability,
    match_skills, route_task, update_availability, list_available,
    Capability, Availability, _now,
)

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "dir.db"
    monkeypatch.setenv("DIR_DB", str(db))
    import agent_directory
    agent_directory.DB_PATH = db
    yield

def test_seed_creates_six_agents():
    conn = get_conn(); seed_demo(conn)
    rows = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
    assert rows == 6

def test_register_new_agent():
    conn = get_conn()
    p = register_agent(conn, "nova", "NOVA", "creative", tags="creative,writing")
    assert p.agent_id == "nova"
    row = conn.execute("SELECT * FROM agent_profiles WHERE agent_id='nova'").fetchone()
    assert row is not None

def test_register_duplicate_raises():
    conn = get_conn(); seed_demo(conn)
    with pytest.raises(ValueError, match="already registered"):
        register_agent(conn, "lucidia", "LUCIDIA2", "reasoning")

def test_find_by_capability_category():
    conn = get_conn(); seed_demo(conn)
    results = find_by_capability(conn, category="security")
    assert len(results) >= 1
    assert all(r["category"] == "security" for r in results)

def test_match_skills_returns_ranked():
    conn = get_conn(); seed_demo(conn)
    matches = match_skills(conn, ["security", "encryption"])
    assert len(matches) >= 1
    assert matches[0].agent_id == "cipher"
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)

def test_update_availability():
    conn = get_conn(); seed_demo(conn)
    update_availability(conn, "alice", "busy", current_tasks=5, load_pct=50.0)
    row = conn.execute("SELECT * FROM availability WHERE agent_id='alice'").fetchone()
    assert row["status"] == "busy"
    assert row["current_tasks"] == 5

def test_availability_is_available():
    a = Availability(avail_id="x", agent_id="a", status="online",
                     load_pct=30.0, max_tasks=10, current_tasks=3,
                     reserved_until="", updated_at=_now())
    assert a.is_available() is True

def test_availability_full_not_available():
    a = Availability(avail_id="x", agent_id="a", status="online",
                     load_pct=100.0, max_tasks=5, current_tasks=5,
                     reserved_until="", updated_at=_now())
    assert a.is_available() is False

def test_capability_score():
    c = Capability(cap_id="x", agent_id="a", category="security", name="Scan",
                   description="", proficiency=80, verified=True, added_at=_now())
    assert c.score() == 80 * 1.2
