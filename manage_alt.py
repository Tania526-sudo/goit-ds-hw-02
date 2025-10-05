# -*- coding: utf-8 -*-

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_DB = "tm_alt.db"

# ---- utilities ----

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def print_table(rows: Sequence[sqlite3.Row]) -> None:
    if not rows:
        print("Nothing found.")
        return
    headers = rows[0].keys()
    # column widths
    widths = {h: max(len(h), *(len(str(r[h])) if r[h] is not None else 0 for r in rows)) for h in headers}
    # header
    line = " | ".join(f"{h:<{widths[h]}}" for h in headers)
    print(line)
    print("-" * len(line))
    # rows
    for r in rows:
        print(" | ".join(f"{str(r[h]) if r[h] is not None else '':<{widths[h]}}" for h in headers))

def write_csv(rows: Sequence[sqlite3.Row], path: str) -> None:
    if not rows:
        # create an empty file with unknown header - skip: no sense
        Path(path).write_text("", encoding="utf-8")
        print(f"Saved empty CSV  {path}")
        return
    headers = rows[0].keys()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in headers})
    print(f"CSV saved  {path}")

def status_id_by_name(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("SELECT id FROM status WHERE name = ?", (name,))
    row = cur.fetchone()
    if not row:
        # suggest available statuses
        cur2 = conn.execute("SELECT name FROM status ORDER BY name;")
        existing = [r[0] for r in cur2.fetchall()]
        raise SystemExit(f"Status '{name}' not found. Available: {existing}")
    return row["id"]

def ensure_user_exists(conn: sqlite3.Connection, uid: int) -> None:
    cur = conn.execute("SELECT id, fullname, email FROM users WHERE id = ?", (uid,))
    if not cur.fetchone():
        raise SystemExit(f"User id={uid} not found.")

def ensure_task_exists(conn: sqlite3.Connection, task_id: int) -> None:
    cur = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not cur.fetchone():
        raise SystemExit(f"Task id={task_id} not found.")

# ---- commands ----

def cmd_list_inprogress(conn: sqlite3.Connection, limit: int | None, csv_path: str | None) -> None:
    sql = """
    SELECT t.id AS task_id, t.title, u.fullname AS user, u.email, t.created_at, t.updated_at
    FROM tasks t
    JOIN status s ON s.id = t.status_id
    JOIN users  u ON u.id = t.user_id
    WHERE s.name = 'in progress'
    ORDER BY t.updated_at DESC, t.id DESC
    """
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    print_table(rows)
    if csv_path:
        write_csv(rows, csv_path)

def cmd_add_task(conn: sqlite3.Connection, uid: int, title: str, desc: str | None, status_name: str | None) -> None:
    ensure_user_exists(conn, uid)
    if status_name is None:
        status_name = "new"
    sid = status_id_by_name(conn, status_name)
    conn.execute(
        "INSERT INTO tasks(title, description, status_id, user_id) VALUES (?, ?, ?, ?);",
        (title, desc, sid, uid)
    )
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
    print(f"Added task id={new_id} for user id={uid} (status: {status_name})")

def cmd_update_status(conn: sqlite3.Connection, task_id: int, status_name: str) -> None:
    ensure_task_exists(conn, task_id)
    sid = status_id_by_name(conn, status_name)
    conn.execute(
        "UPDATE tasks SET status_id = ? WHERE id = ?;",
        (sid, task_id)
    )
    conn.commit()
    print(f"Updated task id={task_id} → '{status_name}'")

def cmd_users_without_tasks(conn: sqlite3.Connection, csv_path: str | None) -> None:
    sql = """
    SELECT u.id, u.fullname, u.email, u.created_at
    FROM users u
    WHERE NOT EXISTS (SELECT 1 FROM tasks t WHERE t.user_id = u.id)
    ORDER BY u.fullname;
    """
    rows = conn.execute(sql).fetchall()
    print_table(rows)
    if csv_path:
        write_csv(rows, csv_path)

# ---- main ----

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Task Manager CLI (alternative)")
    p.add_argument("--db", default=DEFAULT_DB, help=f"Path to SQLite DB (default: {DEFAULT_DB})")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list-inprogress", help="Show tasks in status 'in progress'")
    sp.add_argument("--limit", type=int, default=None, help="Max. number of rows")
    sp.add_argument("--csv", dest="csv_path", help="Save result to CSV")

    sp = sub.add_parser("add-task", help="Add a new task")
    sp.add_argument("--uid", type=int, required=True, help="User ID")
    sp.add_argument("--title", required=True, help="Task title")
    sp.add_argument("--desc", default=None, help="Description (optional)")
    sp.add_argument("--status", dest="status_name", default=None, help="Status ('new'| 'in progress' | 'completed')")

    sp = sub.add_parser("update-status", help="Update task status")
    sp.add_argument("--task-id", type=int, required=True, help="Task ID")
    sp.add_argument("--status", dest="status_name", required=True, help="New status")

    sp = sub.add_parser("users-without-tasks", help="Users without any tasks")
    sp.add_argument("--csv", dest="csv_path", help="Save result to CSV")

    return p

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not Path(args.db).exists():
        print(f"DB not found: {args.db}\nPrepare it using seed.py", file=sys.stderr)
        return 2

    with connect(args.db) as conn:
        if args.cmd == "list-inprogress":
            cmd_list_inprogress(conn, args.limit, args.csv_path)
        elif args.cmd == "add-task":
            cmd_add_task(conn, args.uid, args.title, args.desc, args.status_name)
        elif args.cmd == "update-status":
            cmd_update_status(conn, args.task_id, args.status_name)
        elif args.cmd == "users-without-tasks":
            cmd_users_without_tasks(conn, args.csv_path)
        else:
            parser.error("Unknown command")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
