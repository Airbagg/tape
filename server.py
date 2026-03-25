import http.server
import urllib.request
import urllib.parse
import ssl
import os
import json
import re
import psycopg2
import psycopg2.extras
import hashlib
import time
import secrets
import base64
import io
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    from mutagen.id3 import ID3
    from mutagen.mp4 import MP4
    from mutagen.flac import FLAC
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

def read_tags(filepath):
    if not HAS_MUTAGEN:
        return {}
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.mp3':
            tags = ID3(filepath)
            def get_tag(t):
                if t is None: return None
                if hasattr(t, 'text') and t.text: return str(t.text[0])
                return str(t)
            return {
                'title': get_tag(tags.get('TIT2')),
                'artist': get_tag(tags.get('TPE1')),
                'album': get_tag(tags.get('TALB')),
            }
        elif ext == '.m4a':
            tags = MP4(filepath)
            return {
                'title': (tags.get('©nam') or [None])[0],
                'artist': (tags.get('©ART') or [None])[0],
                'album': (tags.get('©alb') or [None])[0],
            }
        elif ext == '.flac':
            tags = FLAC(filepath)
            return {
                'title': (tags.get('title') or [None])[0],
                'artist': (tags.get('artist') or [None])[0],
                'album': (tags.get('album') or [None])[0],
            }
    except Exception:
        pass
    return {}

def parse_multipart(rfile, headers):
    ct = headers.get('Content-Type', '')
    length = int(headers.get('Content-Length', 0))
    boundary = None
    for p in ct.split(';'):
        p = p.strip()
        if p.startswith('boundary='):
            boundary = p[9:].strip('"').encode()
    if not boundary:
        return {}, {}
    body = rfile.read(length)
    fields = {}
    files = {}
    SEP = b'\r\n'
    for part in body.split(b'--' + boundary)[1:]:
        if part[:2] == b'--':
            continue
        if SEP + SEP not in part:
            continue
        head, _, data = part.partition(SEP + SEP)
        data = data.rstrip(SEP)
        name = None
        filename = None
        for line in head.decode('utf-8', errors='replace').split('\r\n'):
            if 'Content-Disposition' in line:
                for tok in line.split(';'):
                    tok = tok.strip()
                    if tok.startswith('name='):
                        name = tok[5:].strip('"')
                    elif tok.startswith('filename='):
                        filename = tok[9:].strip('"')
        if name is None:
            continue
        if filename:
            files[name] = {'filename': filename, 'data': data}
        else:
            fields[name] = data.decode('utf-8', errors='replace')
    return fields, files

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TRACKS_DIR  = os.path.join(BASE_DIR, 'tracks')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
SUPPORTED   = ('.mp3', '.m4a', '.flac', '.wav', '.ogg')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOADS_DIR, 'photos'), exist_ok=True)
os.makedirs(os.path.join(UPLOADS_DIR, 'music'), exist_ok=True)

SECRET_KEY  = 'tape_secret_change_in_production'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'mmcannel@gmail.com')
ADMIN_PASS  = os.environ.get('ADMIN_PASS', 'admin1234')
TRIAL_DAYS  = 2
SUB_PRICE   = 299

TG_BOT_TOKEN = '8729241382:AAHelxuQXziTWAF0s6edOggzNuV3uI5k2Hg'
TG_ADMIN_CHAT = '464389692'

_tg_verify_codes = {}

# ── БД ──────────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn

def init_db():
    with get_db() as db:
        cur = db.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id         SERIAL PRIMARY KEY,
                email      TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                role       TEXT DEFAULT 'user',
                trial_ends BIGINT,
                sub_active INTEGER DEFAULT 0,
                sub_ends   BIGINT,
                last_seen  BIGINT DEFAULT 0,
                created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS artists (
                name    TEXT PRIMARY KEY,
                photo   TEXT,
                bio     TEXT,
                updated BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER,
                expires_at BIGINT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS track_state (
                id         TEXT PRIMARY KEY,
                enabled    INTEGER DEFAULT 1,
                reason     TEXT DEFAULT ''
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_likes (
                user_id    INTEGER,
                track_key  TEXT,
                PRIMARY KEY (user_id, track_key)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_plugins (
                user_id    INTEGER PRIMARY KEY,
                data       TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS album_meta (
                id            TEXT PRIMARY KEY,
                type          TEXT DEFAULT 'album',
                year          TEXT,
                extra_artists TEXT,
                cover_url     TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_bans (
                user_id   INTEGER PRIMARY KEY,
                reason    TEXT,
                ban_type  TEXT DEFAULT 'email',
                banned_by TEXT,
                banned_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sub_grants (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER,
                days       INTEGER,
                amount     INTEGER DEFAULT 0,
                source     TEXT DEFAULT 'admin',
                note       TEXT DEFAULT '',
                created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
            )
        ''')
        cur.execute('SELECT id FROM users WHERE email=%s', (ADMIN_EMAIL,))
        existing = cur.fetchone()
        if not existing:
            cur.execute('INSERT INTO users (email,password,role,sub_active) VALUES (%s,%s,%s,1)',
                       (ADMIN_EMAIL, hash_password(ADMIN_PASS), 'admin'))
        db.commit()
    print('   DB: PostgreSQL via Supabase')

# ── Auth ─────────────────────────────────────────────────
def tg_send(chat_id, text):
    if not TG_BOT_TOKEN or not chat_id:
        return False
    try:
        data = json.dumps({'chat_id': chat_id, 'text': text}).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        print('TG error:', e)
        return False


def hash_password(pw):
    return hashlib.sha256((pw + SECRET_KEY).encode()).hexdigest()

def make_token(user_id):
    token = secrets.token_hex(32)
    with get_db() as db:
        cur = db.cursor()
        cur.execute('INSERT INTO tokens (token,user_id,expires_at) VALUES (%s,%s,%s)',
                   (token, user_id, int(time.time()) + 86400*30))
        db.commit()
    return token

def get_user_by_token(token):
    if not token: return None
    now = int(time.time())
    with get_db() as db:
        cur = db.cursor()
        cur.execute('''SELECT u.* FROM users u JOIN tokens t ON t.user_id=u.id
                       WHERE t.token=%s AND t.expires_at>%s''', (token, now))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE users SET last_seen=%s WHERE id=%s', (now, row['id']))
            db.commit()
    return dict(row) if row else None

def get_token_from_headers(headers):
    auth = headers.get('Authorization', '')
    return auth[7:] if auth.startswith('Bearer ') else None

def check_access(user):
    if not user: return False, 'unauthorized'
    if user['role'] == 'admin': return True, 'admin'
    if user['sub_active']:
        if not user['sub_ends'] or user['sub_ends'] > int(time.time()):
            return True, 'subscriber'
        with get_db() as db:
            cur = db.cursor()
            cur.execute('UPDATE users SET sub_active=0 WHERE id=%s', (user['id'],))
            db.commit()
    if user['trial_ends'] and user['trial_ends'] > int(time.time()):
        return True, 'trial'
    return False, 'no_access'

# ── Сканирование треков ──────────────────────────────────
def track_id(artist_folder, album_folder, fname):
    return f'{artist_folder}/{album_folder}/{fname}'

def scan_library(include_disabled=False):
    with get_db() as db:
        cur = db.cursor()
        cur.execute('SELECT id, enabled, reason FROM track_state')
        rows = cur.fetchall()
    states = {r['id']: {'enabled': bool(r['enabled']), 'reason': r['reason']} for r in rows}

    library = {}
    if not os.path.isdir(TRACKS_DIR):
        return library

    for artist_folder in sorted(os.listdir(TRACKS_DIR)):
        artist_path = os.path.join(TRACKS_DIR, artist_folder)
        if not os.path.isdir(artist_path): continue

        for album_folder in sorted(os.listdir(artist_path)):
            album_path = os.path.join(artist_path, album_folder)
            if not os.path.isdir(album_path): continue

            album_id = f'{artist_folder}/{album_folder}'
            album_state = states.get(album_id, {})
            album_enabled = album_state.get('enabled', True)
            album_reason = album_state.get('reason', '')

            cover_url = None
            for name in ['cover.jpg','cover.png','folder.jpg','artwork.jpg']:
                if os.path.exists(os.path.join(album_path, name)):
                    cover_url = f'/tracks/{urllib.parse.quote(artist_folder)}/{urllib.parse.quote(album_folder)}/{name}'
                    break

            af = os.path.join(album_path, 'artists.txt')
            if os.path.exists(af):
                with open(af, encoding='utf-8') as f:
                    raw = [a.strip() for a in f.read().split(',') if a.strip()]
                all_artists = list(dict.fromkeys(raw))
            else:
                all_artists = [artist_folder]

            tracks = []
            for fname in sorted(os.listdir(album_path)):
                if not fname.lower().endswith(SUPPORTED): continue
                tid = track_id(artist_folder, album_folder, fname)
                t_state = states.get(tid, {})
                t_enabled = album_enabled and t_state.get('enabled', True)
                t_reason = t_state.get('reason', '') or album_reason

                fpath_full = os.path.join(album_path, fname)
                tags = read_tags(fpath_full)
                title = tags.get('title') or re.sub(r'^\d+[\s\-_.]+', '', os.path.splitext(fname)[0]).strip()
                url = f'/tracks/{urllib.parse.quote(artist_folder)}/{urllib.parse.quote(album_folder)}/{urllib.parse.quote(fname)}'
                track = {
                    'id': tid,
                    'title': title,
                    'artist': ', '.join(all_artists),
                    'album': album_folder,
                    'url': url,
                    'cover': cover_url,
                    'enabled': t_enabled,
                    'reason': t_reason,
                }
                if include_disabled or t_enabled:
                    tracks.append(track)
                elif not include_disabled:
                    tracks.append({**track, 'disabled': True})

            if not tracks: continue

            seen_key = album_id
            for artist in all_artists:
                if artist not in library: library[artist] = {}
                if album_folder not in library[artist]:
                    library[artist][album_folder] = {
                        'tracks': tracks,
                        'cover': cover_url,
                        'enabled': album_enabled,
                        'reason': album_reason,
                        '_src': seen_key,
                    }
                elif library[artist][album_folder].get('_src') != seen_key:
                    pass

    return library

# ── Сохранение загруженного файла ────────────────────────
def save_upload(data, filename, subfolder):
    safe = re.sub(r'[^\w\-_.]', '_', filename)
    path = os.path.join(UPLOADS_DIR, subfolder, safe)
    with open(path, 'wb') as f:
        f.write(data)
    return f'/uploads/{subfolder}/{safe}'

# ── HTTP Handler ─────────────────────────────────────────
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def current_user(self):
        return get_user_by_token(get_token_from_headers(self.headers))

    def serve_file(self, path):
        try:
            fpath = os.path.join(BASE_DIR, urllib.parse.unquote(path.lstrip('/')))
            if not os.path.isfile(fpath):
                return False
            ext = os.path.splitext(fpath)[1].lower()
            mt = {'.html':'text/html','.js':'application/javascript','.css':'text/css',
                  '.mp3':'audio/mpeg','.m4a':'audio/mp4','.flac':'audio/flac',
                  '.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png',
                  '.svg':'image/svg+xml','.wav':'audio/wav','.ogg':'audio/ogg'}.get(ext,'application/octet-stream')

            file_size = os.path.getsize(fpath)
            range_header = self.headers.get('Range')

            if range_header and ext in ('.mp3', '.m4a', '.flac', '.wav', '.ogg'):
                ranges = range_header.replace('bytes=', '').split('-')
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header('Content-Type', mt)
                self.send_header('Content-Length', length)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                with open(fpath, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk: break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                self.send_response(200)
                self.send_header('Content-Type', mt)
                self.send_header('Content-Length', file_size)
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                with open(fpath, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk: break
                        self.wfile.write(chunk)
            return True
        except: pass
        return False

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/api/auth/me':
            user = self.current_user()
            if not user: return self.send_json({'error':'unauthorized'}, 401)
            ok, reason = check_access(user)
            trial_left = max(0,(user['trial_ends'] or 0)-int(time.time()))//3600 if user['trial_ends'] else 0
            self.send_json({'id':user['id'],'email':user['email'],'role':user['role'],
                            'access':ok,'reason':reason,'trial_ends':user['trial_ends'],
                            'trial_hours_left':trial_left,'sub_active':bool(user['sub_active'])})

        elif path == '/library':
            user = self.current_user()
            ok, reason = check_access(user)
            if not ok: return self.send_json({'error':reason}, 403)
            self.send_json(scan_library(include_disabled=False))

        elif path == '/api/library/admin':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            self.send_json(scan_library(include_disabled=True))

        elif path == '/api/artists':
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT * FROM artists ORDER BY name')
                rows = cur.fetchall()
            self.send_json([dict(r) for r in rows])

        elif path.startswith('/api/artists/'):
            name = urllib.parse.unquote(path[len('/api/artists/'):])
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT * FROM artists WHERE name=%s', (name,))
                row = cur.fetchone()
            self.send_json(dict(row) if row else {'name':name,'photo':None,'bio':None})

        elif path == '/api/users':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT id,email,role,trial_ends,sub_active,sub_ends,created_at FROM users ORDER BY created_at DESC')
                rows = cur.fetchall()
                cur.execute('SELECT * FROM user_bans')
                bans = {r['user_id']:dict(r) for r in cur.fetchall()}
            result = []
            for r in rows:
                u = dict(r)
                u['banned'] = u['id'] in bans
                u['ban_reason'] = bans.get(u['id'],{}).get('reason','')
                result.append(u)
            self.send_json(result)

        elif path.startswith('/api/users/'):
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            uid = int(path.split('/')[-1])
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT id,email,role,trial_ends,sub_active,sub_ends,created_at FROM users WHERE id=%s', (uid,))
                row = cur.fetchone()
                cur.execute('SELECT * FROM user_bans WHERE user_id=%s', (uid,))
                ban = cur.fetchone()
                cur.execute('SELECT COUNT(*) as cnt FROM user_likes WHERE user_id=%s', (uid,))
                likes = cur.fetchone()['cnt']
                try:
                    cur.execute('SELECT * FROM sub_grants WHERE user_id=%s ORDER BY created_at DESC LIMIT 5', (uid,))
                    grant_history = [dict(g) for g in cur.fetchall()]
                except:
                    grant_history = []
            if not row: return self.send_json({'error':'not found'}, 404)
            u = dict(row)
            u['banned']        = ban is not None
            u['ban_reason']    = ban['reason'] if ban else ''
            u['play_count']    = 0
            u['likes_count']   = likes
            u['grant_history'] = grant_history
            self.send_json(u)

        elif path == '/api/album-meta':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT * FROM album_meta')
                rows = cur.fetchall()
            self.send_json([dict(r) for r in rows])

        elif path.startswith('/api/album-meta/'):
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            album_id = urllib.parse.unquote(path[len('/api/album-meta/'):])
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT * FROM album_meta WHERE id=%s', (album_id,))
                row = cur.fetchone()
            self.send_json(dict(row) if row else {'id':album_id,'type':'album','year':'','extra_artists':'','cover_url':''})

        elif path == '/api/likes':
            user = self.current_user()
            if not user: return self.send_json({'error':'unauthorized'}, 401)
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT track_key FROM user_likes WHERE user_id=%s', (user['id'],))
                rows = cur.fetchall()
            self.send_json([r['track_key'] for r in rows])

        elif path == '/api/plugins':
            user = self.current_user()
            if not user: return self.send_json({'error':'unauthorized'}, 401)
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT data FROM user_plugins WHERE user_id=%s', (user['id'],))
                row = cur.fetchone()
            self.send_json(json.loads(row['data']) if row else [])

        elif path == '/lastfm':
            parsed = urllib.parse.urlparse(self.path)
            url = f'https://ws.audioscrobbler.com/2.0/?{parsed.query}'
            try:
                req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ctx) as r: data = r.read()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(data)
            except: self.send_response(500); self.end_headers()

        elif path == '/api/stats':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            now = int(time.time())
            with get_db() as db:
                cur = db.cursor()
                cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role!='admin'")
                total_users = cur.fetchone()['cnt']
                cur.execute("SELECT COUNT(*) as cnt FROM users WHERE sub_active=1 AND (sub_ends IS NULL OR sub_ends>%s) AND role!='admin'", (now,))
                active_subs = cur.fetchone()['cnt']
                cur.execute("SELECT COUNT(*) as cnt FROM users WHERE trial_ends>%s AND sub_active=0 AND role!='admin'", (now,))
                trial_users = cur.fetchone()['cnt']
                cur.execute("SELECT COUNT(*) as cnt FROM users WHERE (trial_ends IS NULL OR trial_ends<=%s) AND (sub_active=0 OR sub_ends<=%s) AND role!='admin'", (now,now))
                expired_users = cur.fetchone()['cnt']
                try:
                    cur.execute('SELECT COUNT(*) as cnt FROM users WHERE last_seen>%s', (now-300,))
                    online_users = cur.fetchone()['cnt']
                except:
                    online_users = 0
                cur.execute('SELECT COUNT(*) as cnt FROM user_bans')
                banned_users = cur.fetchone()['cnt']
                cur.execute('SELECT COUNT(*) as cnt FROM user_likes')
                total_likes = cur.fetchone()['cnt']
                try:
                    cur.execute("SELECT COALESCE(SUM(amount),0) as s FROM sub_grants WHERE source='payment' OR source IS NULL AND amount>0")
                    revenue = cur.fetchone()['s']
                except:
                    revenue = 0
                cur.execute('SELECT COUNT(*) as cnt FROM users WHERE created_at>=%s', (now-86400,))
                new_today = cur.fetchone()['cnt']
                cur.execute('SELECT COUNT(*) as cnt FROM users WHERE created_at>=%s', (now-86400*7,))
                new_week = cur.fetchone()['cnt']

                regs = []
                for i in range(6, -1, -1):
                    d0 = now - 86400*(i+1)
                    d1 = now - 86400*i
                    cur.execute('SELECT COUNT(*) as cnt FROM users WHERE created_at>=%s AND created_at<%s', (d0,d1))
                    cnt = cur.fetchone()['cnt']
                    regs.append({'day':i,'ts':d1,'count':cnt})

                subs_7d = []
                for i in range(6, -1, -1):
                    d0 = now - 86400*(i+1)
                    d1 = now - 86400*i
                    try:
                        cur.execute("SELECT COUNT(*) as cnt FROM sub_grants WHERE source='payment' AND created_at>=%s AND created_at<%s", (d0,d1))
                        cnt = cur.fetchone()['cnt']
                        cur.execute("SELECT COALESCE(SUM(amount),0) as s FROM sub_grants WHERE source='payment' AND created_at>=%s AND created_at<%s", (d0,d1))
                        amt = cur.fetchone()['s']
                    except:
                        cnt, amt = 0, 0
                    subs_7d.append({'day':i,'ts':d1,'count':cnt,'amount':amt})

                try:
                    cur.execute('''SELECT sg.*, u.email FROM sub_grants sg
                                   JOIN users u ON u.id=sg.user_id
                                   ORDER BY sg.created_at DESC LIMIT 8''')
                    recent_grants = [dict(g) for g in cur.fetchall()]
                except:
                    recent_grants = []

            lib = scan_library(include_disabled=True)
            total_tracks  = sum(len(al['tracks']) for ar in lib.values() for al in ar.values())
            total_albums  = sum(len(ar) for ar in lib.values())
            total_artists = len(lib)

            self.send_json({
                'total_users':      total_users,
                'active_subs':      active_subs,
                'trial_users':      trial_users,
                'expired_users':    expired_users,
                'online_users':     online_users,
                'banned_users':     banned_users,
                'total_likes':      total_likes,
                'revenue':          revenue,
                'new_today':        new_today,
                'new_week':         new_week,
                'registrations_7d': regs,
                'subscriptions_7d': subs_7d,
                'recent_grants':    recent_grants,
                'total_tracks':     total_tracks,
                'total_albums':     total_albums,
                'total_artists':    total_artists,
            })

        elif path == '/itunes':
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if params.get('lookup') and params.get('id'):
                url = f'https://itunes.apple.com/lookup?id={params["id"][0]}&entity={urllib.parse.quote(params.get("entity",["song"])[0])}&limit=50'
            else:
                q=params.get('q',[''])[0]; entity=params.get('entity',['song'])[0]; limit=params.get('limit',['25'])[0]
                url = f'https://itunes.apple.com/search?term={urllib.parse.quote(q)}&{"media=music&entity=song&" if entity=="song" else f"entity={urllib.parse.quote(entity)}&"}country=ru&limit={limit}'
            try:
                req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ctx) as r: data = r.read()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(data)
            except: self.send_response(500); self.end_headers()

        elif path.startswith('/uploads/') or path.startswith('/tracks/'):
            if not self.serve_file(path):
                self.send_response(404); self.end_headers()

        else:
            super().do_GET()

    def do_POST(self):
        path = self.path.split('?')[0]

        if path == '/api/auth/send-tg-code':
            body = self.read_body()
            email = (body.get('email') or '').strip().lower()
            if not email:
                return self.send_json({'error': 'email обязателен'}, 400)
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT id FROM users WHERE email=%s', (email,))
                exists = cur.fetchone()
            if exists:
                return self.send_json({'error': 'Email уже зарегистрирован'}, 409)
            code = str(secrets.randbelow(900000) + 100000)
            _tg_verify_codes[email] = {'code': code, 'expires': int(time.time()) + 600}
            msg = f'🎵 Tape — код подтверждения\n\nEmail: {email}\nКод: {code}\n\nДействует 10 минут.'
            sent = tg_send(TG_ADMIN_CHAT, msg)
            if not sent and not TG_BOT_TOKEN:
                return self.send_json({'ok': True, 'dev_code': code, 'dev_mode': True})
            if not sent:
                return self.send_json({'error': 'Не удалось отправить код. Попробуй позже.'}, 500)
            self.send_json({'ok': True})

        elif path == '/api/auth/verify-tg-code':
            body = self.read_body()
            email = (body.get('email') or '').strip().lower()
            code = str(body.get('code') or '').strip()
            entry = _tg_verify_codes.get(email)
            if not entry:
                return self.send_json({'error': 'Сначала запроси код'}, 400)
            if int(time.time()) > entry['expires']:
                del _tg_verify_codes[email]
                return self.send_json({'error': 'Код истёк, запроси новый'}, 400)
            if entry['code'] != code:
                return self.send_json({'error': 'Неверный код'}, 400)
            _tg_verify_codes[email]['verified'] = True
            self.send_json({'ok': True})

        elif path == '/api/auth/register':
            body = self.read_body()
            email = (body.get('email') or '').strip().lower()
            pw = body.get('password') or ''
            if not email or not pw: return self.send_json({'error':'email и пароль обязательны'}, 400)
            if len(pw) < 6: return self.send_json({'error':'Пароль минимум 6 символов'}, 400)
            if TG_BOT_TOKEN:
                entry = _tg_verify_codes.get(email)
                if not entry or not entry.get('verified'):
                    return self.send_json({'error':'Подтверди Telegram код'}, 403)
                del _tg_verify_codes[email]
            trial_ends = int(time.time()) + 86400*TRIAL_DAYS
            try:
                with get_db() as db:
                    cur = db.cursor()
                    cur.execute('INSERT INTO users (email,password,trial_ends) VALUES (%s,%s,%s)',
                               (email, hash_password(pw), trial_ends))
                    db.commit()
                    cur.execute('SELECT * FROM users WHERE email=%s', (email,))
                    user = cur.fetchone()
                token = make_token(user['id'])
                self.send_json({'token':token,'role':'user','trial_ends':trial_ends})
            except psycopg2.errors.UniqueViolation:
                self.send_json({'error':'Email уже зарегистрирован'}, 409)

        elif path == '/api/auth/login':
            body = self.read_body()
            email = (body.get('email') or '').strip().lower()
            pw = body.get('password') or ''
            with get_db() as db:
                cur = db.cursor()
                cur.execute('SELECT * FROM users WHERE email=%s AND password=%s',
                            (email, hash_password(pw)))
                user = cur.fetchone()
            if not user: return self.send_json({'error':'Неверный email или пароль'}, 401)
            token = make_token(user['id'])
            ok, reason = check_access(dict(user))
            self.send_json({'token':token,'role':user['role'],'access':ok,'reason':reason})

        elif path.startswith('/api/artists/'):
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            name = urllib.parse.unquote(path[len('/api/artists/'):])
            ct = self.headers.get('Content-Type','')
            if 'multipart/form-data' in ct:
                fields, files = parse_multipart(self.rfile, self.headers)
                photo_url = None
                if 'photo_file' in files:
                    fi = files['photo_file']
                    if fi['filename']:
                        ext = os.path.splitext(fi['filename'])[1].lower() or '.jpg'
                        safe_name = re.sub(r'[^\w]', '_', name)
                        photo_url = save_upload(fi['data'], safe_name + ext, 'photos')
                bio = fields.get('bio', '')
                photo = photo_url or fields.get('photo', '')
            else:
                body = self.read_body()
                photo = body.get('photo')
                bio = body.get('bio')
            with get_db() as db:
                cur = db.cursor()
                cur.execute('''INSERT INTO artists (name,photo,bio) VALUES (%s,%s,%s)
                              ON CONFLICT(name) DO UPDATE SET photo=EXCLUDED.photo,bio=EXCLUDED.bio,
                              updated=EXTRACT(EPOCH FROM NOW())::BIGINT''', (name, photo, bio))
                db.commit()
            self.send_json({'ok':True, 'photo': photo})

        elif path == '/api/track-state':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            body = self.read_body()
            tid = body.get('id')
            enabled = 1 if body.get('enabled', True) else 0
            reason = body.get('reason', '')
            with get_db() as db:
                cur = db.cursor()
                cur.execute('''INSERT INTO track_state (id,enabled,reason) VALUES (%s,%s,%s)
                              ON CONFLICT(id) DO UPDATE SET enabled=EXCLUDED.enabled,reason=EXCLUDED.reason''',
                           (tid, enabled, reason))
                db.commit()
            self.send_json({'ok':True})

        elif path == '/api/likes':
            user = self.current_user()
            if not user: return self.send_json({'error':'unauthorized'}, 401)
            body = self.read_body()
            key = body.get('key', '')
            action = body.get('action', 'add')
            with get_db() as db:
                cur = db.cursor()
                if action == 'add':
                    cur.execute('INSERT INTO user_likes (user_id,track_key) VALUES (%s,%s) ON CONFLICT DO NOTHING', (user['id'], key))
                else:
                    cur.execute('DELETE FROM user_likes WHERE user_id=%s AND track_key=%s', (user['id'], key))
                db.commit()
            self.send_json({'ok': True})

        elif path == '/api/plugins':
            user = self.current_user()
            if not user: return self.send_json({'error':'unauthorized'}, 401)
            body = self.read_body()
            with get_db() as db:
                cur = db.cursor()
                cur.execute('INSERT INTO user_plugins (user_id,data) VALUES (%s,%s) ON CONFLICT(user_id) DO UPDATE SET data=EXCLUDED.data',
                           (user['id'], json.dumps(body.get('plugins', []))))
                db.commit()
            self.send_json({'ok': True})

        elif path == '/api/upload/music':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            ct = self.headers.get('Content-Type','')
            if 'multipart/form-data' not in ct:
                return self.send_json({'error':'multipart required'}, 400)
            fields, files = parse_multipart(self.rfile, self.headers)
            artist = fields.get('artist', '').strip()
            album  = fields.get('album', '').strip()
            if not artist or not album:
                return self.send_json({'error':'artist и album обязательны'}, 400)
            album_path = os.path.join(TRACKS_DIR, artist, album)
            os.makedirs(album_path, exist_ok=True)
            saved = []
            for key, fi in files.items():
                if fi['filename']:
                    fpath = os.path.join(album_path, fi['filename'])
                    with open(fpath, 'wb') as fp:
                        fp.write(fi['data'])
                    saved.append(fi['filename'])
            self.send_json({'ok':True, 'saved':saved})

        elif path == '/api/admin/grant':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            body = self.read_body()
            uid = body.get('user_id')
            if body.get('revoke'):
                with get_db() as db:
                    cur = db.cursor()
                    cur.execute('UPDATE users SET sub_active=0,sub_ends=NULL WHERE id=%s', (uid,))
                    db.commit()
            else:
                days = int(body.get('days', 30))
                now = int(time.time())
                with get_db() as db:
                    cur = db.cursor()
                    cur.execute('SELECT sub_ends FROM users WHERE id=%s', (uid,))
                    cur_row = cur.fetchone()
                    base = max(cur_row['sub_ends'] or now, now)
                    sub_ends = base + 86400*days
                    cur.execute('UPDATE users SET sub_active=1,sub_ends=%s WHERE id=%s', (sub_ends, uid))
                    try:
                        cur.execute('INSERT INTO sub_grants (user_id,days,amount,source) VALUES (%s,%s,%s,%s)', (uid, days, 0, 'admin'))
                    except Exception:
                        pass
                    db.commit()
            self.send_json({'ok':True})

        elif path.startswith('/api/users/'):
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            parts = path.split('/')
            uid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
            action = parts[4] if len(parts) > 4 else None
            if not uid: return self.send_json({'error':'bad request'}, 400)
            body = self.read_body()
            with get_db() as db:
                cur = db.cursor()
                if action == 'role':
                    role = body.get('role','user')
                    cur.execute('UPDATE users SET role=%s WHERE id=%s', (role, uid))
                    db.commit()
                elif action == 'ban':
                    reason   = body.get('reason','')
                    ban_type = body.get('ban_type', 'email')
                    cur.execute('''INSERT INTO user_bans (user_id,reason,ban_type) VALUES (%s,%s,%s)
                                   ON CONFLICT(user_id) DO UPDATE SET reason=EXCLUDED.reason,ban_type=EXCLUDED.ban_type''',
                               (uid, reason, ban_type))
                    db.commit()
                elif action == 'unban':
                    cur.execute('DELETE FROM user_bans WHERE user_id=%s', (uid,))
                    db.commit()
            self.send_json({'ok':True})

        elif path.startswith('/api/album-meta/'):
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            album_id = urllib.parse.unquote(path[len('/api/album-meta/'):])
            body = self.read_body()
            with get_db() as db:
                cur = db.cursor()
                cur.execute('''INSERT INTO album_meta (id,type,year,extra_artists,cover_url)
                              VALUES (%s,%s,%s,%s,%s)
                              ON CONFLICT(id) DO UPDATE SET type=EXCLUDED.type,year=EXCLUDED.year,
                              extra_artists=EXCLUDED.extra_artists,cover_url=EXCLUDED.cover_url''',
                           (album_id, body.get('type','album'), body.get('year',''),
                            body.get('extra_artists',''), body.get('cover_url','')))
                db.commit()
            self.send_json({'ok':True})

        elif path == '/api/upload/cover':
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            ct = self.headers.get('Content-Type','')
            if 'multipart/form-data' not in ct:
                return self.send_json({'error':'multipart required'}, 400)
            fields, files = parse_multipart(self.rfile, self.headers)
            album_id = fields.get('album_id','')
            if not album_id: return self.send_json({'error':'album_id required'}, 400)
            parts = album_id.split('/', 1)
            if len(parts) == 2:
                cover_path = os.path.join(TRACKS_DIR, parts[0], parts[1], 'cover.jpg')
                fi = files.get('cover')
                if fi:
                    with open(cover_path, 'wb') as f: f.write(fi['data'])
                    url = f'/tracks/{urllib.parse.quote(parts[0])}/{urllib.parse.quote(parts[1])}/cover.jpg'
                    self.send_json({'ok':True,'url':url})
                    return
            self.send_json({'error':'failed'}, 400)

        else:
            self.send_response(404); self.end_headers()

    def do_DELETE(self):
        path = self.path.split('?')[0]
        if path.startswith('/api/artists/'):
            user = self.current_user()
            if not user or user['role'] != 'admin':
                return self.send_json({'error':'forbidden'}, 403)
            name = urllib.parse.unquote(path[len('/api/artists/'):])
            with get_db() as db:
                cur = db.cursor()
                cur.execute('DELETE FROM artists WHERE name=%s', (name,))
                db.commit()
            self.send_json({'ok':True})
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, fmt, *args):
        print(f'  {self.address_string()} {fmt%args}')

if __name__ == '__main__':
    init_db()
    port = 8080
    print(f'🎵 Tape  → http://localhost:{port}')
    print(f'   Admin → http://localhost:{port}/admin.html')
    print(f'   Ctrl+C to stop\n')
    http.server.test(H, port=port)
