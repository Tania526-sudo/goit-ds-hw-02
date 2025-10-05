import argparse
import random
import sqlite3
from pathlib import Path
from faker import Faker

DEFAULT_STATUSES = ["new", "in progress", "completed"]

def enable_fks(conn: sqlite3.Connection):
    conn.execute("PRAGMA foreign_keys = ON;")

def bootstrap_schema(conn: sqlite3.Connection, ddl_path: Path):
    sql = ddl_path.read_text(encoding="utf-8")
    conn.executescript(sql)

def seed_status(conn: sqlite3.Connection):
    conn.executemany(
        "INSERT OR IGNORE INTO status(name) VALUES (?);",
        [(s,) for s in DEFAULT_STATUSES]
    )

def seed_users(conn: sqlite3.Connection, n: int, fake: Faker):
    rows = []
    for _ in range(n):
        name = fake.name()
        email = fake.unique.email().lower()
        rows.append((name, email))
    conn.executemany("INSERT INTO users(fullname, email) VALUES (?, ?);", rows)

def get_ids(conn: sqlite3.Connection, table: str):
    cur = conn.execute(f"SELECT id FROM {table};")
    return [r[0] for r in cur.fetchall()]

def seed_tasks(conn: sqlite3.Connection, n: int, fake: Faker):
    user_ids   = get_ids(conn, "users")
    status_ids = get_ids(conn, "status")
    if not user_ids or not status_ids:
        raise RuntimeError("Users/status must be populated before tasks")

    #  ~25–35% of users will not receive any tasks
    users_with_tasks = set(random.sample(
        user_ids,
        k=max(1, int(len(user_ids) * random.uniform(0.65, 0.75)))
    ))

    # Circular iterator
    def status_round_robin():
        while True:
            for sid in status_ids:
                yield sid
    rr = status_round_robin()

    rows = []
    for i in range(n):
        user_id = random.choice(list(users_with_tasks))
        status_id = next(rr)
        title = fake.sentence(nb_words=4).rstrip(".")
        # 20% — None
        r = random.random()
        if r < 0.2:
            desc = None
        elif r < 0.3:
            desc = ""
        else:
            desc = fake.paragraph(nb_sentences=2)
        rows.append((title, desc, status_id, user_id))

    conn.executemany(
        "INSERT INTO tasks(title, description, status_id, user_id) VALUES (?, ?, ?, ?);",
        rows
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="tm_alt.db")
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--tasks", type=int, default=40)
    parser.add_argument("--ddl", default="sql/create_tables_alt.sql")
    args = parser.parse_args()

    fake = Faker()
    random.seed(1337)
    Faker.seed(1337)

    Path("sql").mkdir(exist_ok=True)

    with sqlite3.connect(args.db) as conn:
        enable_fks(conn)
        bootstrap_schema(conn, Path(args.ddl))
        seed_status(conn)
        seed_users(conn, args.users, fake)
        seed_tasks(conn, args.tasks, fake)
        conn.commit()

    print(f"Seeded alternative dataset  {Path(args.db).resolve()}")

if __name__ == "__main__":
    main()