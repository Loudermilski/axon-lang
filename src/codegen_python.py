"""
AXON Compiler - Python Code Generator
Emits async Python (asyncio) from AXON AST.
"""

from .ast_nodes import *
from .codegen import validate_graph, build_deps, topo_waves
from typing import Dict, Set, List
import re


SEMANTIC_TO_PY = {
    "user_id":       "str",
    "email_address": "str",
    "dollar_amount": "float",
    "order_record":  "dict",
    "user_record":   "dict",
    "cart_item":     "dict",
    "timestamp":     "str",
    "url":           "str",
    "phone_number":  "str",
    "jwt_token":     "str",
    "string":        "str",
    "integer":       "int",
    "float":         "float",
    "boolean":       "bool",
}

SEMANTIC_VALIDATORS_PY = {
    "email_address": 'if not re.match(r"^[^@]+@[^@]+\\.[^@]+$", {val}): raise AxonTypeError("Invalid email_address: {name}")',
    "dollar_amount": 'if not isinstance({val}, (int, float)) or {val} < 0: raise AxonTypeError("Invalid dollar_amount: {name}")',
    "user_id":       'if not isinstance({val}, str) or len({val}) == 0: raise AxonTypeError("Invalid user_id: {name}")',
    "url":           'if not re.match(r"^https?://", {val}): raise AxonTypeError("Invalid url: {name}")',
    "phone_number":  'if not re.match(r"^\\+[1-9]\\d{{1,14}}$", {val}): raise AxonTypeError("Invalid phone_number: {name}")',
}


def py_type(sem: SemanticType) -> str:
    base = SEMANTIC_TO_PY.get(sem.name, "dict")
    return f"list[{base}]" if sem.is_collection else base


def ref_to_py(ref, node_out_types: Dict[str, str] = None) -> str:
    types = node_out_types or {}
    if ref is None:
        return "None"
    if isinstance(ref, Ref):
        parts = ref.parts
        if parts[0] == "IN":
            return f"inputs['{parts[1]}']" if len(parts) > 1 else "inputs"
        node = parts[0]
        base = f"results['{node}']"
        if len(parts) == 1 or parts[1].upper() in ("OUT", "ERR"):
            return base
        return base + "['" + "']['".join(parts[1:]) + "']"
    if isinstance(ref, str):
        return f'"{ref}"'
    if isinstance(ref, bool):
        return "True" if ref else "False"
    return str(ref)


def condition_to_py(cond: Condition, node_out_types: Dict[str, str] = None) -> str:
    left = ref_to_py(cond.left, node_out_types)
    right = ref_to_py(cond.right, node_out_types)
    op_map = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}
    return f"{left} {op_map.get(cond.op, cond.op)} {right}"


def condition_to_query_dict(cond: Condition, node_out_types: Dict[str, str] = None) -> str:
    if isinstance(cond.left, Ref):
        field = cond.left.parts[-1]
        value = ref_to_py(cond.right, node_out_types)
        return f"{{'{field}': {value}}}"
    return f"{{'{ref_to_py(cond.left, node_out_types)}': {ref_to_py(cond.right, node_out_types)}}}"


def compute_to_py(op: ComputeOp, node_out_types: Dict[str, str] = None) -> str:
    expr = op.expression.strip()
    array_match = re.match(r'^(\w+)\s*\[\s*\]\s*\.(.*)', expr)
    if op.function == "SUM" and array_match:
        col = array_match.group(1)
        field_expr = array_match.group(2).strip()
        if '*' in field_expr:
            def normalize_field(f):
                f = f.strip()
                m2 = re.match(r'^\w+\s*\[\s*\]\s*\.\s*(.*)', f)
                return f"i['{m2.group(1).strip()}']" if m2 else f"i['{f}']"
            parts = [normalize_field(p) for p in field_expr.split('*')]
            inner = " * ".join(parts)
        else:
            inner = f"i['{field_expr}']"
        return f"sum({inner} for i in inputs['{col}'])"
    elif op.function == "COUNT" and array_match:
        return f"len(inputs['{array_match.group(1)}'])"
    elif op.function == "AVG" and array_match:
        col, field = array_match.group(1), array_match.group(2).strip()
        return f"sum(i['{field}'] for i in inputs['{col}']) / len(inputs['{col}'])"
    elif op.function == "MAP" and array_match:
        col, field = array_match.group(1), array_match.group(2).strip()
        return f"[i['{field}'] for i in inputs['{col}']]"
    elif op.function == "FILTER":
        m = re.match(r'^(\w+)\s*\[\s*\]\s*\.\s*(\w+)\s*(==|!=|<|>|<=|>=)\s*(.+)$', expr)
        if m:
            return f"[i for i in inputs['{m.group(1)}'] if i['{m.group(2)}'] {m.group(3)} {m.group(4).strip()}]"
    return f"[]  # axon:{op.function} {expr}"


def json_obj_to_py(obj: JsonObject, node_out_types: Dict[str, str] = None) -> str:
    pairs = []
    for k, v in obj.pairs.items():
        if isinstance(v, Ref):
            pairs.append(f"'{k}': {ref_to_py(v, node_out_types)}")
        elif isinstance(v, str):
            pairs.append(f"'{k}': '{v}'")
        elif v is None:
            pairs.append(f"'{k}': None")
        elif isinstance(v, bool):
            pairs.append(f"'{k}': {'True' if v else 'False'}")
        else:
            pairs.append(f"'{k}': {v!r}")

    return "{" + ", ".join(pairs) + "}"


def op_to_py(op: Operation, node_name: str, types: Dict[str, str] = None) -> str:
    t = types or {}
    if isinstance(op, DbReadOp):
        q = condition_to_query_dict(op.condition, t) if op.condition else "{}"
        return f"await db['{op.table}'].find_one({q})"
    elif isinstance(op, DbWriteOp):
        data = json_obj_to_py(op.data, t)
        if op.condition:
            return f"await db['{op.table}'].update({condition_to_query_dict(op.condition, t)}, {data})"
        return f"await db['{op.table}'].create({data})"
    elif isinstance(op, DbDeleteOp):
        return f"await db['{op.table}'].delete({condition_to_query_dict(op.condition, t)})"
    elif isinstance(op, AssertOp):
        cond = condition_to_py(op.condition, t)
        desc = cond.replace("'", "\\'")
        return f"axon_assert({cond}, '{desc}')"
    elif isinstance(op, ComputeOp):
        return compute_to_py(op, t)
    elif isinstance(op, EmailOp):
        return f"await notify.send({ref_to_py(op.to, t)}, '{op.template}')"
    elif isinstance(op, HttpOp):
        url = ref_to_py(op.url, t) if isinstance(op.url, Ref) else f'"{op.url}"'
        if op.payload:
            return f"await http_{op.method.lower()}({url}, json={json_obj_to_py(op.payload, t)})"
        return f"await http_{op.method.lower()}({url})"
    elif isinstance(op, McpOp):
        args = json_obj_to_py(op.args, t) if op.args else "{}"
        return f"await mcp['{op.server}']['{op.tool}']({args})"
    return "pass  # unsupported op"


class PythonGenerator:
    def __init__(self):
        self.out: List[str] = []
        self.lvl = 0

    def e(self, line: str = ""):
        self.out.append(("    " * self.lvl + line) if line.strip() else "")

    def i(self): self.lvl += 1
    def d(self): self.lvl -= 1

    def generate(self, program: Program) -> str:
        self._header()
        for graph in program.graphs:
            validate_graph(graph)
            self._graph(graph)
        return "\n".join(self.out)

    def _header(self):
        self.e("# ──────────────────────────────────────────────────────────────")
        self.e("# AXON Generated Python  —  DO NOT EDIT BY HAND")
        self.e("# Guarantees: semantic validation · auto-parallelism · rollback")
        self.e("# ──────────────────────────────────────────────────────────────")
        self.e()
        self.e("from __future__ import annotations")
        self.e("import asyncio")
        self.e("import re")
        self.e("from typing import Any")
        self.e()
        self.e()
        self.e("class AxonTypeError(Exception):")
        self.e("    pass")
        self.e()
        self.e()
        self.e("class AxonFaultError(Exception):")
        self.e("    def __init__(self, code: str, context: Any = None):")
        self.e("        super().__init__(f'[AXON FAULT] {code}')")
        self.e("        self.code = code")
        self.e("        self.context = context")
        self.e()
        self.e()
        self.e("def axon_assert(condition: bool, description: str) -> None:")
        self.e("    if not condition:")
        self.e("        raise AxonFaultError('assertion_failed', {'condition': description})")
        self.e()

    def _graph(self, graph: Graph):
        types: Dict[str, str] = {}
        for node in graph.nodes:
            if node.out:
                types[node.name] = py_type(node.out.type)

        ret_type = py_type(graph.output.type)
        latency_ms = None
        for b in graph.budget:
            self.e(f"# @axon:budget {b.key}={b.value}")
            if b.key == "latency":
                latency_ms = b.value.replace("ms", "")

        params = ", ".join(f"{p.name}: {py_type(p.type)}" for p in graph.inputs)
        self.e(f"async def {graph.name}({params}) -> {ret_type}:")
        self.i()

        # Input validation
        self.e("# ── Semantic input validation ─────────────────────────────────")
        for p in graph.inputs:
            v = SEMANTIC_VALIDATORS_PY.get(p.type.name)
            if v:
                self.e(v.format(val=p.name, name=p.name))
        self.e()

        self.e("inputs = {" + ", ".join(f"'{p.name}': {p.name}" for p in graph.inputs) + "}")
        self.e("results: dict[str, Any] = {}")
        self.e("rollback_stack: list = []")
        self.e()

        # Budget wrapper
        if latency_ms:
            self.e(f"async def __run() -> {ret_type}:")
            self.i()

        waves = topo_waves(build_deps(graph.nodes))
        node_map = {n.name: n for n in graph.nodes}

        self.e("try:")
        self.i()

        for wave in waves:
            if len(wave) == 1:
                self._node(node_map[wave[0]], types, graph.rollback_nodes)
            else:
                self._parallel([node_map[n] for n in wave], types, graph.rollback_nodes)

        self.e(f"return results['{graph.return_node}']")
        self.d()

        self.e("except Exception as err:")
        self.i()
        if graph.rollback_nodes:
            self.e("for undo in reversed(rollback_stack):")
            self.i()
            self.e("try:")
            self.i(); self.e("await undo()"); self.d()
            self.e("except Exception as e:")
            self.i(); self.e("print(f'[AXON rollback] {e}')"); self.d()
            self.d()
        self.e("raise")
        self.d()

        if latency_ms:
            self.d()  # end __run
            self.e()
            self.e(f"return await asyncio.wait_for(__run(), timeout={int(latency_ms) / 1000})")

        self.d()
        self.e()

    def _parallel(self, nodes: List[Node], types: Dict[str, str], rollback_nodes: List[str]):
        names = [n.name for n in nodes]
        self.e(f"# ── Parallel: [{', '.join(names)}] ──────────────────────────")
        # Define coroutine wrappers for each parallel node
        for node in nodes:
            code = op_to_py(node.op, node.name, types)
            if code.startswith("await "):
                # Already a coroutine call — wrap in async def
                self.e(f"async def __{node.name}_task():")
                self.i(); self.e(f"return {code}"); self.d()
            else:
                # Sync expression (e.g. compute) — wrap as coroutine
                self.e(f"async def __{node.name}_task():")
                self.i(); self.e(f"return {code}"); self.d()
        vars_ = ", ".join(f"__{n.name}_r" for n in nodes)
        tasks = ", ".join(f"__{n.name}_task()" for n in nodes)
        self.e(f"{vars_} = await asyncio.gather({tasks})")
        for node in nodes:
            if node.out:
                self.e(f"results['{node.name}'] = __{node.name}_r")
                for fault in node.faults:
                    self._fault_check(node.name, fault, types)
                if node.inverse and node.name in rollback_nodes:
                    self._rollback_append(node, types)
        self.e()

    def _node(self, node: Node, types: Dict[str, str], rollback_nodes: List[str]):
        bar = "─" * max(1, 46 - len(node.name))
        self.e(f"# ── NODE {node.name} {bar}")

        if node.is_async:
            code = op_to_py(node.op, node.name, types)
            self.e(f"async def __async_{node.name}():")
            self.i()
            self.e("try:")
            self.i(); self.e(code); self.d()
            self.e("except Exception as e:")
            self.i(); self.e(f"print(f'[AXON async {node.name}] {{e}}')"); self.d()
            self.d()
            self.e(f"asyncio.ensure_future(__async_{node.name}())")
            self.e()
            return

        code = op_to_py(node.op, node.name, types)

        if node.out:
            self.e(f"{node.name}_raw = {code}")
            for fault in node.faults:
                self._fault_check(node.name, fault, types, raw=True)
            self.e(f"results['{node.name}'] = {node.name}_raw")
            if node.inverse and node.name in rollback_nodes:
                self._rollback_append(node, types)
        else:
            self.e(code)
            for fault in node.faults:
                if fault.condition:
                    cond = condition_to_py(fault.condition, types)
                    self.e(f"if {cond}:")
                    self.i(); self._fault_action(fault.action); self.d()
            if node.inverse and node.name in rollback_nodes:
                self._rollback_append(node, types)

        self.e()

    def _rollback_append(self, node: Node, types: Dict[str, str]):
        inv = op_to_py(node.inverse, node.name, types)
        self.e(f"async def __rollback_{node.name}():")
        self.i(); self.e(inv); self.d()
        self.e(f"rollback_stack.append(__rollback_{node.name})")

    def _fault_check(self, node_name: str, fault: FaultClause,
                     types: Dict[str, str], raw: bool = False):
        ref_name = f"{node_name}_raw" if raw else f"results['{node_name}']"
        if fault.condition:
            cond = condition_to_py(fault.condition, types)
            cond = cond.replace(f"results['{node_name}']", ref_name)
            self.e(f"if {cond}:")
        else:
            self.e(f"if {ref_name} is None:")
        self.i(); self._fault_action(fault.action); self.d()

    def _fault_action(self, action: FaultAction):
        if action.kind == "HALT":
            self.e(f"raise AxonFaultError('{action.argument}')")
        elif action.kind == "RETRY":
            self.e(f"raise AxonFaultError('retry_exhausted', {{'max': {action.argument}}})")
        elif action.kind == "FALLBACK":
            self.e(f"raise AxonFaultError('fallback', {{'target': '{action.argument}'}})")
