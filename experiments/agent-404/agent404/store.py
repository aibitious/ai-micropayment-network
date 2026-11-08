"""SQLite MVP store. One writer per transaction; intentionally single-worker."""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS counters (
                    bucket TEXT NOT NULL, identity TEXT NOT NULL, n INTEGER NOT NULL,
                    PRIMARY KEY(bucket, identity)
                );
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY, subject TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS results_subject ON results(subject, expires_at);
                CREATE TABLE IF NOT EXISTS gaps (
                    fingerprint TEXT PRIMARY KEY, topic TEXT NOT NULL,
                    first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
                    requests INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at INTEGER NOT NULL, identity TEXT NOT NULL, kind TEXT NOT NULL,
                    outcome TEXT NOT NULL, cached INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS events_at ON events(at);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def consume_limit(self, bucket: str, identity: str, maximum: int) -> bool:
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            n = db.execute('SELECT n FROM counters WHERE bucket=? AND identity=?', (bucket, identity)).fetchone()
            if n and n['n'] >= maximum:
                return False
            db.execute('''INSERT INTO counters(bucket,identity,n) VALUES(?,?,1)
                          ON CONFLICT(bucket,identity) DO UPDATE SET n=n+1''', (bucket, identity))
            return True

    def cached(self, subject: str):
        with self.connection() as db:
            item = db.execute('''SELECT payload FROM results WHERE subject=? AND expires_at>?
                                 ORDER BY created_at DESC LIMIT 1''', (subject, int(time.time()))).fetchone()
            return json.loads(item['payload']) if item else None

    def result(self, ident: str):
        with self.connection() as db:
            item = db.execute('SELECT payload FROM results WHERE id=?', (ident,)).fetchone()
            return json.loads(item['payload']) if item else None

    def save(self, ident: str, subject: str, payload: dict, ttl_seconds: int):
        now = int(time.time())
        with self.connection() as db:
            db.execute('''INSERT INTO results(id,subject,payload,created_at,expires_at)
                          VALUES(?,?,?,?,?)''', (ident, subject, json.dumps(payload), now, now+ttl_seconds))

    def event(self, identity: str, kind: str, outcome: str, cached: bool = False):
        with self.connection() as db:
            db.execute('INSERT INTO events(at,identity,kind,outcome,cached) VALUES(?,?,?,?,?)',
                       (int(time.time()), identity, kind, outcome, int(cached)))

    def gap(self, fingerprint: str, topic: str):
        now = int(time.time())
        with self.connection() as db:
            db.execute('''INSERT INTO gaps(fingerprint,topic,first_seen,last_seen,requests)
                          VALUES(?,?,?,?,1) ON CONFLICT(fingerprint) DO UPDATE SET
                          last_seen=excluded.last_seen, requests=requests+1''',
                       (fingerprint, topic, now, now))

    def metrics(self):
        after = int(time.time()) - 30*86400
        with self.connection() as db:
            rows = db.execute('''SELECT kind,outcome,COUNT(*) AS n, SUM(cached) AS cache_hits
                                 FROM events WHERE at>=? GROUP BY kind,outcome''', (after,)).fetchall()
            clients = db.execute('''SELECT COUNT(DISTINCT identity) AS n FROM events WHERE at>=?''', (after,)).fetchone()['n']
            gaps = db.execute('SELECT topic,requests FROM gaps ORDER BY requests DESC LIMIT 20').fetchall()
            return {'last_30_days': [dict(r) for r in rows],
                    'estimated_clients': clients,
                    'top_gaps': [dict(r) for r in gaps],
                    'payments': 'disabled'}

    def prune(self):
        now = int(time.time())
        with self.connection() as db:
            db.execute('DELETE FROM events WHERE at<?', (now-30*86400,))
            db.execute('DELETE FROM results WHERE expires_at<?', (now-7*86400,))
            db.execute('DELETE FROM gaps WHERE last_seen<?', (now-90*86400,))
            db.execute("DELETE FROM counters WHERE bucket LIKE 'day:%' AND bucket<?", (f'day:{time.strftime("%Y%m%d",time.gmtime(now-3*86400))}',))
