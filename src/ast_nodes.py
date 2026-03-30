"""
AXON Compiler - AST Node Definitions
These dataclasses represent the parsed structure of an AXON program.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SemanticType:
    name: str           # e.g. "user_id", "dollar_amount", "string"
    is_collection: bool = False  # true if type[]

    def __str__(self):
        return f"{self.name}{'[]' if self.is_collection else ''}"


@dataclass
class TypedParam:
    name: str
    type: SemanticType


@dataclass
class BudgetConstraint:
    key: str    # latency | tokens | cost
    value: str  # e.g. "500ms", "1000", "$0.01"


@dataclass
class JsonObject:
    pairs: Dict[str, Any]  # key: value (value may be a Ref or literal)


@dataclass
class Ref:
    """A reference to a value: IN.userId, fetch_user.OUT, etc."""
    parts: List[str]

    def __str__(self):
        return ".".join(self.parts)


@dataclass
class Condition:
    left: Any       # Ref or literal
    op: str         # ==, !=, <, >, <=, >=
    right: Any      # Ref or literal


@dataclass
class DbReadOp:
    table: str
    condition: Optional[Condition]


@dataclass
class DbWriteOp:
    table: str
    condition: Optional[Condition]   # WHERE clause (for updates)
    data: JsonObject


@dataclass
class DbDeleteOp:
    table: str
    condition: Condition


@dataclass
class AssertOp:
    condition: Condition


@dataclass
class ComputeOp:
    function: str   # SUM, AVG, COUNT, MAP, FILTER
    expression: str # raw expression string for now


@dataclass
class EmailOp:
    to: Ref
    template: str


@dataclass
class HttpOp:
    method: str     # GET, POST, PUT, DELETE
    url: Any        # Ref or string literal
    payload: Optional[JsonObject] = None


@dataclass
class McpOp:
    server: str
    tool: str
    args: Optional[Dict[str, Any]] = None


# Union type for operations
Operation = DbReadOp | DbWriteOp | DbDeleteOp | AssertOp | ComputeOp | EmailOp | HttpOp | McpOp


@dataclass
class FaultAction:
    kind: str           # HALT, RETRY, FALLBACK
    argument: str       # reason code, retry count, or node name


@dataclass
class FaultClause:
    condition: Optional[Condition]  # None means "any fault"
    action: FaultAction


@dataclass
class Node:
    name: str
    op: Operation
    out: Optional[TypedParam] = None
    faults: List[FaultClause] = field(default_factory=list)
    inverse: Optional[Operation] = None
    is_async: bool = False
    after: List[str] = field(default_factory=list)


@dataclass
class Graph:
    name: str
    inputs: List[TypedParam]
    output: TypedParam
    budget: List[BudgetConstraint]
    nodes: List[Node]
    return_node: str        # node name whose OUT is the graph return
    rollback_nodes: List[str] = field(default_factory=list)


@dataclass
class Program:
    graphs: List[Graph]
