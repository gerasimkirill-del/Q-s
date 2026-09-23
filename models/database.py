"""
База данных бота Q Holsters
"""
import json
import sqlite3
from typing import List, Optional


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            from config import DATABASE_PATH
            db_path = DATABASE_PATH
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _exec(self, sql: str, params: tuple = ()) -> int:
        """INSERT/UPDATE/DELETE. Возвращает rowcount (или lastrowid для INSERT)."""
        conn = self.get_connection()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid if sql.lstrip().upper().startswith("INSERT") else cur.rowcount
        finally:
            conn.close()

    def _all(self, sql: str, params: tuple = ()) -> list:
        conn = self.get_connection()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _one(self, sql: str, params: tuple = ()):
        conn = self.get_connection()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def init_db(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY,
                    admin_id INTEGER UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    user_username TEXT,
                    pistol_model TEXT NOT NULL,
                    holster_type TEXT NOT NULL,
                    flashlight TEXT NOT NULL,
                    color TEXT NOT NULL,
                    city TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # миграция старой БД: статус анкеты
            cols = [r[1] for r in cursor.execute("PRAGMA table_info(orders)")]
            if "status" not in cols:
                cursor.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'new'")
            if "admin_text" not in cols:
                cursor.execute("ALTER TABLE orders ADD COLUMN admin_text TEXT")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spam_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS question_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # сообщения с анкетой у каждого админа (чтобы менять статус-эмодзи везде)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_messages (
                    order_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    PRIMARY KEY (order_id, chat_id, message_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pistols (
                    brand TEXT PRIMARY KEY,
                    models TEXT NOT NULL,
                    has_flashlight INTEGER NOT NULL DEFAULT 1,
                    sort INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.commit()

            # первичное заполнение каталога из config.py
            if cursor.execute("SELECT COUNT(*) FROM pistols").fetchone()[0] == 0:
                from config import PISTOL_BRANDS, NO_FLASHLIGHT_BRANDS
                for i, (brand, models) in enumerate(PISTOL_BRANDS.items()):
                    cursor.execute(
                        "INSERT INTO pistols (brand, models, has_flashlight, sort) VALUES (?, ?, ?, ?)",
                        (brand, json.dumps(models, ensure_ascii=False),
                         0 if brand in NO_FLASHLIGHT_BRANDS else 1, i),
                    )
                conn.commit()
        finally:
            conn.close()

    # ===== АДМИНИСТРАТОРЫ =====
    def add_admin(self, admin_id: int) -> bool:
        try:
            self._exec("INSERT INTO admins (admin_id) VALUES (?)", (admin_id,))
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_admin(self, admin_id: int) -> bool:
        return self._exec("DELETE FROM admins WHERE admin_id = ?", (admin_id,)) > 0

    def get_all_admins(self) -> List[int]:
        return [row[0] for row in self._all("SELECT admin_id FROM admins")]

    def is_admin(self, admin_id: int) -> bool:
        return self._one("SELECT 1 FROM admins WHERE admin_id = ?", (admin_id,)) is not None

    # ===== ЗАКАЗЫ =====
    def save_order(self, user_id: int, user_name: str, user_username: Optional[str],
                   pistol_model: str, holster_type: str, flashlight: str,
                   color: str, city: str, customer_name: str) -> int:
        return self._exec("""
            INSERT INTO orders
            (user_id, user_name, user_username, pistol_model, holster_type, flashlight, color, city, customer_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, user_name, user_username, pistol_model, holster_type, flashlight, color, city, customer_name))

    def get_order(self, order_id: int) -> Optional[dict]:
        row = self._one("SELECT * FROM orders WHERE id = ?", (order_id,))
        return dict(row) if row else None

    def set_order_admin_text(self, order_id: int, text: str):
        self._exec("UPDATE orders SET admin_text = ? WHERE id = ?", (text, order_id))

    def set_order_status(self, order_id: int, status: str) -> bool:
        return self._exec("UPDATE orders SET status = ? WHERE id = ?", (status, order_id)) > 0

    def get_active_orders(self) -> List[dict]:
        """Анкеты, которые ещё не закрыты (новые и в работе)."""
        rows = self._all(
            "SELECT * FROM orders WHERE COALESCE(status, 'new') IN ('new', 'work') ORDER BY id DESC"
        )
        return [dict(r) for r in rows]

    def save_order_message(self, order_id: int, chat_id: int, message_id: int):
        self._exec("INSERT OR IGNORE INTO order_messages (order_id, chat_id, message_id) VALUES (?, ?, ?)",
                   (order_id, chat_id, message_id))

    def get_order_messages(self, order_id: int) -> List[dict]:
        return [dict(r) for r in self._all(
            "SELECT chat_id, message_id FROM order_messages WHERE order_id = ?", (order_id,))]

    # ===== БАН =====
    def ban_user(self, user_id: int, user_name: str = "") -> bool:
        try:
            self._exec("INSERT OR REPLACE INTO banned_users (user_id, user_name) VALUES (?, ?)",
                       (user_id, user_name))
            return True
        except Exception:
            return False

    def unban_user(self, user_id: int) -> bool:
        return self._exec("DELETE FROM banned_users WHERE user_id = ?", (user_id,)) > 0

    def is_banned(self, user_id: int) -> bool:
        return self._one("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,)) is not None

    def get_banned_users(self) -> List[dict]:
        rows = self._all("SELECT user_id, user_name, banned_at FROM banned_users ORDER BY banned_at DESC")
        return [{"user_id": r["user_id"], "user_name": r["user_name"], "banned_at": r["banned_at"]}
                for r in rows]

    # ===== АНТИСПАМ =====
    # created_at пишется в UTC (CURRENT_TIMESTAMP), поэтому и сравниваем с UTC.
    def log_form(self, user_id: int):
        self._exec("INSERT INTO spam_log (user_id) VALUES (?)", (user_id,))

    def get_form_count(self, user_id: int, window_seconds: int) -> int:
        return self._one("""
            SELECT COUNT(*) FROM spam_log
            WHERE user_id = ? AND created_at >= datetime('now', ?)
        """, (user_id, f"-{int(window_seconds)} seconds"))[0]

    def log_question(self, user_id: int):
        self._exec("INSERT INTO question_log (user_id) VALUES (?)", (user_id,))

    def get_question_count(self, user_id: int, window_seconds: int) -> int:
        return self._one("""
            SELECT COUNT(*) FROM question_log
            WHERE user_id = ? AND created_at >= datetime('now', ?)
        """, (user_id, f"-{int(window_seconds)} seconds"))[0]

    # ===== НАСТРОЙКИ =====
    def get_setting(self, key: str, default: int) -> int:
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        return int(row[0]) if row else default

    def set_setting(self, key: str, value: int):
        self._exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

    # ===== КАТАЛОГ ПИСТОЛЕТОВ =====
    def get_pistols(self) -> List[dict]:
        rows = self._all("SELECT brand, models, has_flashlight FROM pistols ORDER BY sort, rowid")
        return [{"brand": r["brand"], "models": json.loads(r["models"]),
                 "has_flashlight": bool(r["has_flashlight"])} for r in rows]

    def get_pistol(self, brand: str) -> Optional[dict]:
        r = self._one("SELECT brand, models, has_flashlight FROM pistols WHERE brand = ?", (brand,))
        if not r:
            return None
        return {"brand": r["brand"], "models": json.loads(r["models"]),
                "has_flashlight": bool(r["has_flashlight"])}

    def save_pistol(self, brand: str, models: List[str], has_flashlight: bool, old_brand: str = None):
        """Добавить новую марку или обновить существующую (old_brand — при переименовании)."""
        payload = json.dumps(models, ensure_ascii=False)
        if old_brand and self.get_pistol(old_brand):
            self._exec("UPDATE pistols SET brand = ?, models = ?, has_flashlight = ? WHERE brand = ?",
                       (brand, payload, int(has_flashlight), old_brand))
        else:
            sort = self._one("SELECT COALESCE(MAX(sort), 0) + 1 FROM pistols")[0]
            self._exec("INSERT OR REPLACE INTO pistols (brand, models, has_flashlight, sort) VALUES (?, ?, ?, ?)",
                       (brand, payload, int(has_flashlight), sort))

    def delete_pistol(self, brand: str) -> bool:
        return self._exec("DELETE FROM pistols WHERE brand = ?", (brand,)) > 0
