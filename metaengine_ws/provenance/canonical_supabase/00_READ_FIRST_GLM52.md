# MetaEngine Supabase — no-interactive-guards mode

Canonical project ref: `gzrbxoiuenkksualgpvp`

This capsule removes MetaEngine-side confirmations for destructive SQL and restore operations. It does **not** embed credentials and cannot disable Supabase/PostgreSQL authentication.

## Runtime variables

Set in the trusted Z.ai/ZCode environment or secret manager:

```text
METAENGINE_DATABASE_URL=<PostgreSQL connection URI with administrative credentials>
SUPABASE_URL=https://gzrbxoiuenkksualgpvp.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role/secret API key>
```

Do not paste secret values into chat transcripts or commit them to the project.

## Install

```bash
python -m pip install 'psycopg[binary]>=3.2,<4'
```

## Optional identity/admin probe

```bash
python scripts/metaengine_db_admin.py verify
python scripts/supabase_service_role_probe.py
```

## Direct SQL commit — no confirmation flag

```bash
python scripts/metaengine_db_admin.py exec-sql --file change.sql
```

## Direct restore — no confirmation flag

```bash
python scripts/metaengine_db_admin.py restore --file backup.dump
```

## Backup is optional

```bash
python scripts/metaengine_db_admin.py backup --out ./backup.dump
```

`exec-sql` and `restore` do not call `verify()` automatically and do not require a project-ref or destructive-operation confirmation. Database permissions are determined solely by the credentials in `METAENGINE_DATABASE_URL`.
