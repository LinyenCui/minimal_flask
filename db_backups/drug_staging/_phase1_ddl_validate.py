#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 1 DDL syntax validation via transaction ROLLBACK on LOCAL dispatch_db.
Runs CREATE TABLE inside ONE transaction, validates, then ROLLBACK -> leaves nothing.
NEVER commits. LOCAL only (refuses non-localhost/dispatch_db). No production. No data DML."""
import re, sys
from urllib.parse import urlparse
import psycopg2

SQL_FILE = "/Users/linyancui/minimal_flask/db_backups/drug_staging/create_prescription_import_phase1_tables.sql"
TABLES = ["prescription_import_batches", "prescription_customer_candidates",
          "prescription_diagnosis_candidates", "prescription_drug_candidates",
          "prescription_import_review_actions", "prescription_drug_diagnosis_link_candidates"]
FORBIDDEN_COLS = ["national_id", "phone", "chart_no", "contact_phone", "medical_record_no"]

def local_dsn():
    for line in open("/Users/linyancui/minimal_flask/.env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return re.sub(r"\+psycopg2?", "", line.split("=", 1)[1].strip().strip('"').strip("'"))
    raise SystemExit("no DATABASE_URL")

def regexists(cur, t):
    cur.execute("SELECT to_regclass(%s)", (f"public.{t}",)); return cur.fetchone()[0] is not None

dsn = local_dsn(); u = urlparse(dsn)
host, port, db, user = (u.hostname or ""), (u.port or 5432), u.path.lstrip("/"), (u.username or "")
print(f"DB target: host={host} port={port} database={db} user={user}")
if host not in ("localhost", "127.0.0.1") or db != "dispatch_db":
    raise SystemExit(f"[ABORT] 非本機 dispatch_db（拒絕執行）：host={host} db={db}")
print("target OK = localhost:5432/dispatch_db (NOT production)\n")

conn = psycopg2.connect(dsn, connect_timeout=8)
conn.autocommit = False           # 單一 transaction，最後 rollback
cur = conn.cursor()
report = {}

# 2) pre-check: 6 表不存在
pre = {t: regexists(cur, t) for t in TABLES}
report["pre_exists"] = pre
print("PRE (expect all False):", {t: pre[t] for t in TABLES})
if any(pre.values()):
    conn.rollback(); conn.close()
    raise SystemExit("[ABORT] 有目標表已存在，停止（不覆蓋）")

# 3) 執行 SQL（移除嵌入的 BEGIN;/COMMIT;，改由本連線單一 transaction 控制）
raw = open(SQL_FILE, encoding="utf-8").read()
ddl = "\n".join(l for l in raw.splitlines() if not re.match(r"^\s*(BEGIN|COMMIT)\s*;\s*$", l, re.I))
try:
    cur.execute(ddl)
    report["ddl_executed"] = True
    print("DDL executed inside transaction: OK")
except Exception as e:
    conn.rollback(); conn.close()
    print(f"[FAIL] DDL 執行錯誤：{e}")
    raise SystemExit(1)

# 4) 交易內驗證
mid = {t: regexists(cur, t) for t in TABLES}
report["created"] = mid
print("CREATED (expect all True):", {t: mid[t] for t in TABLES})

# constraints per table (c=CHECK, f=FK, p=PK)
cur.execute("""
   SELECT rel.relname, con.contype, count(*) FROM pg_constraint con
   JOIN pg_class rel ON rel.oid=con.conrelid
   JOIN pg_namespace n ON n.oid=rel.relnamespace
   WHERE n.nspname='public' AND rel.relname = ANY(%s)
   GROUP BY rel.relname, con.contype ORDER BY rel.relname, con.contype
""", (TABLES,))
cons = {}
for relname, contype, c in cur.fetchall():
    cons.setdefault(relname, {})[contype] = c
report["constraints"] = cons
print("\nconstraints per table (c=CHECK f=FK p=PK):")
for t in TABLES:
    print(f"  {t}: {cons.get(t,{})}")

# indexes per table
cur.execute("SELECT tablename, count(*) FROM pg_indexes WHERE schemaname='public' AND tablename = ANY(%s) GROUP BY tablename", (TABLES,))
idx = {r[0]: r[1] for r in cur.fetchall()}
report["indexes"] = idx
print("\nindexes per table:", {t: idx.get(t, 0) for t in TABLES})

# generated column
cur.execute("""SELECT is_generated, generation_expression FROM information_schema.columns
               WHERE table_schema='public' AND table_name='prescription_drug_candidates'
               AND column_name='effective_nhi_drug_code'""")
g = cur.fetchone()
report["effective_generated"] = g
print("\neffective_nhi_drug_code:", g, "(expect is_generated=ALWAYS)")

# forbidden columns scan
cur.execute("""SELECT table_name, column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name = ANY(%s) AND column_name = ANY(%s)""",
            (TABLES, FORBIDDEN_COLS))
forb = cur.fetchall()
report["forbidden_cols"] = forb
print("forbidden columns found (expect none):", forb or "NONE")

# sample: customer gender CHECK + match_status CHECK present?
cur.execute("""SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con
   JOIN pg_class rel ON rel.oid=con.conrelid WHERE rel.relname='prescription_customer_candidates'
   AND con.contype='c' ORDER BY con.conname""")
print("\nprescription_customer_candidates CHECK defs:")
for name, d in cur.fetchall():
    print(f"  {name}: {d}")

# 5) ROLLBACK
conn.rollback()
print("\n>>> ROLLBACK done")

# 6) post-check: 6 表不存在（rollback 後）
post = {t: regexists(cur, t) for t in TABLES}
report["post_exists"] = post
print("POST (expect all False):", {t: post[t] for t in TABLES})
conn.close()

passed = (not any(pre.values()) and all(mid.values()) and not any(post.values())
          and not forb and g and g[0] == "ALWAYS")
print("\nVALIDATION_PASSED =", passed)
