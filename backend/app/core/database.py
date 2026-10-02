"""SQLAlchemy engine, session factory and declarative base."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _is_memory_sqlite(url: str) -> bool:
    return url in ("sqlite://", "sqlite:///:memory:")


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        # FastAPI serves requests from a thread pool; the background auction
        # worker also uses its own sessions.
        kwargs["connect_args"] = {"check_same_thread": False}
        if _is_memory_sqlite(url):
            kwargs["poolclass"] = StaticPool

    eng = create_engine(url, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if not _is_memory_sqlite(url):
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return eng


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Models must be imported so they register on Base."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    """Drop every table actually in the database (including ones no longer in
    the models) and recreate the current schema."""
    import app.models  # noqa: F401
    from sqlalchemy import MetaData

    existing = MetaData()
    existing.reflect(bind=engine)
    sqlite = engine.dialect.name == "sqlite"
    with engine.connect() as conn:
        if sqlite:
            # pysqlite runs PRAGMAs outside a transaction, so this takes effect.
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.commit()
        existing.drop_all(bind=conn)
        conn.commit()
        if sqlite:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.commit()
    Base.metadata.create_all(bind=engine)
