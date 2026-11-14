"""Persistent accounts, opaque cookie sessions and encrypted provider settings."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import contextmanager

SESSION_SECONDS = 12 * 60 * 60
COOKIE = 'kun_global_session'


def password_hash(password):
    if not 12 <= len(password) <= 256:
        raise ValueError('Mật khẩu cần từ 12 đến 256 ký tự.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def password_matches(password, encoded):
    try:
        data = base64.b64decode(encoded, validate=True)
        digest = hashlib.scrypt(password.encode(), salt=data[:16], n=16384, r=8, p=1)
        return hmac.compare_digest(data[16:], digest)
    except (ValueError, TypeError):
        return False


def username_value(value):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}', value):
        raise ValueError('Tên đăng nhập cần 3–64 ký tự: chữ, số, dấu chấm, gạch ngang hoặc gạch dưới.')
    return value.lower()


def public_user(row):
    return {key: row[key] for key in ('id', 'username', 'role', 'active', 'created_at')}


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def init(self):
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users(
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','user')),
                    active INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS login_failures(
                    identity TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS usage(
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS history(
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    input TEXT NOT NULL, output TEXT NOT NULL, source TEXT NOT NULL,
                    target TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chatgpt_connections(
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    issuer TEXT NOT NULL, subject TEXT NOT NULL, client_id TEXT NOT NULL,
                    credentials TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
                    UNIQUE(issuer,subject));
                CREATE TABLE IF NOT EXISTS chatgpt_attempts(
                    state_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    actor_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    session_hash TEXT NOT NULL, payload TEXT NOT NULL, expires INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', message TEXT NOT NULL DEFAULT '');
            ''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(chatgpt_attempts)')}
            if 'actor_id' not in columns:
                db.execute('ALTER TABLE chatgpt_attempts ADD COLUMN actor_id TEXT REFERENCES users(id) ON DELETE CASCADE')
            db.execute('UPDATE chatgpt_attempts SET actor_id=user_id WHERE actor_id IS NULL')
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def cipher(self):
        from cryptography.fernet import Fernet
        keyfile = self.path.parent / 'master.key'
        try:
            fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(Fernet.generate_key())
        return Fernet(keyfile.read_bytes())

    def create_user(self, username, password, role='user'):
        username = username_value(username)
        if role not in ('admin', 'user'):
            raise ValueError('Vai trò không hợp lệ.')
        row = dict(id=uuid.uuid4().hex, username=username, role=role, active=1, created_at=int(time.time()))
        try:
            with self.connect() as db:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                           (row['id'], username, password_hash(password), role, 1, row['created_at']))
        except sqlite3.IntegrityError:
            raise ValueError('Tên đăng nhập đã tồn tại.')
        return row

    def login(self, username, password, ip):
        now = int(time.time())
        identity = hashlib.sha256((ip + ':' + username.lower()).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            failure = db.execute('SELECT * FROM login_failures WHERE identity=?', (identity,)).fetchone()
            if failure and failure['expires'] > now and failure['count'] >= 5:
                raise BlockingIOError('Đăng nhập sai nhiều lần. Vui lòng thử lại sau 15 phút.')
            row = db.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE', (username,)).fetchone()
            # Pay the same password hashing cost even for an unknown username.
            valid = password_matches(password, row['password_hash']) if row else bool(
                hashlib.scrypt(password.encode(), salt=b'kun-dummy-salt!!', n=16384, r=8, p=1) and False)
            if not valid or not row['active']:
                count = failure['count'] + 1 if failure and failure['expires'] > now else 1
                db.execute('INSERT OR REPLACE INTO login_failures VALUES(?,?,?)', (identity, count, now + 900))
                # Commit failures before raising.
                db.commit()
                raise ValueError('Tên đăng nhập hoặc mật khẩu không đúng.')
            db.execute('DELETE FROM login_failures WHERE identity=?', (identity,))
        return public_user(row), self.new_session(row['id'])

    def new_session(self, user_id):
        token = secrets.token_urlsafe(48)
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (int(time.time()),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), user_id, int(time.time()) + SESSION_SECONDS))
        return token

    def account_for(self, token):
        if not token or len(token) > 256:
            return None
        with self.connect() as db:
            row = db.execute('''SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id
                WHERE s.token_hash=? AND s.expires>? AND u.active=1''',
                (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        return public_user(row) if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def users(self):
        with self.connect() as db:
            return [public_user(row) for row in db.execute('SELECT * FROM users ORDER BY created_at,username')]

    def managed_users(self):
        with self.connect() as db:
            rows = db.execute('''SELECT u.*,
                (SELECT COUNT(*) FROM sessions s WHERE s.user_id=u.id AND s.expires>?) AS active_sessions,
                (SELECT COUNT(*) FROM history h WHERE h.user_id=u.id) AS history_count
                FROM users u ORDER BY u.created_at,u.username''', (int(time.time()),))
            return [{**public_user(row), 'active_sessions': row['active_sessions'],
                     'history_count': row['history_count']} for row in rows]

    def revoke_sessions(self, user_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
                raise LookupError('Không tìm thấy tài khoản.')
            count = db.execute('SELECT COUNT(*) FROM sessions WHERE user_id=? AND expires>?',
                (user_id, int(time.time()))).fetchone()[0]
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        return count

    def delete_user(self, user_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
            if not row:
                raise LookupError('Không tìm thấy tài khoản.')
            if row['role'] != 'user':
                raise ValueError('Chỉ có thể xóa tài khoản người dùng.')
            db.execute('DELETE FROM usage WHERE user_id=?', (user_id,))
            db.execute('DELETE FROM users WHERE id=?', (user_id,))

    def update_user(self, user_id, changes, actor_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not row:
                raise LookupError('Không tìm thấy tài khoản.')
            username = username_value(changes.get('username', row['username']))
            role = changes.get('role', row['role'])
            active = int(changes.get('active', row['active']))
            if role not in ('admin', 'user') or active not in (0, 1):
                raise ValueError('Vai trò hoặc trạng thái không hợp lệ.')
            if user_id == actor_id and not active:
                raise ValueError('Không thể khóa tài khoản đang đăng nhập.')
            if row['role'] == 'admin' and row['active'] and (role != 'admin' or not active):
                count = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
                if count <= 1:
                    raise ValueError('Cần giữ ít nhất một quản trị viên hoạt động.')
            hashed = password_hash(changes['password']) if changes.get('password') else row['password_hash']
            try:
                db.execute('UPDATE users SET username=?,role=?,active=?,password_hash=? WHERE id=?',
                           (username, role, active, hashed, user_id))
            except sqlite3.IntegrityError:
                raise ValueError('Tên đăng nhập đã tồn tại.')
            if hashed != row['password_hash'] or role != row['role'] or not active:
                db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
            return public_user(db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone())

    def change_password(self, user_id, current, new):
        with self.connect() as db:
            row = db.execute('SELECT password_hash FROM users WHERE id=?', (user_id,)).fetchone()
        if not row or not password_matches(current, row[0]):
            raise ValueError('Mật khẩu hiện tại không đúng.')
        self.update_user(user_id, {'password': new}, user_id)
        return self.new_session(user_id)

    def provider(self):
        with self.connect() as db:
            settings = dict(db.execute('SELECT key,value FROM settings'))
        key = os.getenv('OPENAI_API_KEY', '').strip()
        if settings.get('openai_key'):
            key = self.cipher().decrypt(settings['openai_key'].encode()).decode()
        return {'key': key, 'model': settings.get('openai_model') or os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')}

    def configure_provider(self, model, key=None, clear_key=False):
        if not re.fullmatch(r'[a-zA-Z0-9._:-]{1,120}', model):
            raise ValueError('Tên mô hình không hợp lệ.')
        if key is not None and not 20 <= len(key.strip()) <= 512:
            raise ValueError('Khóa API không hợp lệ.')
        encrypted = self.cipher().encrypt(key.strip().encode()).decode() if key is not None else None
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', ('openai_model', model))
            if clear_key:
                db.execute('DELETE FROM settings WHERE key=?', ('openai_key',))
            elif encrypted:
                db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', ('openai_key', encrypted))

    def record_usage(self, user_id, model, input_tokens, output_tokens):
        owner = user_id or 'system'
        with self.connect() as db:
            db.execute('''INSERT INTO usage(user_id,model,input_tokens,output_tokens,created_at)
                SELECT ?,?,?,?,? WHERE ?='system' OR EXISTS (SELECT 1 FROM users WHERE id=?)''',
                (owner, model, input_tokens, output_tokens, int(time.time()), owner, owner))

    def usage(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT u.username, g.model, COUNT(*) AS requests,
                SUM(g.input_tokens) AS input_tokens, SUM(g.output_tokens) AS output_tokens
                FROM usage g LEFT JOIN users u ON u.id=g.user_id
                WHERE g.created_at>? GROUP BY g.user_id,g.model ORDER BY requests DESC''',
                (int(time.time()) - 30 * 86400,))]

    def history(self, user_id):
        with self.connect() as db:
            rows = db.execute('SELECT id,input,output,source,target,created_at AS date FROM history WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 30', (user_id,))
            return [dict(row) for row in rows]

    def add_history(self, user_id, body):
        from datetime import datetime, timezone
        with self.connect() as db:
            db.execute('INSERT INTO history VALUES(?,?,?,?,?,?,?)', (uuid.uuid4().hex, user_id,
                body.input, body.output, body.source, body.target, datetime.now(timezone.utc).isoformat()))
            db.execute('DELETE FROM history WHERE user_id=? AND id NOT IN (SELECT id FROM history WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 30)', (user_id, user_id))
        return self.history(user_id)

    def clear_history(self, user_id, entry_id=None):
        with self.connect() as db:
            if entry_id is None:
                db.execute('DELETE FROM history WHERE user_id=?', (user_id,))
            else:
                db.execute('DELETE FROM history WHERE user_id=? AND id=?', (user_id, entry_id))


store = Store(os.getenv('DATABASE_PATH', 'data/kun-global.sqlite'))
