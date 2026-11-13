"""Durable local event queue. No external HTTP delivery is performed."""
import json
import re
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager


class ValidationError(ValueError):
    pass


class ConflictError(ValueError):
    pass


def validate(data):
    if not isinstance(data, dict) or set(data) != {'event_id', 'event_type', 'payload'}:
        raise ValidationError('Use exactly event_id, event_type, and payload.')
    for key in ('event_id', 'event_type'):
        if not isinstance(data[key], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', data[key]):
            raise ValidationError(f'{key} must contain 1–80 letters, digits, dots, underscores or hyphens.')
    if not isinstance(data['payload'], dict):
        raise ValidationError('payload must be a JSON object.')
    if set(data['payload']) - {'ticket_id', 'priority', 'summary', 'fail_until'}:
        raise ValidationError('Demo payload allows ticket_id, priority, summary, fail_until only.')
    for key in ('ticket_id', 'priority', 'summary'):
        if key in data['payload'] and (not isinstance(data['payload'][key], str) or len(data['payload'][key]) > 200):
            raise ValidationError(f'{key} must be text up to 200 characters.')
    failures = data['payload'].get('fail_until', 0)
    if type(failures) is not int or not 0 <= failures <= 10:
        raise ValidationError('fail_until must be an integer from 0 to 10.')
    return data


class Queue:
    def __init__(self, path, clock=None):
        self.path = str(path)
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL, next_attempt REAL, error TEXT);
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(event_id),
                attempt INTEGER NOT NULL, at REAL NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            with db:
                yield db
        finally:
            db.close()

    def submit(self, data):
        validate(data)
        payload = json.dumps(data['payload'], sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM events WHERE event_id=?', (data['event_id'],)).fetchone()
            if old:
                if old['event_type'] != data['event_type'] or old['payload'] != payload:
                    raise ConflictError('This event_id already belongs to a different event.')
                return dict(old), False
            db.execute('INSERT INTO events VALUES (?,?,?, ?,0,?,NULL,NULL)',
                       (data['event_id'], data['event_type'], payload, 'pending', self.clock()))
            return dict(db.execute('SELECT * FROM events WHERE event_id=?', (data['event_id'],)).fetchone()), True

    def list(self):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM events ORDER BY created DESC, event_id LIMIT 200').fetchall()
            total = db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            counts = dict(db.execute('SELECT status, COUNT(*) FROM events GROUP BY status').fetchall())
            return {'events': [dict(r) for r in rows], 'total': total, 'counts': counts}

    def detail(self, event_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM events WHERE event_id=?', (event_id,)).fetchone()
            if row is None:
                return None
            return {'event': dict(row), 'history': [dict(r) for r in db.execute(
                'SELECT * FROM attempts WHERE event_id=? ORDER BY id', (event_id,))]}

    def process(self):
        """One local simulation per call; lock keeps concurrent workers from double processing."""
        now = self.clock()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM events WHERE status='pending' OR (status='retry_wait' AND next_attempt<=?) ORDER BY created,event_id LIMIT 1", (now,)).fetchone()
            if row is None:
                return None
            attempt = row['attempts'] + 1
            fails = json.loads(row['payload']).get('fail_until', 0)
            failed = attempt <= fails
            status = ('dead_letter' if attempt >= 3 else 'retry_wait') if failed else 'succeeded'
            due = now + 2 ** attempt if status == 'retry_wait' else None
            error = 'Simulated transient failure' if failed else None
            db.execute('UPDATE events SET status=?,attempts=?,next_attempt=?,error=? WHERE event_id=?',
                       (status, attempt, due, error, row['event_id']))
            db.execute('INSERT INTO attempts(event_id,attempt,at,outcome,detail) VALUES (?,?,?,?,?)',
                       (row['event_id'], attempt, now, status, error or 'Local simulation completed; no external delivery.'))
            return {'event_id': row['event_id'], 'status': status, 'attempt': attempt, 'next_attempt': due}
