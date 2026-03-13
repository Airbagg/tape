#!/usr/bin/env python3
"""
Tape — Telegram бот с оплатой через Telegram Stars
Запуск: python3 bot.py
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import time
import sqlite3
import os
import sys
import ssl
import smtplib
import secrets as secrets_mod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Отключаем проверку SSL (нужно на macOS)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ── Настройки ─────────────────────────────────────────────
BOT_TOKEN   = '8729241382:AAHelxuQXziTWAF0s6edOggzNuV3uI5k2Hg'
ADMIN_ID    = 464389692
DB_PATH     = os.path.join(os.path.dirname(__file__), 'tape.db')
APP_URL     = 'http://192.168.0.6:8080'

# Цены в Stars (1 Star ≈ 0.013$, ~1.3₽)
# 299₽ ≈ 230 Stars, 747₽ ≈ 575 Stars
GMAIL_USER = 'mmcannel@gmail.com'
GMAIL_PASS = 'fwyeccyurkvaxxnn'  # пароль приложения без пробелов

PLANS = [
    {'id': 'month_1',  'label': '1 месяц',   'days': 30,  'stars': 1,  'rub': 299},
    {'id': 'month_3',  'label': '3 месяца',  'days': 90,  'stars': 575,  'rub': 747},
    {'id': 'month_6',  'label': '6 месяцев', 'days': 180, 'stars': 1025, 'rub': 1344},
    {'id': 'month_12', 'label': '12 месяцев','days': 365, 'stars': 1840, 'rub': 2388},
]

# ── API ────────────────────────────────────────────────────
BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'

def api(method, data=None):
    url = f'{BASE}/{method}'
    if data:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={'Content-Type':'application/json'})
    else:
        req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        return json.loads(resp.read())
    except Exception as e:
        print(f'API error {method}:', e)
        return None

def send(chat_id, text, reply_markup=None, parse_mode='HTML'):
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        data['reply_markup'] = reply_markup
    return api('sendMessage', data)

def answer_cbq(cbq_id, text=''):
    api('answerCallbackQuery', {'callback_query_id': cbq_id, 'text': text})

def send_invoice(chat_id, plan):
    return api('sendInvoice', {
        'chat_id': chat_id,
        'title': f'Tape — {plan["label"]}',
        'description': f'Подписка на музыкальный сервис Tape на {plan["label"].lower()}',
        'payload': plan['id'],
        'currency': 'XTR',  # Telegram Stars
        'prices': [{'label': plan['label'], 'amount': plan['stars']}],
        'provider_token': '',  # пустой для Stars
    })

# ── БД ────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_tg(tg_id):
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE tg_id=?', (tg_id,)).fetchone()

def link_tg_to_email(tg_id, email):
    with get_db() as db:
        user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if not user:
            return None
        db.execute('UPDATE users SET tg_id=? WHERE email=?', (tg_id, email))
        db.commit()
        return dict(user)

def activate_sub(tg_id, days, stars, plan_id):
    now = int(time.time())
    with get_db() as db:
        user = db.execute('SELECT * FROM users WHERE tg_id=?', (tg_id,)).fetchone()
        if not user:
            return False
        base = max(user['sub_ends'] or now, now)
        sub_ends = base + 86400 * days
        db.execute('UPDATE users SET sub_active=1, sub_ends=? WHERE tg_id=?', (sub_ends, tg_id))
        try:
            db.execute(
                'INSERT INTO sub_grants (user_id, days, amount, source, note) VALUES (?,?,?,?,?)',
                (user['id'], days, round(stars * 1.3), 'payment', f'stars:{stars} plan:{plan_id}')
            )
        except Exception:
            pass
        db.commit()
        return sub_ends

# ── Состояния пользователей ────────────────────────────────
# {tg_id: {'state': 'awaiting_email'|'awaiting_code', 'email': ...}}
_states = {}

# ── Верификационные коды (синхронизация с server.py через БД) ──
def save_verify_code(email, code):
    """Сохраняем код в БД чтобы server.py мог его прочитать"""
    with get_db() as db:
        try:
            db.execute('CREATE TABLE IF NOT EXISTS tg_verify (email TEXT PRIMARY KEY, code TEXT, expires INTEGER, verified INTEGER DEFAULT 0)')
            db.execute('INSERT OR REPLACE INTO tg_verify (email, code, expires, verified) VALUES (?,?,?,0)',
                       (email, code, int(time.time()) + 600))
            db.commit()
        except Exception as e:
            print('save_verify_code error:', e)

def mark_verified(email):
    with get_db() as db:
        try:
            db.execute('UPDATE tg_verify SET verified=1 WHERE email=?', (email,))
            db.commit()
        except Exception as e:
            print('mark_verified error:', e)

# ── Клавиатуры ────────────────────────────────────────────
def kb_plans():
    buttons = []
    for p in PLANS:
        buttons.append([{'text': f'⭐ {p["label"]} — {p["stars"]} Stars (~{p["rub"]}₽)', 'callback_data': f'buy_{p["id"]}'}])
    buttons.append([{'text': '📱 Открыть Tape', 'url': APP_URL}])
    return {'inline_keyboard': buttons}

def kb_main(linked=False):
    buttons = [
        [{'text': '💳 Оформить подписку', 'callback_data': 'plans'}],
        [{'text': '📱 Открыть Tape', 'url': APP_URL}],
    ]
    if not linked:
        buttons.insert(0, [{'text': '🔗 Привязать аккаунт', 'callback_data': 'link'}])
    else:
        buttons.insert(0, [{'text': '👤 Мой аккаунт', 'callback_data': 'account'}])
    return {'inline_keyboard': buttons}

# ── Обработчики ───────────────────────────────────────────
def handle_start(msg):
    tg_id = msg['from']['id']
    name = msg['from'].get('first_name', 'друг')
    user = get_user_by_tg(tg_id)

    text = (
        f'🎵 <b>Привет, {name}!</b>\n\n'
        f'Добро пожаловать в <b>Tape</b> — музыка без цензуры.\n\n'
    )
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

def send_email(to, subject, html):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'Tape <{GMAIL_USER}>'
        msg['To'] = to
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, to, msg.as_string())
        return True
    except Exception as e:
        print('Email error:', e)
        return False

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

    text = (
        f'👤 <b>Аккаунт</b>\n\n'
        f'📧 {user["email"]}\n'
        f'💳 Подписка: {sub_text}\n'
    )
    send(tg_id, text, kb_main(linked=True))

def handle_plans(tg_id):
    send(tg_id, '💳 <b>Выбери план подписки:</b>\n\n⭐ Оплата через Telegram Stars', kb_plans())

def handle_buy(tg_id, plan_id):
    plan = next((p for p in PLANS if p['id'] == plan_id), None)
    if not plan:
        return
    user = get_user_by_tg(tg_id)
    if not user:
        send(tg_id, '❌ Сначала привяжи аккаунт Tape.', kb_main(linked=False))
        return
    send_invoice(tg_id, plan)

def handle_text(msg):
    tg_id = msg['from']['id']
    text = msg.get('text', '').strip()
    state = _states.get(tg_id, {})

    if state.get('state') == 'awaiting_email':
        email = text.lower().strip()
        if '@' not in email:
            send(tg_id, '❌ Введи корректный email')
            return
        # Проверяем что аккаунт существует
        with get_db() as db:
            user = db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if not user:
            send(tg_id, '❌ Аккаунт с таким email не найден.\n\nСначала зарегистрируйся в Tape.')
            _states.pop(tg_id, None)
            return
        # Генерируем код и шлём на email
        code = str(secrets_mod.randbelow(900000) + 100000)
        _states[tg_id] = {'state': 'awaiting_code', 'email': email, 'code': code, 'expires': int(time.time()) + 600}
        sent = send_email(email, 'Tape — код подтверждения',
            f'''<div style="font-family:sans-serif;max-width:400px;margin:0 auto">
            <h2 style="color:#c8a97e">🎵 Tape</h2>
            <p>Код для привязки Telegram аккаунта:</p>
            <h1 style="letter-spacing:8px;color:#c8a97e">{code}</h1>
            <p style="color:#888">Действует 10 минут. Если это не вы — игнорируйте письмо.</p>
            </div>''')
        if sent:
            send(tg_id, f'📬 Код отправлен на <b>{email}</b>\n\nВведи 6-значный код:')
        else:
            send(tg_id, '❌ Не удалось отправить письмо. Проверь email и попробуй снова.')
            _states.pop(tg_id, None)

    elif state.get('state') == 'awaiting_code':
        code = text.strip()
        email = state.get('email')
        if int(time.time()) > state.get('expires', 0):
            send(tg_id, '⏰ Код истёк. Попробуй привязать аккаунт заново.')
            _states.pop(tg_id, None)
            return
        if code != state.get('code'):
            send(tg_id, '❌ Неверный код. Попробуй ещё раз:')
            return
        # Код верный — привязываем
        user = link_tg_to_email(tg_id, email)
        _states.pop(tg_id, None)
        send(tg_id, f'✅ Аккаунт <b>{email}</b> привязан!', kb_main(linked=True))
        api('sendMessage', {
            'chat_id': ADMIN_ID,
            'text': f'🔗 Новая привязка TG\n{email} → tg_id:{tg_id}'
        })

    else:
        handle_start(msg)

def handle_pre_checkout(query):
    """Telegram требует ответить в течение 10 сек"""
    api('answerPreCheckoutQuery', {
        'pre_checkout_query_id': query['id'],
        'ok': True
    })

def handle_successful_payment(msg):
    tg_id = msg['from']['id']
    payment = msg['successful_payment']
    plan_id = payment['invoice_payload']
    stars = payment['total_amount']

    plan = next((p for p in PLANS if p['id'] == plan_id), None)
    if not plan:
        return

    sub_ends = activate_sub(tg_id, plan['days'], stars, plan_id)
    if sub_ends:
        from datetime import datetime
        date_str = datetime.fromtimestamp(sub_ends).strftime('%d.%m.%Y')
        send(tg_id,
            f'🎉 <b>Подписка оформлена!</b>\n\n'
            f'📅 План: {plan["label"]}\n'
            f'⭐ Оплачено: {stars} Stars\n'
            f'📆 Действует до: {date_str}\n\n'
            f'Открывай Tape и слушай!',
            {'inline_keyboard': [[{'text': '📱 Открыть Tape', 'url': APP_URL}]]}
        )
        # Уведомляем админа
        user = get_user_by_tg(tg_id)
        api('sendMessage', {
            'chat_id': ADMIN_ID,
            'text': f'💰 Новая оплата!\n'
                    f'👤 {user["email"] if user else tg_id}\n'
                    f'📅 {plan["label"]}\n'
                    f'⭐ {stars} Stars (~{round(stars*1.3)}₽)'
        })
    else:
        send(tg_id, '⚠️ Оплата прошла, но аккаунт не найден. Напиши @mmcannel')

# ── Polling ───────────────────────────────────────────────
def run():
    # Добавляем колонку tg_id в users если нет
    with get_db() as db:
        try:
            db.execute('ALTER TABLE users ADD COLUMN tg_id INTEGER')
            db.commit()
        except Exception:
            pass
        try:
            db.execute('CREATE TABLE IF NOT EXISTS tg_verify (email TEXT PRIMARY KEY, code TEXT, expires INTEGER, verified INTEGER DEFAULT 0)')
            db.commit()
        except Exception:
            pass

    print('🤖 Tape bot запущен...')
    me = api('getMe')
    if me:
        print(f'   Бот: @{me["result"]["username"]}')

    offset = 0
    while True:
        try:
            result = api('getUpdates', {'offset': offset, 'timeout': 30, 'allowed_updates': ['message', 'callback_query', 'pre_checkout_query']})
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
            if 'timed out' in str(e) or 'The read operation timed out' in str(e):
                continue  # нормальный таймаут long polling
            print('Poll error:', e)
            time.sleep(5)

def process(upd):
    # Pre-checkout
    if 'pre_checkout_query' in upd:
        handle_pre_checkout(upd['pre_checkout_query'])
        return

    # Callback query
    if 'callback_query' in upd:
        cbq = upd['callback_query']
        tg_id = cbq['from']['id']
        data = cbq.get('data', '')
        answer_cbq(cbq['id'])

        if data == 'plans':
            handle_plans(tg_id)
        elif data == 'link':
            handle_link(tg_id)
        elif data == 'account':
            handle_account(tg_id)
        elif data.startswith('buy_'):
            handle_buy(tg_id, data[4:])
        return

    # Message
    if 'message' not in upd:
        return

    msg = upd['message']
    tg_id = msg['from']['id']

    # Успешная оплата
    if 'successful_payment' in msg:
        handle_successful_payment(msg)
        return

    text = msg.get('text', '')

    if text.startswith('/start'):
        handle_start(msg)
    elif text.startswith('/sub') or text.startswith('/plans'):
        handle_plans(tg_id)
    elif text.startswith('/account'):
        handle_account(tg_id)
    else:
        handle_text(msg)

if __name__ == '__main__':
    run()
