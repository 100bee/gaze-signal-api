from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from gaze_signal_api.storage.models import Base


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        connect_args: dict[str, object] = {}
        engine_kwargs: dict[str, object] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if ":memory:" in url:
                engine_kwargs["poolclass"] = StaticPool
            self._ensure_parent(url)

        self.engine: Engine = create_engine(
            url,
            connect_args=connect_args,
            future=True,
            **engine_kwargs,
        )
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
            if ":memory:" not in url:
                # WAL lets the API read summaries while the analysis thread writes
                # event batches. Configure it once before application traffic starts.
                with self.engine.connect() as connection:
                    connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    @staticmethod
    def _ensure_parent(url: str) -> None:
        prefix = "sqlite:///"
        if not url.startswith(prefix) or ":memory:" in url:
            return
        raw_path = url.removeprefix(prefix)
        if raw_path:
            Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()
