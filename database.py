import sqlite3
import time
from contextlib import closing


DB_FILE = "cypherbot.db"


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    with closing(connect()) as db:

        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            plan TEXT DEFAULT 'FREE',
            pro_until INTEGER DEFAULT 0,
            requests_today INTEGER DEFAULT 0,
            request_date TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            joined_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            rules TEXT DEFAULT '',
            welcome_enabled INTEGER DEFAULT 1,
            anti_link INTEGER DEFAULT 0,
            anti_spam INTEGER DEFAULT 1,
            auto_reaction INTEGER DEFAULT 0,
            reaction TEXT DEFAULT '👍'
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            message TEXT,
            remind_at INTEGER,
            sent INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            payload TEXT,
            amount INTEGER,
            currency TEXT,
            charge_id TEXT,
            created_at INTEGER
        );
        """)

        db.commit()


def ensure_user(user):

    now = int(time.time())

    with closing(connect()) as db:

        db.execute("""
        INSERT INTO users
        (user_id, username, first_name, joined_at, request_date)
        VALUES (?, ?, ?, ?, date('now'))
        ON CONFLICT(user_id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name
        """, (
            user.id,
            user.username,
            user.first_name,
            now
        ))

        db.commit()


def get_user(user_id):

    with closing(connect()) as db:

        row = db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        return row


def is_pro(user_id):

    user = get_user(user_id)

    if not user:
        return False

    return (
        user["plan"] == "PRO"
        and user["pro_until"] > int(time.time())
    )


def activate_pro(user_id, until):

    with closing(connect()) as db:

        db.execute("""
        UPDATE users
        SET plan='PRO', pro_until=?
        WHERE user_id=?
        """, (until, user_id))

        db.commit()


def get_usage(user_id):

    user = get_user(user_id)

    if not user:
        return 0

    today = time.strftime("%Y-%m-%d")

    if user["request_date"] != today:

        with closing(connect()) as db:

            db.execute("""
            UPDATE users
            SET requests_today=0,
                request_date=?
            WHERE user_id=?
            """, (today, user_id))

            db.commit()

        return 0

    return user["requests_today"]


def consume_request(user_id):

    today = time.strftime("%Y-%m-%d")

    with closing(connect()) as db:

        row = db.execute(
            "SELECT request_date, requests_today FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if not row:
            return 0

        if row["request_date"] != today:

            db.execute("""
            UPDATE users
            SET requests_today=1,
                request_date=?
            WHERE user_id=?
            """, (today, user_id))

            db.commit()
            return 1

        new_value = row["requests_today"] + 1

        db.execute("""
        UPDATE users
        SET requests_today=?
        WHERE user_id=?
        """, (new_value, user_id))

        db.commit()

        return new_value


def save_message(user_id, chat_id, role, content):

    with closing(connect()) as db:

        db.execute("""
        INSERT INTO messages
        (user_id, chat_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            chat_id,
            role,
            content,
            int(time.time())
        ))

        db.commit()


def get_history(user_id, chat_id, limit=10):

    with closing(connect()) as db:

        rows = db.execute("""
        SELECT role, content
        FROM messages
        WHERE user_id=? AND chat_id=?
        ORDER BY id DESC
        LIMIT ?
        """, (
            user_id,
            chat_id,
            limit
        )).fetchall()

        rows = list(reversed(rows))

        return [
            {
                "role": row["role"],
                "content": row["content"]
            }
            for row in rows
        ]


def save_group(chat_id, title):

    with closing(connect()) as db:

        db.execute("""
        INSERT INTO groups(chat_id, title)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
        title=excluded.title
        """, (chat_id, title))

        db.commit()


def get_group(chat_id):

    with closing(connect()) as db:

        return db.execute(
            "SELECT * FROM groups WHERE chat_id=?",
            (chat_id,)
        ).fetchone()


def set_rules(chat_id, rules):

    with closing(connect()) as db:

        db.execute("""
        UPDATE groups
        SET rules=?
        WHERE chat_id=?
        """, (rules, chat_id))

        db.commit()


def add_warning(chat_id, user_id, reason):

    with closing(connect()) as db:

        db.execute("""
        INSERT INTO warnings
        (chat_id, user_id, reason, created_at)
        VALUES (?, ?, ?, ?)
        """, (
            chat_id,
            user_id,
            reason,
            int(time.time())
        ))

        db.commit()

        row = db.execute("""
        SELECT COUNT(*) AS count
        FROM warnings
        WHERE chat_id=? AND user_id=?
        """, (
            chat_id,
            user_id
        )).fetchone()

        return row["count"]


def warning_count(chat_id, user_id):

    with closing(connect()) as db:

        row = db.execute("""
        SELECT COUNT(*) AS count
        FROM warnings
        WHERE chat_id=? AND user_id=?
        """, (
            chat_id,
            user_id
        )).fetchone()

        return row["count"]


def add_xp(user_id, amount=1):

    with closing(connect()) as db:

        row = db.execute(
            "SELECT xp, level FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if not row:
            return 1

        xp = row["xp"] + amount
        level = max(1, (xp // 100) + 1)

        db.execute("""
        UPDATE users
        SET xp=?, level=?
        WHERE user_id=?
        """, (
            xp,
            level,
            user_id
        ))

        db.commit()

        return level


def add_reminder(user_id, chat_id, message, remind_at):

    with closing(connect()) as db:

        db.execute("""
        INSERT INTO reminders
        (user_id, chat_id, message, remind_at)
        VALUES (?, ?, ?, ?)
        """, (
            user_id,
            chat_id,
            message,
            remind_at
        ))

        db.commit()


def get_due_reminders():

    with closing(connect()) as db:

        rows = db.execute("""
        SELECT *
        FROM reminders
        WHERE sent=0 AND remind_at<=?
        """, (int(time.time()),)).fetchall()

        return rows


def mark_reminder_sent(reminder_id):

    with closing(connect()) as db:

        db.execute("""
        UPDATE reminders
        SET sent=1
        WHERE id=?
        """, (reminder_id,))

        db.commit()


def save_payment(
    user_id,
    payload,
    amount,
    currency,
    charge_id
):

    with closing(connect()) as db:

        db.execute("""
        INSERT INTO payments
        (user_id, payload, amount, currency, charge_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            payload,
            amount,
            currency,
            charge_id,
            int(time.time())
        ))

        db.commit()
import sqlite3
from datetime import date


DATABASE = "cypherbot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def init_db():
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            plan TEXT DEFAULT 'FREE',
            requests_today INTEGER DEFAULT 0,
            last_request_date TEXT
        )
        """
    )

    connection.commit()
    connection.close()


def ensure_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT telegram_id FROM users WHERE telegram_id = ?",
        (user_id,)
    )

    user = cursor.fetchone()

    if not user:
        cursor.execute(
            """
            INSERT INTO users (
                telegram_id,
                plan,
                requests_today,
                last_request_date
            )
            VALUES (?, 'FREE', 0, ?)
            """,
            (user_id, str(date.today()))
        )

    connection.commit()
    connection.close()


def get_usage(user_id):
    ensure_user(user_id)

    connection = get_connection()
    cursor = connection.cursor()

    today = str(date.today())

    cursor.execute(
        """
        SELECT requests_today, last_request_date
        FROM users
        WHERE telegram_id = ?
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    if not result:
        connection.close()
        return 0

    requests_today, last_request_date = result

    if last_request_date != today:
        cursor.execute(
            """
            UPDATE users
            SET requests_today = 0,
                last_request_date = ?
            WHERE telegram_id = ?
            """,
            (today, user_id)
        )

        connection.commit()

        connection.close()

        return 0

    connection.close()

    return requests_today


def increment_usage(user_id):
    ensure_user(user_id)

    connection = get_connection()
    cursor = connection.cursor()

    today = str(date.today())

    cursor.execute(
        """
        UPDATE users
        SET requests_today = requests_today + 1,
            last_request_date = ?
        WHERE telegram_id = ?
        """,
        (today, user_id)
    )

    connection.commit()
    connection.close()
