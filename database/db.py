import os
from dataclasses import dataclass
from typing import Optional

import keyring
import mysql.connector
import oracledb
import psycopg
from dotenv import load_dotenv


load_dotenv()

DEFAULT_ORACLE_CLIENT_PATH = r"C:\oraclexe\app\oracle\product\11.2.0\server\bin"
_oracle_client_initialized = False


def _ensure_oracle_client():
    global _oracle_client_initialized
    if _oracle_client_initialized:
        return

    try:
        if not oracledb.is_thin_mode():
            _oracle_client_initialized = True
            return
    except AttributeError:
        pass

    client_path = os.getenv("ORACLE_CLIENT_PATH", DEFAULT_ORACLE_CLIENT_PATH)
    if not os.path.isdir(client_path):
        raise RuntimeError(
            "Oracle Client was not found.\n\n"
            f"Expected path:\n{client_path}\n\n"
            "Set ORACLE_CLIENT_PATH or install/configure Oracle Client."
        )

    oracledb.init_oracle_client(lib_dir=client_path)
    _oracle_client_initialized = True


@dataclass
class ConnectionProfile:
    database_type: str
    host: str
    port: int
    database: str
    username: str
    profile_name: str = ""

    def __post_init__(self):
        self.database_type = self.database_type.strip().lower()
        if self.database_type == "postgresql":
            self.database_type = "postgres"

        self.host = self.host.strip()
        self.database = self.database.strip()
        self.username = self.username.strip()

        if not self.profile_name:
            self.profile_name = (
                f"{self.database_type.upper()} - "
                f"{self.username}@{self.host}"
            )

        if not self.host:
            raise ValueError("Database host cannot be empty.")
        if not self.username:
            raise ValueError("Database username cannot be empty.")
        if not self.database:
            raise ValueError("Database/service name cannot be empty.")
        if self.port <= 0:
            raise ValueError("Database port must be greater than zero.")
        if self.database_type not in {"oracle", "mysql", "postgres"}:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    @property
    def keyring_service(self):
        return (
            "QRYVANTA/"
            f"{self.database_type}/"
            f"{self.host}:{self.port}/"
            f"{self.database}/"
            f"{self.username}"
        )

    def to_dict(self):
        return {
            "profile_name": self.profile_name,
            "database_type": self.database_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            database_type=data["database_type"],
            host=data["host"],
            port=int(data["port"]),
            database=data["database"],
            username=data["username"],
            profile_name=data.get("profile_name", ""),
        )


_active_profile: Optional[ConnectionProfile] = None
_active_password: Optional[str] = None


def set_active_profile(profile: ConnectionProfile, password: str):
    global _active_profile, _active_password
    if not isinstance(profile, ConnectionProfile):
        raise TypeError("profile must be a ConnectionProfile.")
    if not password:
        raise ValueError("Password cannot be empty.")
    _active_profile = profile
    _active_password = password


def get_active_profile():
    return _active_profile


def clear_active_profile():
    global _active_profile, _active_password
    _active_profile = None
    _active_password = None


def save_password(profile: ConnectionProfile, password: str):
    if not password:
        raise ValueError("Password cannot be empty.")
    keyring.set_password(profile.keyring_service, profile.username, password)


def get_saved_password(profile: ConnectionProfile):
    return keyring.get_password(profile.keyring_service, profile.username)


def delete_saved_password(profile: ConnectionProfile):
    try:
        keyring.delete_password(profile.keyring_service, profile.username)
    except keyring.errors.PasswordDeleteError:
        pass


def _profile_from_environment():
    username = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN", "localhost:1521/XE")

    if not username or not password:
        raise RuntimeError(
            "No active database profile is configured and "
            "ORACLE_USER / ORACLE_PASSWORD are not available in .env."
        )

    host, port, service = "localhost", 1521, "XE"

    if "/" in dsn:
        host_port, service = dsn.split("/", 1)
        if ":" in host_port:
            host, port_text = host_port.rsplit(":", 1)
            port = int(port_text)
        else:
            host = host_port
    elif ":" in dsn:
        host, port_text = dsn.rsplit(":", 1)
        port = int(port_text)

    return ConnectionProfile(
        database_type="oracle",
        host=host,
        port=port,
        database=service,
        username=username,
        profile_name="Development Oracle",
    ), password


def get_connection(profile=None, password=None):
    if profile is None:
        profile = _active_profile
        if password is None:
            password = _active_password

    if profile is None:
        profile, password = _profile_from_environment()
    elif password is None:
        password = get_saved_password(profile) or _active_password

    if not password:
        raise RuntimeError(
            f"No password is available for {profile.profile_name}."
        )

    if profile.database_type == "oracle":
        _ensure_oracle_client()
        dsn = f"{profile.host}:{profile.port}/{profile.database}"
        return oracledb.connect(
            user=profile.username,
            password=password,
            dsn=dsn,
        )

    if profile.database_type == "mysql":
        return mysql.connector.connect(
            host=profile.host,
            port=profile.port,
            user=profile.username,
            password=password,
            database=profile.database,
        )

    if profile.database_type == "postgres":
        return psycopg.connect(
            host=profile.host,
            port=profile.port,
            user=profile.username,
            password=password,
            dbname=profile.database,
        )

    raise ValueError(f"Unsupported database type: {profile.database_type}")


def test_connection(profile: ConnectionProfile, password: str):
    connection = None
    try:
        connection = get_connection(profile=profile, password=password)
        return True, "Connected successfully."
    except Exception as error:
        return False, str(error)
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def connect_active_profile(profile: ConnectionProfile, password: str, remember=False):
    success, message = test_connection(profile, password)
    if not success:
        raise RuntimeError(message)

    set_active_profile(profile, password)

    if remember:
        save_password(profile, password)

    return True


def disconnect():
    clear_active_profile()
