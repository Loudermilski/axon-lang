"""
AXON Compiler - AST Node Definitions
These dataclasses represent the parsed structure of an AXON program.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set




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
class Ref:
    """A reference to a value: IN.userId, fetch_user.OUT, etc."""
    parts: List[str]

    def __str__(self):
        return ".".join(self.parts)

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        if self.parts[0] in node_names:
            return {self.parts[0]}
        return set()

    def is_state(self) -> bool:
        return self.parts[0] == "STATE"


@dataclass
class Condition:
    left: Any       # Ref or literal
    op: str         # ==, !=, <, >, <=, >=
    right: Any      # Ref or literal

    def __str__(self):
        return f"{self.left} {self.op} {self.right}"

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = set()
        if isinstance(self.left, Ref):
            refs.update(self.left.get_refs(node_names))
        if isinstance(self.right, Ref):
            refs.update(self.right.get_refs(node_names))
        return refs


@dataclass
class JsonObject:
    pairs: Dict[str, Any]  # key: value (value may be a Ref or literal)

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = set()
        for v in self.pairs.values():
            if isinstance(v, Ref):
                refs.update(v.get_refs(node_names))
        return refs


@dataclass
class DbReadOp:
    table: str
    condition: Optional[Condition]

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.condition.get_refs(node_names) if self.condition else set()


@dataclass
class DbWriteOp:
    table: str
    condition: Optional[Condition]   # WHERE clause (for updates)
    data: JsonObject

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = self.data.get_refs(node_names)
        if self.condition:
            refs.update(self.condition.get_refs(node_names))
        return refs


@dataclass
class DbDeleteOp:
    table: str
    condition: Condition

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.condition.get_refs(node_names)


@dataclass
class AssertOp:
    condition: Condition

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.condition.get_refs(node_names)


@dataclass
class ComputeOp:
    function: str   # SUM, AVG, COUNT, MAP, FILTER
    expression: str # raw expression string for now

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return set()


@dataclass
class EmailOp:
    to: Ref
    template: str

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.to.get_refs(node_names)


@dataclass
class HttpOp:
    method: str     # GET, POST, PUT, DELETE
    url: Any        # Ref or string literal
    payload: Optional[JsonObject] = None

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = set()
        if isinstance(self.url, Ref):
            refs.update(self.url.get_refs(node_names))
        if self.payload:
            refs.update(self.payload.get_refs(node_names))
        return refs


@dataclass
class McpOp:
    server: str
    tool: str
    args: Optional[JsonObject] = None

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.args.get_refs(node_names) if self.args else set()


@dataclass
class HumanOp:
    kind: str       # approve | input
    prompt: str

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return set()


@dataclass
class CallOp:
    graph_name: str
    args: Optional[JsonObject] = None

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.args.get_refs(node_names) if self.args else set()


@dataclass
class ForEachOp:
    iterator: str
    collection: Ref
    operation: 'Operation'

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = self.collection.get_refs(node_names)
        refs.update(self.operation.get_refs(node_names))
        return refs


@dataclass
class StreamOp:
    operation: 'Operation'
    target: str

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        return self.operation.get_refs(node_names)


@dataclass
class MatchOp:
    ref: Ref
    arms: List[tuple[Any, 'Operation']] # value -> operation

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = self.ref.get_refs(node_names)
        for _, op in self.arms:
            refs.update(op.get_refs(node_names))
        return refs


@dataclass
class WhileOp:
    condition: 'Condition'
    operation: 'Operation'

    def get_refs(self, node_names: Set[str]) -> Set[str]:
        refs = self.condition.get_refs(node_names)
        refs.update(self.operation.get_refs(node_names))
        return refs


# Union type for operations
Operation = DbReadOp | DbWriteOp | DbDeleteOp | AssertOp | ComputeOp | EmailOp | HttpOp | McpOp | HumanOp | CallOp | ForEachOp | WhileOp | MatchOp | StreamOp


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
    if_cond: Optional[Condition] = None
    out: Optional[TypedParam] = None
    faults: List[FaultClause] = field(default_factory=list)
    inverse: Optional[Operation] = None
    is_async: bool = False
    after: List[str] = field(default_factory=list)

    def get_dependencies(self, node_names: Set[str]) -> Set[str]:
        deps = set(a for a in self.after if a in node_names)
        if self.if_cond:
            deps.update(self.if_cond.get_refs(node_names))
        deps.update(self.op.get_refs(node_names))
        return deps


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
class CustomType:
    name: str
    fields: List[TypedParam]


@dataclass
class Actor:
    name: str
    state: List[TypedParam]
    graphs: List[Graph]


@dataclass
class Program:
    custom_types: List[CustomType] = field(default_factory=list)
    actors: List[Actor] = field(default_factory=list)
    graphs: List[Graph] = field(default_factory=list)
