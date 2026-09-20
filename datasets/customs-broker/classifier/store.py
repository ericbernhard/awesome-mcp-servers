#!/usr/bin/env python3
"""
Persistence for classifications: an append-only audit log + a human-review queue.

Two needs this covers:
  1. Reasonable-care recordkeeping — CBP expects importers to keep classification
     records for 5 years. Every classify() result should be logged immutably.
  2. Human-in-the-loop — `review_required` results go into a queue for a licensed
     broker; their correction is recorded and becomes future training/eval data.

Stdlib sqlite3 only. Default DB file: classifications.db (override via env or arg).

    from store import Store
    s = Store()
    s.log(result)                       # audit every classification
    if result["review_required"]:
        s.enqueue(result)               # send to broker queue
    s.list_pending()                    # broker view
    s.resolve(item_id, "6109100012", reviewer="jdoe", note="correct subheading")
"""
import argparse
import json
import os
import sqlite3
import time

DEFAULT_DB = os.environ.get("CLASSIFIER_DB", "classifications.db")


class Store:
    def __init__(self, path=DEFAULT_DB):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                description TEXT,
                hts10 TEXT,
                chapter TEXT,
                confidence REAL,
                review_required INTEGER,
                model TEXT,
                mock INTEGER,
                result_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                description TEXT,
                predicted_hts10 TEXT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                corrected_hts10 TEXT,
                reviewer TEXT,
                note TEXT,
                resolved_ts REAL,
                result_json TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def log(self, result: dict) -> int:
        """Append a classification to the immutable audit log. Returns row id."""
        cur = self.db.execute(
            "INSERT INTO audit (ts, description, hts10, chapter, confidence, "
            "review_required, model, mock, result_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), result.get("_description", result.get("description", "")),
             result.get("hts10", ""), result.get("chapter", ""),
             float(result.get("confidence", 0) or 0),
             int(bool(result.get("review_required"))), result.get("model", ""),
             int(bool(result.get("mock"))), json.dumps(result)),
        )
        self.db.commit()
        return cur.lastrowid

    def enqueue(self, result: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO review_queue (ts, description, predicted_hts10, reason, result_json) "
            "VALUES (?,?,?,?,?)",
            (time.time(), result.get("_description", result.get("description", "")),
             result.get("hts10", ""), result.get("review_reason", ""), json.dumps(result)),
        )
        self.db.commit()
        return cur.lastrowid

    def list_pending(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, ts, description, predicted_hts10, reason FROM review_queue "
            "WHERE status='pending' ORDER BY ts")]

    def resolve(self, item_id: int, corrected_hts10: str, reviewer: str, note: str = ""):
        self.db.execute(
            "UPDATE review_queue SET status='resolved', corrected_hts10=?, reviewer=?, "
            "note=?, resolved_ts=? WHERE id=?",
            (corrected_hts10, reviewer, note, time.time(), item_id))
        self.db.commit()

    def export_corrections(self) -> list[dict]:
        """Resolved items as labeled rows — feed back into the eval set / few-shot."""
        out = []
        for r in self.db.execute(
                "SELECT description, corrected_hts10 FROM review_queue "
                "WHERE status='resolved' AND corrected_hts10 != ''"):
            out.append({"description": r["description"], "true_hts10": r["corrected_hts10"]})
        return out


def _demo():
    s = Store(":memory:")
    sample = {"description": "men's cotton t-shirt", "hts10": "6109100099",
              "chapter": "61", "confidence": 0.55, "review_required": True,
              "review_reason": "low confidence", "model": "mock", "mock": True}
    s.log(sample)
    qid = s.enqueue(sample)
    print("pending:", s.list_pending())
    s.resolve(qid, "6109100012", reviewer="broker_jdoe", note="correct stat suffix")
    print("corrections for eval:", s.export_corrections())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Demo the audit log + review queue (in-memory).")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        ap.print_help()
