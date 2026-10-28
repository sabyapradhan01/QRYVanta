from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from core.plan_model import PlanModel
from core.schema_model import SchemaModel


@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    rowcount: Optional[int] = None
    message: str = ""


class DatabaseAdapter(ABC):
    """Common interface implemented by every QRYVANTA database backend."""

    name = "Generic"
    dialect = ""

    def __init__(self, profile=None, password: str | None = None):
        self.profile = profile
        self.password = password

    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def get_schema(self) -> SchemaModel:
        raise NotImplementedError

    @abstractmethod
    def explain(self, query: str) -> PlanModel:
        raise NotImplementedError

    @abstractmethod
    def execute(self, query: str) -> QueryResult:
        raise NotImplementedError

    @abstractmethod
    def quote_identifier(self, name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def sample_query(self, table: str, limit: int = 500) -> str:
        raise NotImplementedError

    def test(self) -> bool:
        connection = self.connect()
        try:
            return True
        finally:
            connection.close()
