from dataclasses import dataclass
from typing import Optional


@dataclass
class PlanNode:
    operation: str
    table: Optional[str] = None
    index: Optional[str] = None
    estimated_rows: Optional[float] = None
    cost: Optional[float] = None
    depth: int = 0
    details: str = ""


class PlanModel:
    def __init__(self):
        self.nodes: list[PlanNode] = []

    def add(self, node: PlanNode):
        self.nodes.append(node)

    def has_operation(self, operation: str) -> bool:
        operation = operation.upper()
        return any(node.operation.upper() == operation for node in self.nodes)

    def table_scans(self):
        return [node for node in self.nodes if node.operation == "TABLE_SCAN"]

    def index_scans(self):
        return [
            node for node in self.nodes
            if node.operation in {
                "INDEX_SCAN",
                "INDEX_LOOKUP",
                "INDEX_RANGE_SCAN",
            }
        ]

    def joins(self):
        join_ops = {
            "NESTED_LOOPS",
            "HASH_JOIN",
            "MERGE_JOIN",
            "NESTED_LOOP_JOIN",
        }
        return [
            node for node in self.nodes
            if node.operation.upper() in join_ops
            or node.operation.upper().endswith("_JOIN")
        ]

    def sorts(self):
        return [
            node for node in self.nodes
            if node.operation in {
                "SORT",
                "SORT_ORDER_BY",
                "SORT_GROUP_BY",
            }
        ]

    def temporary_operations(self):
        return [node for node in self.nodes if node.operation == "TEMPORARY"]

    def tables(self):
        return [node.table for node in self.nodes if node.table]

    def indexes(self):
        return [node.index for node in self.nodes if node.index]
