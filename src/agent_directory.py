#!/usr/bin/env python3
"""BlackRoad Agent Directory — registry, capability index, skill matching, routing, availability."""

from __future__ import annotations
import argparse, hashlib, json, os, random, sqlite3, sys, time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

R="\033[0;31m"; G="\033[0;32m"; Y="\033[1;33m"; C="\033[0;36m"
B="\033[0;34m"; M="\033[0;35m"; W="\033[1;37m"; DIM="\033[2m"; NC="\033[0m"; BOLD="\033[1m"

DB_PATH = Path(os.environ.get("DIR_DB", Path.home() / ".blackroad" / "agent_directory.db"))

@dataclass
class AgentProfile:
    agent_id: str
    name: str
    agent_type: str
    description: str
    model: str
    version: str
    owner: str
    tags: str
    registered_at: str
    last_updated: str
    active: bool = True

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

@dataclass
class Capability:
    cap_id: str
    agent_id: str
    category: str
    name: str
    description: str
    proficiency: int
    verified: bool
    added_at: str

    def score(self):
        return self.proficiency * (1.2 if self.verified else 1.0)

@dataclass
class SkillMatch:
    match_id: str
    query: str
    agent_id: str
    score: float
    matched_caps: str
    matched_at: str

    def cap_list(self):
        try: return json.loads(self.matched_caps)
        except: return []

@dataclass
class RoutingRule:
    rule_id: str
    name: str
    match_type: str
    match_value: str
    target_agent_id: str
    priority: int
    active: bool
    created_at: str

@dataclass
class Availability:
    avail_id: str
    agent_id: str
    status: str
    load_pct: float
    max_tasks: int
    current_tasks: int
    reserved_until: str
    updated_at: str

    def is_available(self):
        if self.status not in ("online","idle"): return False
        if self.current_tasks >= self.max_tasks: return False
        if self.reserved_until:
            try:
                if datetime.fromisoformat(self.reserved_until) > datetime.utcnow():
                    return False
            except: pass
        return True

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn

def _init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS agent_profiles (
        agent_id    TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        agent_type  TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        model       TEXT NOT NULL DEFAULT 'llama3.2',
        version     TEXT NOT NULL DEFAULT '1.0.0',
        owner       TEXT NOT NULL DEFAULT 'blackroad',
        tags        TEXT NOT NULL DEFAULT '',
        registered_at TEXT NOT NULL,
        last_updated  TEXT NOT NULL,
        active      INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS capabilities (
        cap_id      TEXT PRIMARY KEY,
        agent_id    TEXT NOT NULL,
        category    TEXT NOT NULL,
        name        TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        proficiency INTEGER NOT NULL DEFAULT 50,
        verified    INTEGER NOT NULL DEFAULT 0,
        added_at    TEXT NOT NULL,
        FOREIGN KEY (agent_id) REFERENCES agent_profiles(agent_id)
    );
    CREATE TABLE IF NOT EXISTS skill_matches (
        match_id     TEXT PRIMARY KEY,
        query        TEXT NOT NULL,
        agent_id     TEXT NOT NULL,
        score        REAL NOT NULL DEFAULT 0,
        matched_caps TEXT NOT NULL DEFAULT '[]',
        matched_at   TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS routing_rules (
        rule_id        TEXT PRIMARY KEY,
        name           TEXT NOT NULL,
        match_type     TEXT NOT NULL,
        match_value    TEXT NOT NULL,
        target_agent_id TEXT NOT NULL,
        priority       INTEGER NOT NULL DEFAULT 50,
        active         INTEGER NOT NULL DEFAULT 1,
        created_at     TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS availability (
        avail_id       TEXT PRIMARY KEY,
        agent_id       TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'offline',
        load_pct       REAL NOT NULL DEFAULT 0,
        max_tasks      INTEGER NOT NULL DEFAULT 10,
        current_tasks  INTEGER NOT NULL DEFAULT 0,
        reserved_until TEXT NOT NULL DEFAULT '',
        updated_at     TEXT NOT NULL,
        FOREIGN KEY (agent_id) REFERENCES agent_profiles(agent_id)
    );
    """)
    conn.commit()

def _now(): return datetime.utcnow().isoformat(timespec="seconds")
def _uid(p=""): return p + hashlib.sha1(f"{p}{time.time_ns()}{random.random()}".encode()).hexdigest()[:10]

SEED_DATA = [
    ("lucidia",  "LUCIDIA",  "reasoning", "Philosophical reasoning engine", "qwen2.5:7b",
     "reasoning,synthesis,planning,strategy,deep-analysis"),
    ("alice",    "ALICE",    "worker",    "Task executor and router",        "llama3.2:3b",
     "execution,automation,routing,deploy,ci-cd"),
    ("octavia",  "OCTAVIA",  "worker",    "Infrastructure operator",         "mistral:7b",
     "devops,monitoring,infra,docker,kubernetes"),
    ("prism",    "PRISM",    "analytics", "Data pattern analyst",            "qwen2.5:7b",
     "analytics,patterns,ml,reporting,visualization"),
    ("echo",     "ECHO",     "memory",    "Knowledge librarian",             "llama3.2:3b",
     "memory,recall,context,search,indexing"),
    ("cipher",   "CIPHER",   "security",  "Security guardian",               "mistral:7b",
     "security,auth,encryption,scanning,compliance"),
]

CAPABILITY_SEEDS = {
    "lucidia": [("reasoning","Deep Reasoning","Multi-step logical inference",95,True),
                ("synthesis","Knowledge Synthesis","Cross-domain synthesis",88,True),
                ("strategy","Strategic Planning","Long-horizon planning",80,False)],
    "alice":   [("execution","Task Execution","Reliable task runner",90,True),
                ("routing","Smart Routing","Intelligent task routing",85,True),
                ("automation","Workflow Automation","Complex automations",78,False)],
    "octavia": [("devops","DevOps","Full DevOps lifecycle",92,True),
                ("monitoring","System Monitoring","Real-time monitoring",88,True),
                ("infra","Infrastructure","IaC and provisioning",82,False)],
    "prism":   [("analytics","Data Analytics","Statistical analysis",90,True),
                ("patterns","Pattern Recognition","ML pattern detection",87,True),
                ("reporting","Report Generation","Automated reports",75,False)],
    "echo":    [("memory","Memory Management","Persistent memory store",94,True),
                ("search","Semantic Search","Vector similarity search",86,True),
                ("context","Context Management","Session context",79,False)],
    "cipher":  [("security","Security Scanning","Vuln scanning",93,True),
                ("auth","Authentication","OAuth2/JWT management",89,True),
                ("encryption","Data Encryption","AES/RSA encryption",84,True)],
}

def seed_demo(conn):
    if conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0] > 0:
        return
    now = _now()
    for aid, name, atype, desc, model, tags in SEED_DATA:
        conn.execute("INSERT INTO agent_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (aid, name, atype, desc, model, "1.0.0", "blackroad", tags, now, now, 1))
        for cat, cname, cdesc, prof, verified in CAPABILITY_SEEDS.get(aid, []):
            conn.execute("INSERT INTO capabilities VALUES (?,?,?,?,?,?,?,?)",
                         (_uid("cap"), aid, cat, cname, cdesc, prof, int(verified), now))
        status = random.choice(["online","idle","busy"])
        cur = random.randint(0, 8)
        conn.execute("INSERT INTO availability VALUES (?,?,?,?,?,?,?,?)",
                     (_uid("av"), aid, status, round(cur/10*100,1), 10, cur, "", now))
    for i, (aid, _, _, _, _, _) in enumerate(SEED_DATA):
        if i < 3:
            conn.execute("INSERT INTO routing_rules VALUES (?,?,?,?,?,?,?,?)",
                         (_uid("rr"), f"Route to {aid}", "type",
                          SEED_DATA[i][2], aid, 50 + i*10, 1, now))
    conn.commit()

def register_agent(conn, agent_id, name, agent_type, description="", model="llama3.2", tags=""):
    now = _now()
    if conn.execute("SELECT 1 FROM agent_profiles WHERE agent_id=?", (agent_id,)).fetchone():
        raise ValueError(f"Agent '{agent_id}' already registered")
    p = AgentProfile(agent_id=agent_id, name=name, agent_type=agent_type,
                     description=description, model=model, version="1.0.0",
                     owner="cli", tags=tags, registered_at=now, last_updated=now)
    conn.execute("INSERT INTO agent_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (p.agent_id, p.name, p.agent_type, p.description, p.model,
                  p.version, p.owner, p.tags, p.registered_at, p.last_updated, int(p.active)))
    conn.execute("INSERT INTO availability VALUES (?,?,?,?,?,?,?,?)",
                 (_uid("av"), agent_id, "offline", 0.0, 10, 0, "", now))
    conn.commit()
    return p

def find_by_capability(conn, category=None, name_contains=None, min_proficiency=0):
    q = "SELECT c.*, p.name as agent_name FROM capabilities c JOIN agent_profiles p ON c.agent_id=p.agent_id WHERE 1=1"
    params = []
    if category:
        q += " AND c.category=?"; params.append(category)
    if name_contains:
        q += " AND c.name LIKE ?"; params.append(f"%{name_contains}%")
    if min_proficiency:
        q += " AND c.proficiency>=?"; params.append(min_proficiency)
    q += " ORDER BY c.proficiency DESC"
    return [dict(r) for r in conn.execute(q, params).fetchall()]

def match_skills(conn, query_skills: list[str]) -> list[SkillMatch]:
    query_lower = [s.lower() for s in query_skills]
    all_caps = conn.execute("SELECT * FROM capabilities").fetchall()
    scores: dict[str, dict] = {}
    for row in all_caps:
        aid = row["agent_id"]
        cap_text = (row["name"] + " " + row["category"] + " " + row["description"]).lower()
        for qs in query_lower:
            if qs in cap_text:
                if aid not in scores:
                    scores[aid] = {"score": 0.0, "caps": []}
                scores[aid]["score"] += row["proficiency"] * (1.2 if row["verified"] else 1.0)
                scores[aid]["caps"].append(row["name"])
    results = []
    now = _now()
    for aid, data in sorted(scores.items(), key=lambda x: -x[1]["score"])[:5]:
        m = SkillMatch(match_id=_uid("sm"), query=",".join(query_skills),
                       agent_id=aid, score=round(data["score"], 2),
                       matched_caps=json.dumps(data["caps"]), matched_at=now)
        conn.execute("INSERT INTO skill_matches VALUES (?,?,?,?,?,?)",
                     (m.match_id, m.query, m.agent_id, m.score, m.matched_caps, m.matched_at))
        results.append(m)
    conn.commit()
    return results

def route_task(conn, task_type=None, task_tag=None) -> Optional[dict]:
    q = "SELECT r.*, p.name FROM routing_rules r JOIN agent_profiles p ON r.target_agent_id=p.agent_id WHERE r.active=1"
    params = []
    if task_type:
        q += " AND (r.match_type='type' AND r.match_value=?)"; params.append(task_type)
    q += " ORDER BY r.priority DESC LIMIT 1"
    row = conn.execute(q, params).fetchone()
    return dict(row) if row else None

def update_availability(conn, agent_id, status, current_tasks=None, load_pct=None):
    if not conn.execute("SELECT 1 FROM agent_profiles WHERE agent_id=?", (agent_id,)).fetchone():
        raise ValueError(f"Agent '{agent_id}' not found")
    now = _now()
    updates = ["status=?", "updated_at=?"]; vals: list = [status, now]
    if current_tasks is not None:
        updates.append("current_tasks=?"); vals.append(current_tasks)
    if load_pct is not None:
        updates.append("load_pct=?"); vals.append(load_pct)
    vals.append(agent_id)
    conn.execute(f"UPDATE availability SET {', '.join(updates)} WHERE agent_id=?", vals)
    conn.commit()

def list_available(conn) -> list[Availability]:
    rows = conn.execute("SELECT * FROM availability").fetchall()
    avails = [Availability(**dict(r)) for r in rows]
    return [a for a in avails if a.is_available()]

def _header(title):
    print(f"\n{B}{'─'*62}{NC}\n{W}{BOLD}  {title}{NC}\n{B}{'─'*62}{NC}")

STATUS_COL = {"online":G,"idle":C,"busy":Y,"offline":R}

def cmd_register(args):
    conn = get_conn()
    try:
        p = register_agent(conn, args.agent_id, args.name, args.type,
                           description=args.description or "", model=args.model or "llama3.2",
                           tags=args.tags or "")
        _header("Agent Registered")
        print(f"  {G}✓{NC} ID: {W}{p.agent_id}{NC}  Name: {p.name}  Type: {p.agent_type}")
        print(f"  {C}→{NC} Model: {p.model}  Tags: {p.tags}")
        print()
    except ValueError as e:
        print(f"{R}✗ {e}{NC}", file=sys.stderr); sys.exit(1)

def cmd_find(args):
    conn = get_conn(); seed_demo(conn)
    results = find_by_capability(conn, category=args.category,
                                  name_contains=args.name, min_proficiency=args.min_prof or 0)
    _header(f"Capability Search  [{len(results)} found]")
    for r in results[:20]:
        vbadge = f"{G}[verified]{NC}" if r["verified"] else f"{DIM}[unverified]{NC}"
        print(f"  {W}{r['agent_name']:<12}{NC}  {r['category']:<14}  {r['name']:<24}  "
              f"prof:{Y}{r['proficiency']}{NC}  {vbadge}")
    print()

def cmd_match(args):
    conn = get_conn(); seed_demo(conn)
    skills = [s.strip() for s in args.skills.split(",")]
    matches = match_skills(conn, skills)
    _header(f"Skill Match: '{args.skills}'  [{len(matches)} results]")
    for m in matches:
        print(f"  {G}{'●':>2}{NC} {m.agent_id:<12}  score:{Y}{m.score:>8.1f}{NC}  "
              f"caps: {C}{', '.join(m.cap_list())}{NC}")
    if not matches:
        print(f"  {DIM}No matching agents found.{NC}")
    print()

def cmd_route(args):
    conn = get_conn(); seed_demo(conn)
    rule = route_task(conn, task_type=args.task_type)
    _header("Routing Decision")
    if rule:
        print(f"  {G}✓{NC} Route to: {W}{rule['target_agent_id']}{NC}  ({rule['name']})")
        print(f"  {C}→{NC} Priority: {rule['priority']}  Match: {rule['match_type']}={rule['match_value']}")
    else:
        print(f"  {Y}⚠ No routing rule matched. Using default.{NC}")
    print()

def cmd_update(args):
    conn = get_conn(); seed_demo(conn)
    try:
        update_availability(conn, args.agent_id, args.status,
                            current_tasks=args.tasks, load_pct=args.load)
        print(f"{G}✓{NC} Updated {W}{args.agent_id}{NC} → status:{args.status}")
    except ValueError as e:
        print(f"{R}✗ {e}{NC}", file=sys.stderr); sys.exit(1)

def cmd_list(args):
    conn = get_conn(); seed_demo(conn)
    rows = conn.execute("""
        SELECT p.*, a.status, a.load_pct, a.current_tasks, a.max_tasks
        FROM agent_profiles p LEFT JOIN availability a ON p.agent_id=a.agent_id
        WHERE p.active=1 ORDER BY p.name
    """).fetchall()
    _header(f"Agent Directory  [{len(rows)} agents]")
    for r in rows:
        sc = STATUS_COL.get(r["status"] or "offline", NC)
        print(f"  {W}{r['name']:<10}{NC}  {DIM}{r['agent_id']:<10}{NC}  "
              f"{r['agent_type']:<12}  {sc}{r['status'] or 'offline':<8}{NC}  "
              f"load:{r['load_pct'] or 0:.0f}%  {r['current_tasks'] or 0}/{r['max_tasks'] or 10} tasks")
    print()

def build_parser():
    p = argparse.ArgumentParser(prog="agent-directory",
                                description=f"{W}BlackRoad Agent Directory{NC}")
    sub = p.add_subparsers(dest="command", required=True)
    pr = sub.add_parser("register", help="Register a new agent")
    pr.add_argument("agent_id"); pr.add_argument("name"); pr.add_argument("--type", default="worker")
    pr.add_argument("--description"); pr.add_argument("--model"); pr.add_argument("--tags")
    pr.set_defaults(func=cmd_register)
    pf = sub.add_parser("find", help="Find agents by capability")
    pf.add_argument("--category"); pf.add_argument("--name"); pf.add_argument("--min-prof", dest="min_prof", type=int)
    pf.set_defaults(func=cmd_find)
    pm = sub.add_parser("match", help="Match agents to skills")
    pm.add_argument("skills", help="Comma-separated skills")
    pm.set_defaults(func=cmd_match)
    pro = sub.add_parser("route", help="Route task to best agent")
    pro.add_argument("--task-type", dest="task_type")
    pro.set_defaults(func=cmd_route)
    pu = sub.add_parser("update", help="Update agent availability")
    pu.add_argument("agent_id"); pu.add_argument("status", choices=["online","idle","busy","offline"])
    pu.add_argument("--tasks", type=int); pu.add_argument("--load", type=float)
    pu.set_defaults(func=cmd_update)
    pl = sub.add_parser("list", help="List all agents")
    pl.set_defaults(func=cmd_list)
    return p

def main():
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
