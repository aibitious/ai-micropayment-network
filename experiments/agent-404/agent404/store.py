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
                CREATE TABLE IF NOT EXISTS lab_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at INTEGER NOT NULL,
                    tool TEXT NOT NULL,
                    identity TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    internal INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS lab_events_tool_at ON lab_events(tool,at);
                CREATE TABLE IF NOT EXISTS discovery_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at INTEGER NOT NULL,
                    route TEXT NOT NULL,
                    method TEXT NOT NULL,
                    identity TEXT NOT NULL,
                    segment TEXT NOT NULL,
                    campaign TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    internal INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS discovery_events_at ON discovery_events(at);
                CREATE INDEX IF NOT EXISTS discovery_events_route_at ON discovery_events(route,at);
                CREATE TABLE IF NOT EXISTS wave2_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at INTEGER NOT NULL, tool TEXT NOT NULL, identity TEXT NOT NULL,
                    stage TEXT NOT NULL, outcome TEXT NOT NULL,
                    channel TEXT NOT NULL, internal INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS wave2_events_tool_at ON wave2_events(tool,at);
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

    def lab_event(self, tool: str, identity: str, channel: str,
                  outcome: str, latency_ms: int, internal: bool = False):
        # No raw tool input, results, URL, secret, CSV, invoice or prompt is persisted.
        with self.connection() as db:
            db.execute('''INSERT INTO lab_events(at,tool,identity,channel,outcome,internal,latency_ms)
                          VALUES(?,?,?,?,?,?,?)''',
                       (int(time.time()), tool, identity, channel, outcome,
                        int(internal), min(60000,max(0,int(latency_ms)))))

    def lab_metrics(self, since: int | None = None):
        after = int(since or (time.time() - 30*86400))
        with self.connection() as db:
            rows = db.execute('''SELECT tool, channel, COUNT(*) AS calls,
                         SUM(CASE WHEN outcome IN ('ok','issues') THEN 1 ELSE 0 END) AS completed,
                         SUM(CASE WHEN outcome='invalid_input' THEN 1 ELSE 0 END) AS invalid,
                         SUM(CASE WHEN outcome='rate_limited' THEN 1 ELSE 0 END) AS rate_limited,
                         SUM(CASE WHEN outcome='error' THEN 1 ELSE 0 END) AS errors,
                         COUNT(DISTINCT CASE WHEN channel='rest' THEN identity END) AS estimated_rest_client_ids,
                         ROUND(AVG(latency_ms),1) AS mean_latency_ms
                         FROM lab_events WHERE at>=? AND internal=0
                         GROUP BY tool,channel ORDER BY tool,channel''',(after,)).fetchall()
            internal = db.execute('''SELECT tool,COUNT(*) AS n FROM lab_events
                                     WHERE at>=? AND internal=1 GROUP BY tool''',(after,)).fetchall()
            repeats = db.execute('''SELECT tool,COUNT(*) AS estimated_rest_returning_network_ids
                       FROM (SELECT tool,identity,COUNT(DISTINCT DATE(at,'unixepoch')) AS active_days
                             FROM lab_events WHERE at>=? AND internal=0 AND channel='rest'
                             GROUP BY tool,identity) WHERE active_days>=2 GROUP BY tool''',(after,)).fetchall()
            cve = db.execute('''SELECT COUNT(*) AS n,COUNT(DISTINCT identity) AS estimated_client_ids
                                FROM events WHERE at>=? AND kind='resolve' ''',(after,)).fetchone()
            return {'window_start_unix':after,'tool_channels':[dict(r) for r in rows],
                    'estimated_rest_returning_network_ids':{r['tool']:r['estimated_rest_returning_network_ids'] for r in repeats},
                    'internal_test_events':{r['tool']:r['n'] for r in internal},
                    'cve_baseline':dict(cve),
                    'note':'REST unique clients are HMAC network-ID estimates; MCP uses a shared anonymous bucket, so unique MCP agents are unknown. Crawlers are not automatically excluded. No raw payloads are retained.'}

    def discovery_event(self, route: str, method: str, identity: str,
                        segment: str, campaign: str, status_code: int,
                        internal: bool = False):
        """Metadata-only discovery record: no raw IP, UA, referrer, URL or payload."""
        with self.connection() as db:
            db.execute('''INSERT INTO discovery_events
                       (at,route,method,identity,segment,campaign,status_code,internal)
                       VALUES(?,?,?,?,?,?,?,?)''',
                       (int(time.time()), route, method, identity, segment,
                        campaign, int(status_code), int(internal)))

    def discovery_metrics(self, since: int | None = None):
        """Unclassified/declared-automated traffic; neither implies a real person."""
        after = int(since if since is not None else time.time() - 30*86400)
        with self.connection() as db:
            rows = db.execute('''SELECT DATE(at,'unixepoch') AS day,route,method,
                             segment,campaign,status_code,COUNT(*) AS requests,
                             COUNT(DISTINCT identity) AS estimated_network_ids
                             FROM discovery_events
                             WHERE at>=? AND internal=0
                             GROUP BY day,route,method,segment,campaign,status_code
                             ORDER BY day,route,method''', (after,)).fetchall()
            tests = db.execute('''SELECT COUNT(*) AS n FROM discovery_events
                                  WHERE at>=? AND internal=1''',(after,)).fetchone()['n']
            returning = db.execute('''SELECT COUNT(*) AS n FROM
                (SELECT identity FROM discovery_events
                 WHERE at>=? AND internal=0 AND segment='unclassified'
                   AND route IN ('landing','tools_directory','tool_detail','wave2_directory','wave2_detail','docs')
                   AND method='GET' AND status_code BETWEEN 200 AND 299
                 GROUP BY identity
                 HAVING COUNT(DISTINCT DATE(at,'unixepoch')) >= 2)''',
                 (after,)).fetchone()['n']
            return {'window_start_unix': after,
                    'by_day_route': [dict(r) for r in rows],
                    'internal_probes_excluded': tests,
                    'estimated_returning_unclassified_network_ids': returning,
                    'measurement_started_from_first_discovery_event': True,
                    'interpretation': 'Network IDs are HMAC estimates; User-Agent self-declared automation is spoofable. Unclassified visits are NOT confirmed people or independent agents. MCP HTTP requests are NOT sessions or distinct agents. Campaign is a self-reported hint. Previous traffic before deployment is unknown.'}

    def wave2_event(self, tool: str, identity: str, stage: str, outcome: str,
                    channel: str, internal: bool = False):
        with self.connection() as db:
            db.execute('''INSERT INTO wave2_events(at,tool,identity,stage,outcome,channel,internal)
                          VALUES(?,?,?,?,?,?,?)''',
                       (int(time.time()),tool,identity,stage,outcome,channel,int(internal)))

    def wave2_metrics(self, since: int | None = None):
        after = int(since or (time.time()-30*86400))
        with self.connection() as db:
            rows = db.execute('''SELECT tool,stage,outcome,channel,COUNT(*) AS events,
                         COUNT(DISTINCT CASE WHEN channel!='mcp' THEN identity END) AS estimated_network_ids
                         FROM wave2_events WHERE at>=? AND internal=0
                         GROUP BY tool,stage,outcome,channel ORDER BY tool,stage,outcome,channel''',(after,)).fetchall()
            returns = db.execute('''SELECT tool,COUNT(*) AS estimated_returning_network_ids FROM
                         (SELECT tool,identity,COUNT(DISTINCT DATE(at,'unixepoch')) AS days
                          FROM wave2_events WHERE at>=? AND internal=0 AND channel='rest'
                            AND stage='launch' AND outcome IN ('ok','issues')
                          GROUP BY tool,identity) WHERE days>=2 GROUP BY tool''',(after,)).fetchall()
            interest_after_launch = db.execute('''SELECT i.tool,
                         COUNT(DISTINCT i.identity) AS estimated_network_ids
                         FROM wave2_events AS i
                         WHERE i.at>=? AND i.internal=0 AND i.channel='rest'
                           AND i.stage='paid_demand_signal'
                           AND EXISTS (SELECT 1 FROM wave2_events AS l
                                       WHERE l.tool=i.tool AND l.identity=i.identity
                                         AND l.at>=? AND l.at<=i.at AND l.internal=0
                                         AND l.channel='rest' AND l.stage='launch'
                                         AND l.outcome IN ('ok','issues'))
                         GROUP BY i.tool''',(after,after)).fetchall()
            tests = db.execute('''SELECT tool,stage,COUNT(*) AS events FROM wave2_events
                                  WHERE at>=? AND internal=1 GROUP BY tool,stage''',(after,)).fetchall()
            return {'window_start_unix':after, 'funnel_events':[dict(r) for r in rows],
                    'estimated_rest_returning_network_ids':{r['tool']:r['estimated_returning_network_ids'] for r in returns},
                    'estimated_rest_interest_after_launch_network_ids':{r['tool']:r['estimated_network_ids'] for r in interest_after_launch},
                    'internal_test_events':[dict(r) for r in tests],
                    'note':'HMAC network IDs are not people. MCP uses one shared identity and cannot yield unique agents or return rate. Returns require successful launches on distinct UTC days. Discovery counts are exposures, not users. Interest is self-reported, and linked interest is not payment intent verification.'}

    def prune(self):
        now = int(time.time())
        with self.connection() as db:
            db.execute('DELETE FROM discovery_events WHERE at<?', (now-30*86400,))
            db.execute('DELETE FROM events WHERE at<?', (now-30*86400,))
            db.execute('DELETE FROM lab_events WHERE at<?', (now-30*86400,))
            db.execute('DELETE FROM wave2_events WHERE at<?', (now-30*86400,))
            db.execute('DELETE FROM results WHERE expires_at<?', (now-7*86400,))
            db.execute('DELETE FROM gaps WHERE last_seen<?', (now-90*86400,))
            db.execute("DELETE FROM counters WHERE bucket LIKE 'day:%' AND bucket<?", (f'day:{time.strftime("%Y%m%d",time.gmtime(now-3*86400))}',))
