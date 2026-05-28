#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transaction-ROLLBACK validation of alter_drug_diagnosis_links_add_soft_delete.sql.
LOCAL ONLY. Runs the ALTERs inside ONE transaction, verifies, then ROLLBACK (no persisted change).
Strips the file's BEGIN;/COMMIT; so the transaction is controlled here. Never COMMITs. No prod."""
import re, sys
import psycopg2

ENV = "/Users/linyancui/minimal_flask/.env"
SQLFILE = "/Users/linyancui/minimal_flask/db_backups/drug_staging/alter_drug_diagnosis_links_add_soft_delete.sql"
TARGET_COLS = ["is_active", "deactivated_at", "deactivated_by_line_user_id", "deactivated_by_display_name",
               "deactivation_reason", "reactivated_at", "reactivated_by_line_user_id", "reactivation_reason"]

def parse_dsn():
    raw = None
    for line in open(ENV, encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            raw = re.sub(r"\+psycopg2?", "", line.split("=", 1)[1].strip().strip('"').strip("'"))
    m = re.search(r"://([^:/@]+)(?::[^@]*)?@([^:/]+):(\d+)/([^?]+)", raw)
    user, host, port, db = (m.group(1), m.group(2), m.group(3), m.group(4)) if m else ("?", "?", "?", "?")
    return raw, user, host, port, db

def cols_of(cur):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='drug_diagnosis_links' ORDER BY ordinal_position")
    return [r[0] for r in cur.fetchall()]

def unique_def(cur):
    cur.execute("""SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con
                   JOIN pg_class c ON c.oid=con.conrelid WHERE c.relname='drug_diagnosis_links' AND con.contype='u'""")
    return sorted(cur.fetchall())

dsn, user, host, port, db = parse_dsn()
print(f"[db] {host}:{port}/{db} user={user} (password not shown)")
if (host, port, db) != ("localhost", "5432", "dispatch_db"):
    sys.exit(f"REFUSE: not localhost:5432/dispatch_db (got {host}:{port}/{db})")

# ---- extract executable statements (strip comments / BEGIN / COMMIT) ----
raw_sql = open(SQLFILE, encoding="utf-8").read()
exec_lines = []
for line in raw_sql.splitlines():
    line = line.split("--", 1)[0]  # drop inline/full-line comments
    if line.strip():
        exec_lines.append(line)
joined = "\n".join(exec_lines)
stmts = [s.strip() for s in joined.split(";") if s.strip()]
stmts = [s for s in stmts if s.upper() not in ("BEGIN", "COMMIT")]
print(f"[sql] executable statements = {len(stmts)}")
# safety: only ALTER TABLE ... ADD COLUMN allowed
bad = [s for s in stmts if not (s.upper().startswith("ALTER TABLE") and "ADD COLUMN" in s.upper())]
forbidden = [kw for kw in ("DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE", "GRANT", "CREATE") if re.search(rf"\b{kw}\b", joined.upper())]
if bad or forbidden:
    sys.exit(f"REFUSE: non-additive statement(s) found bad={bad} forbidden={forbidden}")
print("[sql] safety: all statements are ALTER TABLE ... ADD COLUMN; no DROP/DELETE/TRUNCATE/INSERT/UPDATE")

result = {"pre": {}, "intx": {}, "post": {}, "pass": True, "notes": []}

# ---- PRE (fresh, read-only) ----
c0 = psycopg2.connect(dsn); c0.set_session(readonly=True, autocommit=True); cur0 = c0.cursor()
cur0.execute("SELECT count(*) FROM drug_diagnosis_links"); n0 = cur0.fetchone()[0]
pre_cols = cols_of(cur0); pre_uni = unique_def(cur0)
pre_target_present = [x for x in TARGET_COLS if x in pre_cols]
cur0.close(); c0.close()
result["pre"] = {"count": n0, "cols": pre_cols, "target_present": pre_target_present, "unique": pre_uni}
print(f"[pre] count={n0} | cols={len(pre_cols)} | target cols already present={pre_target_present}")
if pre_target_present:
    result["pass"] = False; result["notes"].append(f"PRE: target cols already exist: {pre_target_present}")

# ---- TRANSACTION: run ALTERs, verify, ROLLBACK ----
c1 = psycopg2.connect(dsn); c1.autocommit = False; cur1 = c1.cursor()
try:
    for s in stmts:
        cur1.execute(s)
    intx_cols = cols_of(cur1)
    missing = [x for x in TARGET_COLS if x not in intx_cols]
    cur1.execute("""SELECT data_type, is_nullable, column_default FROM information_schema.columns
                    WHERE table_name='drug_diagnosis_links' AND column_name='is_active'""")
    ia = cur1.fetchone()
    cur1.execute("SELECT count(*) FROM drug_diagnosis_links"); n_tx = cur1.fetchone()[0]
    cur1.execute("SELECT count(*) FROM drug_diagnosis_links WHERE is_active IS NOT TRUE"); not_true = cur1.fetchone()[0]
    intx_uni = unique_def(cur1)
    result["intx"] = {"missing": missing, "is_active": ia, "count": n_tx, "rows_not_true": not_true, "unique": intx_uni}
    print(f"[in-tx] 8 cols missing={missing} | is_active(type,nullable,default)={ia}")
    print(f"[in-tx] count={n_tx} | rows is_active<>true={not_true} | unique={intx_uni}")
    if missing: result["pass"] = False; result["notes"].append(f"IN-TX missing cols: {missing}")
    if not (ia and ia[0] == "boolean" and ia[1] == "NO" and ia[2] and "true" in ia[2].lower()):
        result["pass"] = False; result["notes"].append(f"IN-TX is_active def wrong: {ia}")
    if n_tx != n0: result["pass"] = False; result["notes"].append(f"IN-TX count changed {n0}->{n_tx}")
    if not_true != 0: result["pass"] = False; result["notes"].append(f"IN-TX {not_true} rows not is_active=true")
    if intx_uni != pre_uni: result["pass"] = False; result["notes"].append("IN-TX unique constraint changed")
finally:
    c1.rollback()  # NEVER commit
    c1.close()
print("[rollback] transaction rolled back (no commit)")

# ---- POST (fresh) confirm no residue ----
c2 = psycopg2.connect(dsn); c2.set_session(readonly=True, autocommit=True); cur2 = c2.cursor()
cur2.execute("SELECT count(*) FROM drug_diagnosis_links"); n2 = cur2.fetchone()[0]
post_cols = cols_of(cur2); post_uni = unique_def(cur2)
post_target_present = [x for x in TARGET_COLS if x in post_cols]
cur2.close(); c2.close()
result["post"] = {"count": n2, "cols": post_cols, "target_present": post_target_present, "unique": post_uni}
print(f"[post] count={n2} | cols={len(post_cols)} | target cols present after rollback={post_target_present}")
if post_target_present: result["pass"] = False; result["notes"].append(f"POST residue cols: {post_target_present}")
if n2 != n0: result["pass"] = False; result["notes"].append(f"POST count changed {n0}->{n2}")
if post_cols != pre_cols: result["pass"] = False; result["notes"].append("POST columns differ from PRE (residue)")
if post_uni != pre_uni: result["pass"] = False; result["notes"].append("POST unique constraint differs from PRE")

print("=" * 60)
print("VALIDATION:", "PASS ✅" if result["pass"] else "FAIL ❌")
print("notes:", result["notes"] or "none")
print("row count before / in-tx / after =", n0, "/", result["intx"].get("count"), "/", n2)
print("pre cols:", pre_cols)
print("post cols == pre cols:", post_cols == pre_cols)
