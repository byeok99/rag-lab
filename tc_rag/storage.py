from __future__ import annotations

import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import TestCase
from .util import sha256_text, stable_json


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS documents(
          document_id TEXT PRIMARY KEY, filename TEXT NOT NULL, file_hash TEXT NOT NULL,
          project_id TEXT NOT NULL, product_version TEXT NOT NULL, imported_at TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1, parser_report TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS test_cases(
          record_id TEXT PRIMARY KEY, document_id TEXT, identity_key TEXT, content_hash TEXT NOT NULL,
          project_id TEXT NOT NULL, product_version TEXT NOT NULL, origin TEXT NOT NULL,
          review_status TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, data_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_tc_scope ON test_cases(project_id, product_version, active);
        CREATE INDEX IF NOT EXISTS idx_tc_identity ON test_cases(document_id, identity_key, active);
        CREATE TABLE IF NOT EXISTS splits(
          split_version TEXT NOT NULL, record_id TEXT NOT NULL, partition TEXT NOT NULL,
          group_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(split_version, record_id));
        CREATE TABLE IF NOT EXISTS vector_index(
          index_version TEXT NOT NULL, record_id TEXT NOT NULL, chunk_id TEXT NOT NULL,
          model TEXT NOT NULL, dimension INTEGER NOT NULL, preprocess TEXT NOT NULL,
          vector_json TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(index_version, chunk_id));
        CREATE TABLE IF NOT EXISTS reviews(
          review_id INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT NOT NULL, action TEXT NOT NULL,
          reason TEXT, reviewer TEXT NOT NULL, before_json TEXT, after_json TEXT,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs(
          run_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
          config_json TEXT NOT NULL, result_json TEXT, started_at TEXT NOT NULL, finished_at TEXT);
        CREATE TABLE IF NOT EXISTS id_sequences(project_id TEXT PRIMARY KEY, next_value INTEGER NOT NULL);
        """)
        self.db.commit()

    def close(self): self.db.close()

    def import_report(self, report, project: str, version: str, file_hash: str) -> dict[str, Any]:
        existing_doc = self.db.execute("SELECT * FROM documents WHERE filename=? AND project_id=? AND product_version=? AND active=1", (report.filename,project,version)).fetchone()
        unchanged = bool(existing_doc and existing_doc["file_hash"] == file_hash)
        if unchanged: return {"status":"unchanged","inserted":0,"updated":0,"deleted":0,"document_id":existing_doc["document_id"]}
        old = {}
        if existing_doc:
            for row in self.db.execute("SELECT * FROM test_cases WHERE document_id=? AND active=1", (existing_doc["document_id"],)):
                old.setdefault(row["identity_key"], []).append(row)
            self.db.execute("UPDATE documents SET active=0 WHERE document_id=?", (existing_doc["document_id"],))
        self.db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,1,?)", (report.source_document_id,report.filename,file_hash,project,version,now(),stable_json({"warnings":report.warnings})))
        inserted=updated=ambiguous=0; matched=set()
        for tc in report.records:
            identity = self._identity(tc); content_hash = sha256_text(stable_json(self._content(tc)))
            matches = old.get(identity, [])
            if len(matches) == 1:
                previous = matches[0]; matched.add(previous["record_id"])
                tc.record_id = previous["record_id"]
                updated += int(previous["content_hash"] != content_hash)
            elif len(matches) > 1:
                ambiguous += 1
                tc.parser_notes.append("ambiguous identity; stored as a new record")
                inserted += 1
            else: inserted += 1
            self.db.execute("""INSERT OR REPLACE INTO test_cases
              (record_id,document_id,identity_key,content_hash,project_id,product_version,origin,review_status,active,data_json,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,1,?,?,?)""", (tc.record_id,report.source_document_id,identity,content_hash,project,version,tc.origin,tc.review_status,stable_json(tc.to_dict()),now(),now()))
        deleted = 0
        if existing_doc:
            stale = [r["record_id"] for rows in old.values() for r in rows if r["record_id"] not in matched]
            for rid in stale:
                self.db.execute("UPDATE test_cases SET active=0,updated_at=? WHERE record_id=?",(now(),rid)); deleted += 1
        self.db.commit()
        return {"status":"imported","inserted":inserted,"updated":updated,"deleted":deleted,"ambiguous":ambiguous,"document_id":report.source_document_id}

    @staticmethod
    def _identity(tc: TestCase) -> str:
        # Row is intentionally excluded; duplicates are disambiguated by content and never merged by TC_ID alone.
        return sha256_text(stable_json([tc.original_tc_id,tc.category_large,tc.category_medium,tc.category_small,tc.scenario,tc.raw_input_text,tc.raw_expected_output_text]))

    @staticmethod
    def _content(tc: TestCase) -> dict[str,Any]:
        d=tc.to_dict(); d.pop("record_id",None); d.pop("source_refs",None); return d

    def get(self, record_id: str) -> TestCase | None:
        row=self.db.execute("SELECT data_json FROM test_cases WHERE record_id=? AND active=1",(record_id,)).fetchone()
        return TestCase.from_dict(json.loads(row[0])) if row else None

    def list_cases(self, project: str|None=None, version: str|None=None, origin: str|None=None, status: str|None=None) -> list[TestCase]:
        sql="SELECT data_json FROM test_cases WHERE active=1"; args=[]
        for col,val in (("project_id",project),("product_version",version),("origin",origin),("review_status",status)):
            if val is not None: sql+=f" AND {col}=?"; args.append(val)
        return [TestCase.from_dict(json.loads(r[0])) for r in self.db.execute(sql+" ORDER BY created_at",args)]

    def save_case(self, tc: TestCase, document_id: str|None=None) -> None:
        content_hash=sha256_text(stable_json(self._content(tc)))
        self.db.execute("""INSERT OR REPLACE INTO test_cases
        (record_id,document_id,identity_key,content_hash,project_id,product_version,origin,review_status,active,data_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,1,?,COALESCE((SELECT created_at FROM test_cases WHERE record_id=?),?),?)""",
        (tc.record_id,document_id,self._identity(tc),content_hash,tc.project_id,tc.product_version,tc.origin,tc.review_status,stable_json(tc.to_dict()),tc.record_id,now(),now())); self.db.commit()

    def next_tc_id(self, project: str, prefix: str="GEN") -> str:
        row=self.db.execute("SELECT next_value FROM id_sequences WHERE project_id=?",(project,)).fetchone(); n=row[0] if row else 1
        self.db.execute("INSERT OR REPLACE INTO id_sequences VALUES(?,?)",(project,n+1)); self.db.commit()
        return f"{prefix}-{n:04d}"

    def review(self, record_id: str, action: str, reviewer: str, reason: str="", patch: dict[str,Any]|None=None) -> TestCase:
        tc=self.get(record_id)
        if not tc: raise ValueError("record not found")
        before=tc.to_dict()
        if patch:
            protected={"record_id","origin","source_refs"}
            for k,v in patch.items():
                if k in tc.__dataclass_fields__ and k not in protected: setattr(tc,k,v)
        if action=="approve":
            if tc.requires_confirmation or tc.expected_result_basis=="unknown" or not tc.expected_results:
                raise ValueError("unconfirmed expected result cannot be approved")
            if not reason: raise ValueError("approval requires an evidence note")
            tc.review_status="approved"
        elif action=="reject": tc.review_status="rejected"
        elif action in {"request-confirmation","needs-revision"}: tc.review_status="needs_revision"; tc.requires_confirmation=True
        elif action=="edit": tc.review_status="needs_revision"
        else: raise ValueError("unsupported review action")
        self.save_case(tc)
        self.db.execute("INSERT INTO reviews(record_id,action,reason,reviewer,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)",(record_id,action,reason,reviewer,stable_json(before),stable_json(tc.to_dict()),now())); self.db.commit()
        return tc

