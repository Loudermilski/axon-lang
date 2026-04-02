"""
AXON Compiler - TypeScript Code Generator v0.2
Fixes:
  - WHERE clause now emits query objects { field: value }
  - Node ref resolution uses typed casting (results.node as Type).field
  - Compute expressions properly parsed for SUM/AVG/COUNT
  - INVERSE enforcement: db.write without INVERSE is a compile error
  - BUDGET latency wraps execution in Promise.race timeout
"""

from .ast_nodes import *
from typing import Dict, Set, List, Optional
import re

SEMANTIC_TO_TS = {
    "user_id":       "string",
    "email_address": "string",
    "dollar_amount": "number",
    "order_record":  "OrderRecord",
    "user_record":   "UserRecord",
    "cart_item":     "CartItem",
    "timestamp":     "string",
    "url":           "string",
    "phone_number":  "string",
    "jwt_token":     "string",
    "string":        "string",
    "integer":       "number",
    "float":         "number",
    "boolean":       "boolean",
}

SEMANTIC_VALIDATORS = {
    "email_address": 'if (!/^[^@]+@[^@]+\\.[^@]+$/.test({val})) throw new AxonTypeError("Invalid email_address: {name}");',
    "dollar_amount": 'if (typeof {val} !== "number" || {val} < 0) throw new AxonTypeError("Invalid dollar_amount: {name}");',
    "user_id":       'if (typeof {val} !== "string" || {val}.length === 0) throw new AxonTypeError("Invalid user_id: {name}");',
    "url":           'if (!/^https?:\\/\\//.test({val})) throw new AxonTypeError("Invalid url: {name}");',
    "phone_number":  'if (!/^\\+[1-9]\\d{1,14}$/.test({val})) throw new AxonTypeError("Invalid phone_number: {name}");',
}


def ts_type(sem: SemanticType) -> str:
    base = SEMANTIC_TO_TS.get(sem.name, sem.name)
    return f"{base}[]" if sem.is_collection else base


def ref_to_ts(ref: Any, node_out_types: Dict[str, str] = None) -> str:
    types = node_out_types or {}
    if ref is None:
        return "null"
    if isinstance(ref, Ref):
        parts = ref.parts
        if parts[0] == "IN":
            return f"inputs.{'.'.join(parts[1:])}" if len(parts) > 1 else "inputs"
        node = parts[0]
        if node in types:
            ts_t = types[node]
            base = f"(results.{node} as {ts_t})"
            if len(parts) == 1 or parts[1].upper() in ("OUT", "ERR"):
                return base
            return base + "." + ".".join(parts[1:])
        return ".".join(parts)
    if isinstance(ref, str):
        return f'"{ref}"'
    if isinstance(ref, bool):
        return "true" if ref else "false"
    return str(ref)


def condition_to_ts(cond: Condition, node_out_types: Dict[str, str] = None) -> str:
    left = ref_to_ts(cond.left, node_out_types)
    right = ref_to_ts(cond.right, node_out_types)
    op_map = {"==": "===", "!=": "!==", "<": "<", ">": ">", "<=": "<=", ">=": ">="}
    return f"{left} {op_map.get(cond.op, cond.op)} {right}"


def condition_to_query_obj(cond: Condition, node_out_types: Dict[str, str] = None) -> str:
    """WHERE id == IN.userId  →  { id: inputs.userId }"""
    if isinstance(cond.left, Ref):
        field = cond.left.parts[-1]
        value = ref_to_ts(cond.right, node_out_types)
        return f"{{ {field}: {value} }}"
    return f"{{ {ref_to_ts(cond.left, node_out_types)}: {ref_to_ts(cond.right, node_out_types)} }}"


def compute_to_ts(op: ComputeOp, node_out_types: Dict[str, str] = None) -> str:
    expr = op.expression.strip()
    array_match = re.match(r'^(\w+)\s*\[\s*\]\s*\.(.*)', expr)
    if op.function == "SUM" and array_match:
        col = array_match.group(1)
        field_expr = array_match.group(2).strip()
        if '*' in field_expr:
            # Handle: price * collection[].quantity  OR  price * quantity
            def normalize_field(f):
                f = f.strip()
                # Strip leading collection[]. if present
                m2 = re.match(r'^\w+\s*\[\s*\]\s*\.\s*(.*)', f)
                return f"i.{m2.group(1).strip()}" if m2 else f"i.{f}"
            parts = [normalize_field(p) for p in field_expr.split('*')]
            inner = " * ".join(parts)
        else:
            inner = f"i.{field_expr}"
        return f"inputs.{col}.reduce((acc, i) => acc + {inner}, 0)"
    elif op.function == "COUNT" and array_match:
        return f"inputs.{array_match.group(1)}.length"
    elif op.function == "AVG" and array_match:
        col, field = array_match.group(1), array_match.group(2).strip()
        return f"inputs.{col}.reduce((acc, i) => acc + i.{field}, 0) / inputs.{col}.length"
    elif op.function == "MAP" and array_match:
        col, field = array_match.group(1), array_match.group(2).strip()
        return f"inputs.{col}.map(i => i.{field})"
    elif op.function == "FILTER":
        m = re.match(r'^(\w+)\s*\[\s*\]\s*\.\s*(\w+)\s*(==|!=|<|>|<=|>=)\s*(.+)$', expr)
        if m:
            return f"inputs.{m.group(1)}.filter(i => i.{m.group(2)} {m.group(3)} {m.group(4).strip()})"
    return f"/* axon:{op.function} {expr} */ []"


def json_obj_to_ts(obj: JsonObject, node_out_types: Dict[str, str] = None) -> str:
    pairs = []
    for k, v in obj.pairs.items():
        if isinstance(v, Ref):
            pairs.append(f"{k}: {ref_to_ts(v, node_out_types)}")
        elif isinstance(v, str) and not v.startswith('"'):
            pairs.append(f'{k}: "{v}"')
        elif v is None:
            pairs.append(f"{k}: null")
        elif isinstance(v, bool):
            pairs.append(f"{k}: {'true' if v else 'false'}")
        else:
            pairs.append(f"{k}: {v!r}")
    return "{ " + ", ".join(pairs) + " }"


def op_to_ts(op: Operation, node_name: str, types: Dict[str, str] = None) -> str:
    t = types or {}
    if isinstance(op, DbReadOp):
        q = condition_to_query_obj(op.condition, t) if op.condition else "{}"
        return f"await db.{op.table}.findOne({q})"
    elif isinstance(op, DbWriteOp):
        data = json_obj_to_ts(op.data, t)
        if op.condition:
            return f"await db.{op.table}.update({condition_to_query_obj(op.condition, t)}, {data})"
        return f"await db.{op.table}.create({data})"
    elif isinstance(op, DbDeleteOp):
        return f"await db.{op.table}.delete({condition_to_query_obj(op.condition, t)})"
    elif isinstance(op, AssertOp):
        cond = condition_to_ts(op.condition, t)
        return f"((): void => {{ if (!({cond})) throw new AxonFaultError(\"assertion_failed\", {{ condition: `{cond}` }}); }})()"
    elif isinstance(op, ComputeOp):
        return compute_to_ts(op, t)
    elif isinstance(op, EmailOp):
        return f'await notify.send({ref_to_ts(op.to, t)}, "{op.template}")'
    elif isinstance(op, HttpOp):
        url = ref_to_ts(op.url, t) if isinstance(op.url, Ref) else f'"{op.url}"'
        body = f', body: JSON.stringify({json_obj_to_ts(op.payload, t)})' if op.payload else ""
        return f'await fetch({url}, {{ method: "{op.method}"{body} }}).then(r => r.json())'
    elif isinstance(op, McpOp):
        args = json_obj_to_ts(op.args, t) if op.args else "{}"
        return f"await mcp.{op.server}.{op.tool}({args})"
    elif isinstance(op, HumanOp):
        if op.kind == "approve":
            return f"await human.approve({ref_to_ts(op.prompt, t)})"
        else:
            return f"await human.input({ref_to_ts(op.prompt, t)})"
    elif isinstance(op, CallOp):
        args = json_obj_to_ts(op.args, t) if op.args else "{}"
        return f"await {op.graph_name}({args})"
    return "/* unsupported op */"


# ─── Compiler Validation ─────────────────────────────────────────────────────

class CompileError(Exception):
    pass


def validate_graph(graph: Graph):
    node_names = {n.name for n in graph.nodes}
    if graph.return_node not in node_names:
        raise CompileError(f"RETURN '{graph.return_node}' not found in NODEs.")
    for node in graph.nodes:
        if isinstance(node.op, DbWriteOp) and node.inverse is None:
            raise CompileError(
                f"NODE '{node.name}': db.write requires INVERSE.\n"
                f"  Add: INVERSE db.delete {node.op.table} WHERE id == {node.name}.id"
            )
        for dep in node.after:
            if dep not in node_names:
                raise CompileError(f"NODE '{node.name}': AFTER '{dep}' does not exist.")


# ─── Parallelism ─────────────────────────────────────────────────────────────

def build_deps(nodes: List[Node]) -> Dict[str, Set[str]]:
    names = {n.name for n in nodes}
    return {n.name: n.get_dependencies(names) for n in nodes}


def topo_waves(deps: Dict[str, Set[str]]) -> List[List[str]]:
    remaining = {k: set(v) for k, v in deps.items()}
    done: Set[str] = set()
    waves = []
    while remaining:
        wave = sorted(n for n, d in remaining.items() if d.issubset(done))
        if not wave:
            raise CompileError(f"Circular dependency: {sorted(remaining)}")
        waves.append(wave)
        for n in wave:
            del remaining[n]
            done.add(n)
    return waves


# ─── Generator ───────────────────────────────────────────────────────────────

class TypeScriptGenerator:
    def __init__(self):
        self.out: List[str] = []
        self.lvl = 0

    def e(self, line: str = ""):
        self.out.append(("  " * self.lvl + line) if line.strip() else "")

    def i(self): self.lvl += 1
    def d(self): self.lvl -= 1

    def generate(self, program: Program) -> str:
        self._header()
        for ct in program.custom_types:
            self._custom_type(ct)
        for graph in program.graphs:
            validate_graph(graph)
            self._graph(graph)
        return "\n".join(self.out)

    def _custom_type(self, ct: CustomType):
        self.e(f"export class {ct.name} {{")
        self.i()
        for field in ct.fields:
            self.e(f"public {field.name}: {ts_type(field.type)};")
        self.e()
        self.e("constructor(data: any) {")
        self.i()
        for field in ct.fields:
            self.e(f"this.{field.name} = data.{field.name};")
            v = SEMANTIC_VALIDATORS.get(field.type.name)
            if v:
                self.e(v.format(val=f"this.{field.name}", name=f"{ct.name}.{field.name}"))
        self.d(); self.e("}")
        self.d(); self.e("}")
        self.e()

    def _header(self):
        self.e("// ──────────────────────────────────────────────────────────────")
        self.e("// AXON Generated TypeScript v0.2  —  DO NOT EDIT BY HAND")
        self.e("// Guarantees: semantic validation · auto-parallelism · rollback")
        self.e("// ──────────────────────────────────────────────────────────────")
        self.e()
        self.e("export class AxonTypeError extends Error {")
        self.i(); self.e('constructor(msg: string) { super(msg); this.name = "AxonTypeError"; }'); self.d()
        self.e("}")
        self.e("export class AxonFaultError extends Error {")
        self.i()
        self.e("constructor(public readonly code: string, public readonly context?: unknown) {")
        self.i(); self.e('super(`[AXON FAULT] ${code}`); this.name = "AxonFaultError";'); self.d()
        self.e("}"); self.d(); self.e("}")
        self.e()
        self.e("export interface UserRecord  { id: string; email: string; balance: number; [k: string]: unknown; }")
        self.e("export interface OrderRecord { id: string; userId: string; total: number; status: string; [k: string]: unknown; }")
        self.e("export interface CartItem    { id: string; price: number; quantity: number; sku: string; }")
        self.e()
        self.e("declare const db: Record<string, {")
        self.i()
        self.e("findOne: (q: Record<string, unknown>) => Promise<unknown>;")
        self.e("create:  (d: Record<string, unknown>) => Promise<unknown>;")
        self.e("update:  (q: Record<string, unknown>, d: Record<string, unknown>) => Promise<unknown>;")
        self.e("delete:  (q: Record<string, unknown>) => Promise<void>;")
        self.d(); self.e("}>;")
        self.e("declare const notify: { send: (to: string, tpl: string) => Promise<void>; };")
        self.e("declare const mcp:    Record<string, Record<string, (a: unknown) => Promise<unknown>>>;")
        self.e("declare const human:  { approve: (p: string) => Promise<boolean>; input: (p: string) => Promise<string>; };")
        self.e()

    def _graph(self, graph: Graph):
        validate_graph(graph)

        # Build type map for ref resolution
        types: Dict[str, str] = {}
        for node in graph.nodes:
            if node.out:
                types[node.name] = ts_type(node.out.type)

        ret_type = ts_type(graph.output.type)
        latency_ms = None
        for b in graph.budget:
            self.e(f"// @axon:budget {b.key}={b.value}")
            if b.key == "latency":
                latency_ms = b.value.replace("ms", "")

        in_shape = "{ " + "; ".join(f"{p.name}: {ts_type(p.type)}" for p in graph.inputs) + " }"
        self.e(f"export async function {graph.name}(")
        self.i(); self.e(f"inputs: {in_shape}"); self.d()
        self.e(f"): Promise<{ret_type}> {{")
        self.i()

        # Validate inputs
        self.e("// ── Semantic input validation ─────────────────────────────────")
        for p in graph.inputs:
            v = SEMANTIC_VALIDATORS.get(p.type.name)
            if v:
                self.e(v.format(val=f"inputs.{p.name}", name=p.name))
        self.e()
        self.e("const results: Record<string, unknown> = {};")
        self.e("const rollbackStack: Array<() => Promise<void>> = [];")
        self.e()

        # Budget wrapper
        if latency_ms:
            self.e(f"const __timeout = new Promise<never>((_, rej) =>")
            self.i()
            self.e(f"setTimeout(() => rej(new AxonFaultError('budget_exceeded', {{ ms: {latency_ms} }})), {latency_ms})")
            self.d(); self.e(");")
            self.e(f"return Promise.race([__timeout, __run()]);")
            self.e(); self.e(f"async function __run(): Promise<{ret_type}> {{"); self.i()

        waves = topo_waves(build_deps(graph.nodes))
        node_map = {n.name: n for n in graph.nodes}

        self.e("try {"); self.i()

        for wave in waves:
            if len(wave) == 1:
                self._node(node_map[wave[0]], types, graph.rollback_nodes)
            else:
                self._parallel([ node_map[n] for n in wave ], types, graph.rollback_nodes)

        self.e(f"return results.{graph.return_node} as {ret_type};")
        self.d()

        self.e("} catch (err) {"); self.i()
        if graph.rollback_nodes:
            self.e("for (const undo of [...rollbackStack].reverse()) {")
            self.i()
            self.e("try { await undo(); }")
            self.e("catch (e) { console.error('[AXON rollback]', e); }")
            self.d(); self.e("}")
        self.e("throw err;")
        self.d(); self.e("}")

        if latency_ms:
            self.d(); self.e("}")  # end __run

        self.d(); self.e("}")
        self.e()

    def _parallel(self, nodes: List[Node], types: Dict[str, str], rollback_nodes: List[str]):
        names = [n.name for n in nodes]
        self.e(f"// ── Parallel: [{', '.join(names)}] ──────────────────────────")
        vars_ = ", ".join(f"__{n}_r" for n in names)
        self.e(f"const [{vars_}] = await Promise.all(["); self.i()
        for node in nodes:
            code = op_to_ts(node.op, node.name, types)
            # Remove await if it's there, Promise.all handles the promises
            if code.startswith("await "):
                code = code[6:]
            if node.if_cond:
                cond = condition_to_ts(node.if_cond, types)
                self.e(f"({cond}) ? {code} : Promise.resolve(null),  // {node.name}")
            else:
                self.e(f"{code},  // {node.name}")
        self.d(); self.e("]);")
        for node in nodes:
            if node.out:
                ts_t = ts_type(node.out.type)
                self.e(f"const {node.name}_result: {ts_t} = __{node.name}_r as {ts_t};")
                self.e(f"results.{node.name} = {node.name}_result;")
                for fault in node.faults:
                    self._fault_check(node.name, ts_t, fault, types)
                if node.inverse and node.name in rollback_nodes:
                    inv = op_to_ts(node.inverse, node.name, types)
                    self.e(f"rollbackStack.push(async () => {{ {inv}; }});")
        self.e()

    def _node(self, node: Node, types: Dict[str, str], rollback_nodes: List[str]):
        bar = "─" * max(1, 46 - len(node.name))
        self.e(f"// ── NODE {node.name} {bar}")

        if node.if_cond:
            self.e(f"if ({condition_to_ts(node.if_cond, types)}) {{")
            self.i()

        if node.is_async:
            code = op_to_ts(node.op, node.name, types)
            self.e(f"void (async () => {{ try {{ {code}; }} catch(e) {{ console.error('[AXON async {node.name}]', e); }} }})();")
            if node.if_cond:
                self.d(); self.e("}")
            self.e(); return

        code = op_to_ts(node.op, node.name, types)

        if node.out:
            ts_t = ts_type(node.out.type)
            self.e(f"const {node.name}_raw: unknown = {code};")
            for fault in node.faults:
                self._fault_check(node.name, ts_t, fault, types, raw=True)
            self.e(f"const {node.name}_result: {ts_t} = {node.name}_raw as {ts_t};")
            self.e(f"results.{node.name} = {node.name}_result;")
            if node.inverse and node.name in rollback_nodes:
                inv = op_to_ts(node.inverse, node.name, {**types, node.name: ts_t})
                self.e(f"rollbackStack.push(async () => {{ {inv}; }});")
        else:
            self.e(f"{code};")
            for fault in node.faults:
                if fault.condition:
                    cond = condition_to_ts(fault.condition, types)
                    self.e(f"if ({cond}) {{"); self.i()
                    self._fault_action(fault.action); self.d(); self.e("}")
            # Register inverse for side-effect nodes (db.write without OUT)
            if node.inverse and node.name in rollback_nodes:
                inv = op_to_ts(node.inverse, node.name, types)
                self.e(f"rollbackStack.push(async () => {{ {inv}; }});")

        if node.if_cond:
            self.d(); self.e("}")

        self.e()

    def _fault_check(self, node_name: str, ts_t: str, fault: FaultClause,
                     types: Dict[str, str], raw: bool = False):
        ref_name = f"{node_name}_raw" if raw else f"{node_name}_result"
        if fault.condition:
            cond = condition_to_ts(fault.condition, types)
            cond = cond.replace(f"(results.{node_name} as {ts_t})", ref_name)
            self.e(f"if ({cond}) {{")
        else:
            self.e(f"if ({ref_name} === null || {ref_name} === undefined) {{")
        self.i(); self._fault_action(fault.action); self.d(); self.e("}")

    def _fault_action(self, action: FaultAction):
        if action.kind == "HALT":
            self.e(f'throw new AxonFaultError("{action.argument}");')
        elif action.kind == "RETRY":
            self.e(f'throw new AxonFaultError("retry_exhausted", {{ max: {action.argument} }});')
        elif action.kind == "FALLBACK":
            self.e(f'throw new AxonFaultError("fallback", {{ target: "{action.argument}" }});')
