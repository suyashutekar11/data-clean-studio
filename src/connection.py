from typing import Tuple, Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
import logging
import secrets
import threading

logger = logging.getLogger(__name__)


class MySQLConnectionManager:
    """Handles secure MySQL connections and server-side connection sessions."""

    _sessions: Dict[str, Dict[str, Any]] = {}
    _lock = threading.Lock()

    @staticmethod
    def build_connection_url(
        host: str,
        port: int,
        user: str,
        password: str,
        database: Optional[str] = None,
    ):
        from sqlalchemy.engine import URL

        return URL.create(
            drivername="mysql+mysqlconnector",
            username=user,
            password=password,
            host=host,
            port=port,
            database=database,
        )

    @classmethod
    def create_engine(
        cls,
        host: str,
        port: int,
        user: str,
        password: str,
        database: Optional[str] = None,
        connect_timeout: int = 5,
    ) -> Engine:
        url = cls.build_connection_url(host, port, user, password, database)

        return create_engine(
            url,
            connect_args={"connect_timeout": connect_timeout},
            pool_pre_ping=True,
        )

    @classmethod
    def create_session(
        cls,
        host: str,
        port: int,
        user: str,
        password: str,
    ) -> Tuple[str, Engine, str]:
        """Create a server-side session and return its opaque token."""
        engine = cls.create_engine(host, port, user, password)

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            engine.dispose()
            raise

        token = secrets.token_urlsafe(32)

        with cls._lock:
            cls._sessions[token] = {
                "engine": engine,
                "host": host,
                "port": int(port),
                "username": user,
            }

        return token, engine, "Successfully connected to MySQL server!"

    @classmethod
    def restore_session(cls, token: Optional[str]):
        """Restore a server-side session using its opaque token."""
        if not token:
            return None

        with cls._lock:
            session = cls._sessions.get(token)

        if not session:
            return None

        engine = session["engine"]

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            return {
                "engine": engine,
                "host": session["host"],
                "port": session["port"],
                "username": session["username"],
            }
        except Exception as exc:
            logger.warning("Stored MySQL session is invalid: %s", exc)
            cls.remove_session(token)
            return None

    @classmethod
    def remove_session(cls, token: Optional[str]) -> None:
        """Dispose and remove a server-side connection session."""
        if not token:
            return

        with cls._lock:
            session = cls._sessions.pop(token, None)

        if session:
            try:
                session["engine"].dispose()
            except Exception:
                logger.exception("Error disposing MySQL engine.")

    @classmethod
    def test_connection(
        cls,
        host: str,
        port: int,
        user: str,
        password: str,
        database: Optional[str] = None,
    ) -> Tuple[bool, str]:
        try:
            engine = cls.create_engine(host, port, user, password, database)

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            engine.dispose()
            return True, "Successfully connected to MySQL server!"

        except OperationalError as e:
            error_code = getattr(e.orig, "errno", None) if hasattr(e, "orig") else None
            orig_msg = str(e.orig) if hasattr(e, "orig") else str(e)

            logger.error(
                "Operational error during MySQL connection attempt: %s",
                orig_msg,
            )

            if error_code == 1045:
                return False, "Access Denied: Invalid username or password."
            elif error_code in (2003, 2002):
                return (
                    False,
                    f"Connection Failed: Cannot reach MySQL server at "
                    f"'{host}:{port}'. Please check host address, port, "
                    f"or network/firewall.",
                )
            elif error_code == 1049:
                return (
                    False,
                    f"Database Error: Database '{database}' does not exist "
                    f"on this server.",
                )
            elif "timed out" in orig_msg.lower() or "timeout" in orig_msg.lower():
                return (
                    False,
                    "Connection Timeout: Server took too long to respond. "
                    "Check if host and port are correct and reachable.",
                )
            return (
                False,
                f"MySQL Operational Error ({error_code or 'Unknown'}): {orig_msg}",
            )

        except ProgrammingError as e:
            orig_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            logger.error("Programming error during MySQL connection: %s", orig_msg)
            return False, f"Database/Access Error: {orig_msg}"

        except SQLAlchemyError as e:
            logger.error("SQLAlchemy error during connection test: %s", str(e))
            return False, f"Database Connection Error: {str(e)}"

        except Exception as e:
            logger.error("Unexpected error during connection test: %s", str(e))
            return False, f"Unexpected Error: {str(e)}"
