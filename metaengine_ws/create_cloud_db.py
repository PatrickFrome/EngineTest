#!/usr/bin/env python3
"""METAENGINE — create a NEW non-canonical Supabase cloud DB with the full schema.

Creates a brand-new Supabase project (NOT the canonical gzrbxoiuenkksualgpvp),
waits for the DB to become ready, then applies the 12 MetaEngine Postgres
migrations in dependency order. Returns the project URL + DB connection string.

Constitutional position: this does NOT touch the canonical store. Boundary 3
(canonical mutation) is NOT triggered because we are creating a SEPARATE
project. The new project is a non-canonical cloud instance of the MetaEngine
schema, clearly labelled as such.

Required env (inject via trusted runtime, NEVER paste in chat):
    SUPABASE_ACCESS_TOKEN  -- Supabase Personal Access Token
                              (Dashboard -> Account -> Access Tokens -> Generate new token)

Optional env:
    SUPABASE_ORG_ID        -- organization id to create the project in
                              (if omitted, the first org you belong to is used)
    METAENGINE_CLOUD_PROJECT_NAME -- project name (default: metaengine-cloud-<random>)
    METAENGINE_CLOUD_DB_PASSWORD  -- db password (default: generated, printed once)
    METAENGINE_CLOUD_REGION       -- region (default: ca-central-1)

Usage:
    SUPABASE_ACCESS_TOKEN=sbp_... python3 create_cloud_db.py
"""

from __future__ import annotations

import json
import os
import secrets
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.supabase.com/v1"
MIGRATIONS_DIR = Path(
    "/tmp/supabase_capsule/METAENGINE_SUPABASE_NO_INTERACTIVE_GUARDS_CAPSULE_2026-08-14/sql/metaengine_migrations"
)

# Apply order matters: base schema first, then feature migrations.
MIGRATION_ORDER = [
    "postgres_schema.sql",
    "deploy_schema_and_seed.sql",
    "interwoven_architecture_1_2.sql",
    "recursive_core4_nonlinearity_1_3.sql",
    "polycentric_reentry_1_4.sql",
    "epistemic_coordination_1_1.sql",
    "parallel_experimental_ecology_2_1.sql",
    "self_reorganizing_ecology_2_0.sql",
    "frontier_evidence_control_2_2.sql",
    "outcome_gated_self_learning_2_3.sql",
    "federated_chat_fabric_d6.sql",
    "federated_chat_fabric_d6_finalization.sql",
]


def _token() -> str:
    tok = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if not tok:
        raise SystemExit(
            "SUPABASE_ACCESS_TOKEN is not set.\n"
            "Get one at: Supabase Dashboard -> Account -> Access Tokens -> Generate new token.\n"
            "Inject it via trusted runtime env, never paste in chat."
        )
    return tok


def _mgmt(method: str, path: str, *, token: str, body: dict | None = None) -> dict:
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        raise SystemExit(f"MGMT_API_ERROR {method} {path}: HTTP {exc.code}\n{err_body}") from exc


def _resolve_org(token: str) -> str:
    org_id = os.environ.get("SUPABASE_ORG_ID", "").strip()
    if org_id:
        return org_id
    orgs = _mgmt("GET", "/organizations", token=token)
    if not orgs:
        raise SystemExit("No organizations found for this token. Create one in Supabase Dashboard first.")
    return orgs[0]["id"]


def _gen_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "Me-" + "".join(secrets.choice(alphabet) for _ in range(24))


def _gen_name() -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"metaengine-cloud-{suffix}"


def create_project(token: str, org_id: str) -> dict:
    name = os.environ.get("METAENGINE_CLOUD_PROJECT_NAME") or _gen_name()
    db_pass = os.environ.get("METAENGINE_CLOUD_DB_PASSWORD") or _gen_password()
    region = os.environ.get("METAENGINE_CLOUD_REGION", "ca-central-1")
    print(f"[create] name={name} region={region} org={org_id}")
    print(f"[create] db_password generated (SAVE THIS): {db_pass}")
    result = _mgmt(
        "POST",
        "/projects",
        token=token,
        body={
            "organization_id": org_id,
            "name": name,
            "db_pass": db_pass,
            "region": region,
            "plan": "free",
            "db_type": "postgres",
        },
    )
    print(f"[create] project ref: {result.get('id')}")
    return {"ref": result["id"], "name": name, "db_pass": db_pass, "region": region}


def wait_for_ready(token: str, project_ref: str, timeout: float = 600.0) -> None:
    print(f"[wait] waiting for project {project_ref} DB to become ready (up to {int(timeout)}s)...")
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        info = _mgmt("GET", f"/projects/{project_ref}", token=token)
        status = info.get("status")
        if status != last_status:
            print(f"[wait] status: {status}")
            last_status = status
        if status == "ACTIVE":
            return
        if status in ("REMOVED", "RESTARTING"):
            raise SystemExit(f"Unexpected project status: {status}")
        time.sleep(10)
    raise SystemExit(f"TIMEOUT waiting for project {project_ref} to become ACTIVE")


def get_db_url(token: str, project_ref: str, db_pass: str) -> str:
    """Build the direct Postgres connection string."""
    # Direct connection: postgres.{ref}.supabase.co:5432
    host = f"db.{project_ref}.supabase.co"
    return f"postgresql://postgres:{db_pass}@{host}:5432/postgres"


def apply_migrations(db_url: str) -> list[str]:
    """Apply each migration in order via psycopg3."""
    try:
        import psycopg
    except ImportError:
        raise SystemExit("psycopg v3 required: python -m pip install 'psycopg[binary]>=3.2,<4'")
    applied = []
    for fname in MIGRATION_ORDER:
        path = MIGRATIONS_DIR / fname
        if not path.is_file():
            print(f"[migrate] SKIP (missing): {fname}")
            continue
        sql = path.read_text(encoding="utf-8")
        print(f"[migrate] applying {fname} ({len(sql)} bytes)...")
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        applied.append(fname)
        print(f"[migrate] OK {fname}")
    return applied


def main() -> int:
    token = _token()
    org_id = _resolve_org(token)
    proj = create_project(token, org_id)
    project_ref = proj["ref"]
    try:
        wait_for_ready(token, project_ref)
    except SystemExit:
        print("\n[info] project may still be provisioning. Check status at:")
        print(f"       https://supabase.com/dashboard/project/{project_ref}")
        print(f"       Once ACTIVE, re-run with METAENGINE_CLOUD_PROJECT_REF={project_ref}")
        print(f"       and METAENGINE_CLOUD_DB_PASSWORD=<the password printed above>")
        return 2

    db_url = get_db_url(token, project_ref, proj["db_pass"])
    print(f"\n[ready] project URL: https://supabase.com/dashboard/project/{project_ref}")
    print(f"[ready] API URL: https://{project_ref}.supabase.co")
    print(f"[ready] DB host: db.{project_ref}.supabase.co:5432")

    applied = apply_migrations(db_url)

    # Verify: list tables in destruktion_meta schema
    print("\n[verify] listing tables in destruktion_meta schema...")
    import psycopg
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select table_name from information_schema.tables where table_schema='destruktion_meta' order by table_name"
            )
            tables = [r[0] for r in cur.fetchall()]
    print(f"[verify] destruktion_meta tables ({len(tables)}): {tables}")

    summary = {
        "status": "CLOUD_DB_CREATED",
        "store_kind": "NON_CANONICAL_CLOUD_SUPABASE_INSTANCE",
        "canonical_authority": False,
        "project_ref": project_ref,
        "project_name": proj["name"],
        "project_url": f"https://supabase.com/dashboard/project/{project_ref}",
        "api_url": f"https://{project_ref}.supabase.co",
        "db_host": f"db.{project_ref}.supabase.co",
        "db_port": 5432,
        "db_name": "postgres",
        "db_user": "postgres",
        "db_password": proj["db_pass"],
        "region": proj["region"],
        "migrations_applied": applied,
        "destruktion_meta_table_count": len(tables),
        "note": "This is a NEW non-canonical cloud instance with the full MetaEngine schema. It does NOT touch the canonical gzrbxoiuenkksualgpvp store (Boundary 3 preserved).",
    }
    out = Path("/home/z/my-project/metaengine_ws/03_EVIDENCE/METAENGINE1/cloud_db_creation_record.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n[summary] written to {out}")
    print(json.dumps(summary, indent=2))
    print("\nCLOUD_DB_CREATE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
