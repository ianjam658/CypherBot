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
