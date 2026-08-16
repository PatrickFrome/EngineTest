PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leases (
  task_hash TEXT PRIMARY KEY CHECK(length(task_hash) = 64),
  owner_hash TEXT NOT NULL,
  lease_version INTEGER NOT NULL,
  expires_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS task_refs (
  task_hash TEXT PRIMARY KEY CHECK(length(task_hash) = 64),
  task_ref TEXT NOT NULL,
  privacy_class TEXT NOT NULL CHECK(privacy_class IN ('P0','P1','P2')),
  status TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_refs (
  candidate_hash TEXT PRIMARY KEY CHECK(length(candidate_hash) = 64),
  task_hash TEXT NOT NULL REFERENCES task_refs(task_hash),
  verifier_hash TEXT,
  status TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS verification_requests (
  request_hash TEXT PRIMARY KEY CHECK(length(request_hash) = 64),
  task_hash TEXT NOT NULL REFERENCES task_refs(task_hash),
  candidate_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_snapshots (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  worker_requests_remaining INTEGER,
  d1_rows_read_remaining INTEGER,
  d1_rows_written_remaining INTEGER,
  r2_class_a_remaining INTEGER,
  r2_class_b_remaining INTEGER,
  workflow_steps_remaining INTEGER,
  workers_ai_neurons_remaining INTEGER,
  observed_at_ms INTEGER NOT NULL
);
