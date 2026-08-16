#!/usr/bin/env python3
"""Finish migration: mechanism_candidates + worklog + verify, then print DB token."""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

API = "https://api.turso.tech"
ROOT = Path(__file__).resolve().parent
HOST = "metaengine-project-patrickfrome.aws-eu-west-1.turso.io"
EVIDENCE = ROOT / "03_EVIDENCE" / "METAENGINE1"
ARCH_LIB = ROOT / "research" / "architecture_library"

def _platform(path, token, body=None):
    req = urllib.request.Request(API+path, data=json.dumps(body).encode() if body else None, method="POST", headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def libsql_execute(host, db_token, sql, params=None):
    url = f"https://{host}/v2/pipeline"
    body = {"requests":[{"type":"execute","stmt":{"sql":sql, **({"args":params} if params else {})}}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Authorization":f"Bearer {db_token}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"LIBSQL_ERROR HTTP {e.code}: {e.read().decode()[:300]}\nSQL: {sql[:200]}", file=sys.stderr)
        raise

def libsql_query(host, db_token, sql):
    result = libsql_execute(host, db_token, sql)
    try:
        res = result["results"][0]["response"]["result"]
        cols = [c.get("name",f"c{i}") for i,c in enumerate(res.get("cols",[]))]
        rows = []
        for row in res.get("rows",[]):
            vals = []
            for v in row.get("values",[]):
                if v.get("type")=="null": vals.append(None)
                else: vals.append(v.get("value"))
            rows.append(dict(zip(cols, vals)))
        return rows
    except (KeyError, IndexError, TypeError) as e:
        print(f"query parse error: {e}", file=sys.stderr)
        return []

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def main():
    tok = os.environ["TURSO_API_TOKEN"]
    db_token = _platform("/v1/databases/metaengine-project/auth/tokens", tok, {})["jwt"]
    print(f"[token] db token created (len {len(db_token)})")

    # mechanism_candidates
    lib = json.loads((ARCH_LIB/"mechanism_library.json").read_text())
    n=0
    for cand in lib.get("candidates",[]):
        libsql_execute(HOST, db_token,
            "INSERT OR REPLACE INTO metaengine_mechanism_candidates (mechanism_id, mechanism_hash, status, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            params=[{"type":"text","value":cand["mechanism_id"]},{"type":"text","value":cand.get("mechanism_hash","")},{"type":"text","value":cand.get("status","")},{"type":"text","value":json.dumps(cand,sort_keys=True)},{"type":"text","value":_now()}])
        n+=1
    print(f"[migrate] mechanism_candidates: {n} rows")

    # worklog
    worklog = Path("/home/z/my-project/worklog.md").read_text(errors="replace")
    sections = worklog.split("\n---\n")
    n=0
    for section in sections:
        section=section.strip()
        if not section or section.startswith("# MetaEngine"): continue
        task_id=agent=task=""
        for line in section.split("\n"):
            ls=line.strip()
            if ls.startswith("Task ID:"): task_id=ls[8:].strip()
            elif ls.startswith("Agent:"): agent=ls[7:].strip()
            elif ls.startswith("Task:"): task=ls[5:].strip(); break
        if not task_id: continue
        libsql_execute(HOST, db_token,
            "INSERT INTO metaengine_worklog (task_id, agent, task, content, created_at) VALUES (?, ?, ?, ?, ?)",
            params=[{"type":"text","value":task_id},{"type":"text","value":agent},{"type":"text","value":task[:500]},{"type":"text","value":section},{"type":"text","value":_now()}])
        n+=1
    print(f"[migrate] worklog: {n} entries")

    # verify
    print("\n=== VERIFY ===")
    counts={}
    for t in ["metaengine_canonical_anchors","metaengine_dev_steps","metaengine_artifacts","metaengine_source_records","metaengine_mechanism_candidates","metaengine_worklog","metaengine_project_meta"]:
        rows=libsql_query(HOST, db_token, f"SELECT COUNT(*) AS n FROM {t}")
        counts[t]=rows[0].get("n","?") if rows else "?"
    print(json.dumps(counts, indent=2))

    # sample query: dev steps
    print("\n=== sample: dev steps ===")
    steps=libsql_query(HOST, db_token, "SELECT step_id, kind, decision, receipt_hash FROM metaengine_dev_steps ORDER BY step_id")
    for s in steps: print(f"  {s}")
    print("\n=== sample: source records ===")
    srcs=libsql_query(HOST, db_token, "SELECT source_id, source_class, ingestion FROM metaengine_source_records ORDER BY source_id")
    for s in srcs: print(f"  {s}")
    print("\n=== sample: mechanism candidates ===")
    mecs=libsql_query(HOST, db_token, "SELECT mechanism_id, status FROM metaengine_mechanism_candidates ORDER BY mechanism_id")
    for m in mecs: print(f"  {m}")

    # write record (no tokens)
    record={
        "status":"CLOUD_DB_CREATED_AND_MIGRATED",
        "store_kind":"TURSO_LIBSQL_CLOUD_DB",
        "canonical_authority":False,
        "role":"NON_CANONICAL_PROJECT_STATE_PERSISTENCE",
        "provider":"turso",
        "group":"metaengine",
        "database":"metaengine-project",
        "host":HOST,
        "libsql_url":f"libsql://{HOST}",
        "https_url":f"https://{HOST}",
        "location":"aws-eu-west-1",
        "row_counts":counts,
        "schema_tables":["metaengine_canonical_anchors","metaengine_dev_steps","metaengine_artifacts","metaengine_source_records","metaengine_mechanism_candidates","metaengine_worklog","metaengine_project_meta"],
        "note":"DB auth token printed to stdout only (not persisted). Store as TURSO_DB_TOKEN for the persister.",
    }
    (EVIDENCE/"cloud_db_creation_record.json").write_text(json.dumps(record,indent=2))
    print(f"\n[record] written to {EVIDENCE/'cloud_db_creation_record.json'}")
    print(f"\n=== DB ACCESS TOKEN (SAVE THIS in your secret manager as TURSO_DB_TOKEN) ===")
    print(f"TURSO_DB_TOKEN={db_token}")
    print(f"\nlibsql URL: libsql://{HOST}")
    print("\nCLOUD_DB_MIGRATE_PASS")

if __name__=="__main__":
    main()
