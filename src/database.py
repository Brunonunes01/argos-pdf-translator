from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import BilingualChunk, Book, TextChunk


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    total_pages INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    original_text TEXT NOT NULL,
                    original_hash TEXT NOT NULL,
                    translated_text TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(book_id, page_number, block_index, original_hash),
                    FOREIGN KEY(book_id) REFERENCES books(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS book_pages (
                    book_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(book_id, page_number),
                    FOREIGN KEY(book_id) REFERENCES books(id)
                )
                """
            )
            self._migrate_chunks_table(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_book_page ON chunks(book_id, page_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_original_hash ON chunks(book_id, original_hash)"
            )
            self._backfill_book_pages(conn)

    def _migrate_chunks_table(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(chunks)").fetchall()
        }
        if "original_hash" not in columns:
            conn.execute("ALTER TABLE chunks ADD COLUMN original_hash TEXT")
        rows = conn.execute(
            "SELECT id, original_text FROM chunks WHERE original_hash IS NULL OR original_hash = ''"
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE chunks SET original_hash = ? WHERE id = ?",
                (self._hash_text(row["original_text"]), row["id"]),
            )

    def _backfill_book_pages(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT book_id, page_number, COUNT(*) AS total_chunks
            FROM chunks
            GROUP BY book_id, page_number
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO book_pages (book_id, page_number, status, total_chunks)
                VALUES (?, ?, 'extracted', ?)
                """,
                (row["book_id"], row["page_number"], int(row["total_chunks"] or 0)),
            )

    def upsert_book(self, book_id: str, filename: str, file_hash: str, total_pages: int) -> Book:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO books (id, filename, file_hash, total_pages)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    filename = excluded.filename,
                    total_pages = excluded.total_pages
                """,
                (book_id, filename, file_hash, total_pages),
            )
            row = conn.execute("SELECT * FROM books WHERE file_hash = ?", (file_hash,)).fetchone()
        return Book(**dict(row))

    def get_book_by_hash(self, file_hash: str) -> Book | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM books WHERE file_hash = ?", (file_hash,)).fetchone()
        return Book(**dict(row)) if row else None

    def insert_chunks_if_missing(self, chunks: Iterable[TextChunk]) -> int:
        inserted = 0
        with self.connect() as conn:
            for chunk in chunks:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO chunks
                        (book_id, page_number, block_index, original_text, original_hash, status)
                    VALUES (?, ?, ?, ?, ?, 'extracted')
                    """,
                    (
                        chunk.book_id,
                        chunk.page_number,
                        chunk.block_index,
                        chunk.original_text,
                        chunk.original_hash,
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def mark_page_status(self, book_id: str, page_number: int, status: str, total_chunks: int = 0) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO book_pages (book_id, page_number, status, total_chunks)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(book_id, page_number) DO UPDATE SET
                    status = excluded.status,
                    total_chunks = excluded.total_chunks,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (book_id, page_number, status, total_chunks),
            )

    def get_pending_chunks(self, book_id: str, start_page: int, end_page: int) -> list[BilingualChunk]:
        return self._get_chunks(
            """
            SELECT * FROM chunks
            WHERE book_id = ? AND page_number BETWEEN ? AND ?
              AND status IN ('extracted')
            ORDER BY page_number, block_index, id
            """,
            (book_id, start_page, end_page),
        )

    def get_chunks(self, book_id: str, start_page: int | None = None, end_page: int | None = None) -> list[BilingualChunk]:
        if start_page is None or end_page is None:
            return self._get_chunks(
                "SELECT * FROM chunks WHERE book_id = ? ORDER BY page_number, block_index, id",
                (book_id,),
            )
        return self._get_chunks(
            """
            SELECT * FROM chunks
            WHERE book_id = ? AND page_number BETWEEN ? AND ?
            ORDER BY page_number, block_index, id
            """,
            (book_id, start_page, end_page),
        )

    def _get_chunks(self, query: str, params: tuple[object, ...]) -> list[BilingualChunk]:
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            BilingualChunk(
                id=row["id"],
                book_id=row["book_id"],
                page_number=row["page_number"],
                block_index=row["block_index"],
                original_text=row["original_text"],
                original_hash=row["original_hash"],
                translated_text=row["translated_text"],
                status=row["status"],
            )
            for row in rows
        ]

    def _hash_text(self, text: str) -> str:
        normalized = " ".join(text.split()).casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def mark_translated(self, chunk_id: int, translated_text: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE chunks
                SET translated_text = ?, status = 'translated', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (translated_text, chunk_id),
            )

    def mark_failed(self, chunk_id: int, error_message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE chunks
                SET translated_text = ?, status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error_message, chunk_id),
            )

    def reset_failed_chunks(self) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE chunks
                SET translated_text = NULL, status = 'extracted', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'failed'
                """
            )
        return cursor.rowcount

    def reset_quota_failures(self) -> int:
        return self.reset_failed_chunks()

    def reset_empty_pages(self, book_id: str) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM book_pages
                WHERE book_id = ? AND status = 'empty'
                """,
                (book_id,),
            )
        return cursor.rowcount

    def reset_range(self, book_id: str, start_page: int, end_page: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE chunks
                SET translated_text = NULL, status = 'extracted', updated_at = CURRENT_TIMESTAMP
                WHERE book_id = ? AND page_number BETWEEN ? AND ?
                """,
                (book_id, start_page, end_page),
            )

    def reset_mock_translations(self, book_id: str, start_page: int, end_page: int) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE chunks
                SET translated_text = NULL, status = 'extracted', updated_at = CURRENT_TIMESTAMP
                WHERE book_id = ?
                    AND page_number BETWEEN ? AND ?
                    AND status = 'translated'
                    AND translated_text LIKE '%TRADUCAO MOCK%'
                """,
                (book_id, start_page, end_page),
            )
        return cursor.rowcount

    def reset_all_mock_translations(self) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE chunks
                SET translated_text = NULL, status = 'extracted', updated_at = CURRENT_TIMESTAMP
                WHERE translated_text LIKE '%TRADUCAO MOCK%'
                """
            )
        return cursor.rowcount

    def reset_all_data(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM book_pages")
            conn.execute("DELETE FROM books")

    def get_progress(self, book_id: str) -> dict[str, int]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_chunks,
                    SUM(CASE WHEN status = 'translated' THEN 1 ELSE 0 END) AS translated_chunks,
                    COUNT(DISTINCT CASE WHEN status = 'translated' THEN page_number END) AS translated_pages
                FROM chunks
                WHERE book_id = ?
                """,
                (book_id,),
            ).fetchone()
        return {
            "total_chunks": int(row["total_chunks"] or 0),
            "translated_chunks": int(row["translated_chunks"] or 0),
            "translated_pages": int(row["translated_pages"] or 0),
        }

    def get_page_statuses(self, book_id: str) -> dict[int, dict[str, int]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    page_number,
                    COUNT(*) AS total_chunks,
                    SUM(CASE WHEN status = 'translated' THEN 1 ELSE 0 END) AS translated_chunks,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_chunks
                FROM chunks
                WHERE book_id = ?
                GROUP BY page_number
                ORDER BY page_number
                """,
                (book_id,),
            ).fetchall()
            page_rows = conn.execute(
                """
                SELECT page_number, status, total_chunks
                FROM book_pages
                WHERE book_id = ?
                """,
                (book_id,),
            ).fetchall()
        statuses = {
            int(row["page_number"]): {
                "total_chunks": int(row["total_chunks"] or 0),
                "translated_chunks": int(row["translated_chunks"] or 0),
                "failed_chunks": int(row["failed_chunks"] or 0),
                "empty": 0,
            }
            for row in rows
        }
        for row in page_rows:
            page_number = int(row["page_number"])
            status = statuses.setdefault(
                page_number,
                {
                    "total_chunks": int(row["total_chunks"] or 0),
                    "translated_chunks": 0,
                    "failed_chunks": 0,
                    "empty": 0,
                },
            )
            if row["status"] == "empty":
                status["empty"] = 1
            if row["status"] == "extracted" and status["total_chunks"] == 0:
                status["total_chunks"] = int(row["total_chunks"] or 0)
        return statuses

    def get_translated_page_bounds(self, book_id: str) -> tuple[int, int] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT MIN(page_number) AS start_page, MAX(page_number) AS end_page
                FROM chunks
                WHERE book_id = ? AND status = 'translated'
                """,
                (book_id,),
            ).fetchone()
        if row["start_page"] is None or row["end_page"] is None:
            return None
        return int(row["start_page"]), int(row["end_page"])
