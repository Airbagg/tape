#!/usr/bin/env python3
"""
Tape — Telegram бот с оплатой через Telegram Stars
Использует PostgreSQL (та же база что и server.py)
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import time
import os
import ssl
import secrets as secrets_mod
import psycopg2
import psycopg2.extras

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ── Настройки ─────────────────────────────────────────────
BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '8729241382:AAHelxuQXziTWAF0s6edOggzNuV3uI5k2Hg')
ADMIN_ID  = int(os.environ.get('TG_ADMIN_CHAT', '464389692'))
APP_URL   = os.environ.get('APP_URL', 'https://tape.up.railway.app')

PLANS = [
    {'id': 'month_1',  'label': '1 месяц',    'days': 30,  'stars': 1,    'rub': 299},
    {'id': 'month_3',  'label': '3 месяца',   'days': 90,  'stars': 575,  'rub': 747},
    {'id': 'month_6',  'label': '6 месяцев',  'days': 180, 'stars': 1025, 'rub': 1344},
    {'id': 'month_12', 'label': '12 месяцев', 'days': 365, 'stars': 1840, 'rub': 2388},
]

# ── БД (PostgreSQL — та же что у server.py) ───────────────
def get_db():
    conn = psycopg2.connect(
        os.environ.get('DATABASE_URL'),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    conn.autocommit = False
    return conn

def init_db():
    with get_db() as db:
        cur = db.cursor()
        try:
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS tg_id BIGINT')
            db.commit()
        except Exception as e:
            db.rollback()
            print('init_db:', e)

def get_user_by_tg(tg_id):
    with get_db() as db:
        cur = db.cursor()
        cur.execute('SELECT * FROM users WHERE tg_id=%s', (tg_id,))
        row = cur.fetchone()
    return dict(row) if row else None

def get_user_by_email(email):
    with get_db() as db:
        cur = db.cursor()
        cur.execute('SELECT id, email, sub_active, sub_ends FROM users WHERE email=%s', (email,))
        row = cur.fetchone()
    return dict(row) if row else None

def link_tg_to_user(tg_id, email):
    with get_db() as db:
        cur = db.cursor()
        cur.execute('UPDATE users SET tg_id=%s WHERE email=%s', (tg_id, email))
        db.commit()
        return cur.rowcount > 0

def activate_sub(tg_id, days, stars, plan_id):
    now = int(time.time())
    with get_db() as db:
        cur = db.cursor()
        cur.execute('SELECT id, sub_ends FROM users WHERE tg_id=%s', (tg_id,))
        user = cur.fetchone()
        if not user:
            return None
        base = max(user['sub_ends'] or now, now)
        sub_ends = base + 86400 * days
        cur.execute('UPDATE users SET sub_active=1, sub_ends=%s WHERE tg_id=%s', (sub_ends, tg_id))
        try:
            cur.execute(
                'INSERT INTO sub_grants (user_id, days, amount, source, note) VALUES (%s,%s,%s,%s,%s)',
                (user['id'], days, round(stars * 1.3), 'payment', f'stars:{stars} plan:{plan_id}')
            )
        except Exception:
            pass
        db.commit()
    return sub_ends

# ── Telegram API ──────────────────────────────────────────
BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'

def api(method, data=None):
    url = f'{BASE}/{method}'
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url, data=body,
        headers={'Content-Type': 'application/json'} if body else {}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        return json.loads(resp.read())
    except Exception as e:
        print(f'API error {method}:', e)
        return None

def send(chat_id, text, reply_markup=None):
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        data['reply_markup'] = reply_markup
    return api('sendMessage', data)

def answer_cbq(cbq_id, text=''):
    api('answerCallbackQuery', {'callback_query_id': cbq_id, 'text': text})

def send_invoice(chat_id, plan):
    return api('sendInvoice', {
        'chat_id': chat_id,
        'title': f'Tape — {plan["label"]}',
        'description': f'Подписка на Tape на {plan["label"].lower()}',
        'payload': plan['id'],
        'currency': 'XTR',
        'prices': [{'label': plan['label'], 'amount': plan['stars']}],
        'provider_token': '',
    })

# ── Клавиатуры ────────────────────────────────────────────
def kb_main(linked=False):
    buttons = [
        [{'text': '💳 Оформить подписку', 'callback_data': 'plans'}],
        [{'text': '📱 Открыть Tape', 'url': APP_URL}],
    ]
    if linked:
        buttons.insert(0, [{'text': '👤 Мой аккаунт', 'callback_data': 'account'}])
    else:
        buttons.insert(0, [{'text': '🔗 Привязать аккаунт', 'callback_data': 'link'}])
    return {'inline_keyboard': buttons}

def kb_plans():
    buttons = [
        [{'text': f'⭐ {p["label"]} — {p["stars"]} Stars (~{p["rub"]}₽)', 'callback_data': f'buy_{p["id"]}'}]
        for p in PLANS
    ]
    buttons.append([{'text': '📱 Открыть Tape', 'url': APP_URL}])
    return {'inline_keyboard': buttons}

# ── Состояния ─────────────────────────────────────────────
_states = {}

# ── Обработчики ───────────────────────────────────────────
def handle_start(msg):
    tg_id = msg['from']['id']
    name  = msg['from'].get('first_name', 'друг')
    user  = get_user_by_tg(tg_id)
    text  = f'🎵 <b>Привет, {name}!</b>\n\nДобро пожаловать в <b>Tape</b> — музыка без цензуры.\n\n'
    if user:
        now = int(time.time())
        sub_ok = user['sub_active'] and (not user['sub_ends'] or user['sub_ends'] > now)
        if sub_ok:
            days_left = max(0, (user['sub_ends'] - now) // 86400) if user['sub_ends'] else '∞'
            text += f'✅ Подписка активна, осталось <b>{days_left} дн.</b>'
        else:
            text += '⏳ Подписка не активна. Оформи ниже!'
        send(tg_id, text, kb_main(linked=True))
    else:
        text += 'Привяжи свой аккаунт Tape чтобы управлять подпиской.'
        send(tg_id, text, kb_main(linked=False))

def handle_link(tg_id):
    _states[tg_id] = {'state': 'awaiting_email'}
    send(tg_id, '📧 Введи email от своего аккаунта Tape:')

def handle_account(tg_id):
    user = get_user_by_tg(tg_id)
    if not user:
        send(tg_id, '❌ Аккаунт не привязан.', kb_main(linked=False))
        return
    now = int(time.time())
    sub_ok = user['sub_active'] and (not user['sub_ends'] or user['sub_ends'] > now)
    if sub_ok and user['sub_ends']:
        days = max(0, (user['sub_ends'] - now) // 86400)
        sub_text = f'✅ Активна, {days} дн. осталось'
    elif sub_ok:
        sub_text = '✅ Активна (бессрочно)'
    else:
        sub_text = '❌ Не активна'
    send(tg_id, f'👤 <b>Аккаунт</b>\n\n📧 {user["email"]}\n💳 Подписка: {sub_text}', kb_main(linked=True))

def handle_plans(tg_id):
    send(tg_id, '💳 <b>Выбери план подписки:</b>\n\n⭐ Оплата через Telegram Stars', kb_plans())

def handle_buy(tg_id, plan_id):
    plan = next((p for p in PLANS if p['id'] == plan_id), None)
    if not plan:
        return
    if not get_user_by_tg(tg_id):
        send(tg_id, '❌ Сначала привяжи аккаунт Tape.', kb_main(linked=False))
        return
    send_invoice(tg_id, plan)

def handle_text(msg):
    tg_id = msg['from']['id']
    text  = msg.get('text', '').strip()
    state = _states.get(tg_id, {})

    if state.get('state') == 'awaiting_email':
        email = text.lower().strip()
        if '@' not in email:
            send(tg_id, '❌ Введи корректный email')
            return
        if not get_user_by_email(email):
            send(tg_id, '❌ Аккаунт с таким email не найден.\n\nСначала зарегистрируйся в Tape.')
            _states.pop(tg_id, None)
            return
        code = str(secrets_mod.randbelow(900000) + 100000)
        _states[tg_id] = {'state': 'awaiting_code', 'email': email, 'code': code, 'expires': int(time.time()) + 600}
        send(tg_id,
            f'📬 Код подтверждения для <b>{email}</b>:\n\n'
            f'<code>{code}</code>\n\n'
            f'Введи этот код здесь. Действует 10 минут.'
        )

    elif state.get('state') == 'awaiting_code':
        if int(time.time()) > state.get('expires', 0):
            send(tg_id, '⏰ Код истёк. Попробуй привязать аккаунт заново.')
            _states.pop(tg_id, None)
            return
        if text.strip() != state.get('code'):
            send(tg_id, '❌ Неверный код. Попробуй ещё раз:')
            return
        ok = link_tg_to_user(tg_id, state['email'])
        _states.pop(tg_id, None)
        if ok:
            send(tg_id, f'✅ Аккаунт <b>{state["email"]}</b> привязан!\n\nТеперь можешь оформить подписку.', kb_main(linked=True))
            api('sendMessage', {'chat_id': ADMIN_ID, 'text': f'🔗 Привязка TG\n{state["email"]} → tg:{tg_id}'})
        else:
            send(tg_id, '❌ Ошибка привязки. Напиши @mmcannel')
    else:
        handle_start(msg)

def handle_pre_checkout(query):
    api('answerPreCheckoutQuery', {'pre_checkout_query_id': query['id'], 'ok': True})

def handle_successful_payment(msg):
    tg_id   = msg['from']['id']
    payment = msg['successful_payment']
    plan_id = payment['invoice_payload']
    stars   = payment['total_amount']
    plan    = next((p for p in PLANS if p['id'] == plan_id), None)
    if not plan:
        return
    sub_ends = activate_sub(tg_id, plan['days'], stars, plan_id)
    if sub_ends:
        from datetime import datetime
        date_str = datetime.fromtimestamp(sub_ends).strftime('%d.%m.%Y')
        send(tg_id,
            f'🎉 <b>Подписка оформлена!</b>\n\n'
            f'📅 {plan["label"]}\n⭐ {stars} Stars\n📆 До: {date_str}\n\nОткрывай Tape!',
            {'inline_keyboard': [[{'text': '📱 Открыть Tape', 'url': APP_URL}]]}
        )
        user = get_user_by_tg(tg_id)
        api('sendMessage', {'chat_id': ADMIN_ID,
            'text': f'💰 Оплата!\n👤 {user["email"] if user else tg_id}\n📅 {plan["label"]}\n⭐ {stars} Stars (~{round(stars*1.3)}₽)'})
    else:
        send(tg_id, '⚠️ Оплата прошла, но аккаунт не найден. Напиши @mmcannel')

# ── Polling ───────────────────────────────────────────────
def process(upd):
    if 'pre_checkout_query' in upd:
        handle_pre_checkout(upd['pre_checkout_query'])
        return
    if 'callback_query' in upd:
        cbq   = upd['callback_query']
        tg_id = cbq['from']['id']
        data  = cbq.get('data', '')
        answer_cbq(cbq['id'])
        if data == 'plans':           handle_plans(tg_id)
        elif data == 'link':          handle_link(tg_id)
        elif data == 'account':       handle_account(tg_id)
        elif data.startswith('buy_'): handle_buy(tg_id, data[4:])
        return
    if 'message' not in upd:
        return
    msg   = upd['message']
    tg_id = msg['from']['id']
    if 'successful_payment' in msg:
        handle_successful_payment(msg)
        return
    text = msg.get('text', '')
    if text.startswith('/start'):                        handle_start(msg)
    elif text.startswith('/sub') or text.startswith('/plans'): handle_plans(tg_id)
    elif text.startswith('/account'):                    handle_account(tg_id)
    else:                                                handle_text(msg)

def run():
    init_db()
    print('🤖 Tape bot запущен (PostgreSQL)...')
    me = api('getMe')
    if me and me.get('ok'):
        print(f'   Бот: @{me["result"]["username"]}')
    offset = 0
    while True:
        try:
            result = api('getUpdates', {'offset': offset, 'timeout': 30,
                'allowed_updates': ['message', 'callback_query', 'pre_checkout_query']})
            if not result or not result.get('ok'):
                time.sleep(3)
                continue
            for upd in result.get('result', []):
                offset = upd['update_id'] + 1
                try:
                    process(upd)
                except Exception as e:
                    print('Update error:', e)
        except KeyboardInterrupt:
            print('Бот остановлен')
            break
        except urllib.error.URLError as e:
            if 'timed out' in str(e) or 'read operation timed out' in str(e):
                continue
            print('Poll error:', e)
            time.sleep(5)

if __name__ == '__main__':
    run()
