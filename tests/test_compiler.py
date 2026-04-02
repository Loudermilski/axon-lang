"""
AXON Compiler Test Suite
Run: pytest tests/test_compiler.py -v
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.lexer import Lexer, TokenType
from src.parser import Parser
from src.codegen import TypeScriptGenerator, CompileError, validate_graph
from src.codegen_python import PythonGenerator
from src.ast_nodes import *


def compile_axon(source: str) -> str:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    return TypeScriptGenerator().generate(program)


def compile_axon_py(source: str) -> str:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    return PythonGenerator().generate(program)


# ─── Lexer Tests ──────────────────────────────────────────────────────────────

class TestLexer:
    def test_keywords_recognized(self):
        src = "GRAPH NODE IN OUT RETURN ROLLBACK ON FAULT"
        tokens = Lexer(src).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.GRAPH in types
        assert TokenType.NODE in types
        assert TokenType.RETURN in types

    def test_compound_keywords(self):
        src = "db.read db.write db.delete email.send http.post"
        tokens = Lexer(src).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.DB_READ in types
        assert TokenType.DB_WRITE in types
        assert TokenType.EMAIL_SEND in types
        assert TokenType.HTTP_POST in types

    def test_duration_token(self):
        src = "BUDGET latency=500ms"
        tokens = Lexer(src).tokenize()
        dur = [t for t in tokens if t.type == TokenType.DURATION]
        assert len(dur) == 1
        assert dur[0].value == "500ms"

    def test_arrow_token(self):
        src = "FAULT -> HALT[not_found]"
        tokens = Lexer(src).tokenize()
        arrows = [t for t in tokens if t.type == TokenType.ARROW]
        assert len(arrows) == 1

    def test_string_literal(self):
        src = 'status: "pending"'
        tokens = Lexer(src).tokenize()
        strings = [t for t in tokens if t.type == TokenType.STRING]
        assert strings[0].value == "pending"

    def test_comments_skipped(self):
        src = "-- this is a comment\nGRAPH foo"
        tokens = Lexer(src).tokenize()
        types = [t.type for t in tokens if t.type not in (TokenType.EOF, TokenType.NEWLINE)]
        assert TokenType.GRAPH in types
        # Comment content should not appear
        values = [t.value for t in tokens]
        assert "comment" not in values


# ─── Parser Tests ─────────────────────────────────────────────────────────────

MINIMAL_GRAPH = """
GRAPH test_graph
  IN    userId<user_id>
  OUT   result<string>

  NODE fetch
    OP      db.read users WHERE id == IN.userId
    OUT     result<string>
    FAULT   fetch == null -> HALT[not_found]

  RETURN fetch
"""

class TestParser:
    def test_parses_graph_name(self):
        tokens = Lexer(MINIMAL_GRAPH).tokenize()
        program = Parser(tokens).parse_program()
        assert len(program.graphs) == 1
        assert program.graphs[0].name == "test_graph"

    def test_parses_inputs(self):
        tokens = Lexer(MINIMAL_GRAPH).tokenize()
        program = Parser(tokens).parse_program()
        graph = program.graphs[0]
        assert len(graph.inputs) == 1
        assert graph.inputs[0].name == "userId"
        assert graph.inputs[0].type.name == "user_id"

    def test_parses_nodes(self):
        tokens = Lexer(MINIMAL_GRAPH).tokenize()
        program = Parser(tokens).parse_program()
        graph = program.graphs[0]
        assert len(graph.nodes) == 1
        assert graph.nodes[0].name == "fetch"

    def test_return_node(self):
        tokens = Lexer(MINIMAL_GRAPH).tokenize()
        program = Parser(tokens).parse_program()
        assert program.graphs[0].return_node == "fetch"

    def test_fault_clause_parsed(self):
        tokens = Lexer(MINIMAL_GRAPH).tokenize()
        program = Parser(tokens).parse_program()
        node = program.graphs[0].nodes[0]
        assert len(node.faults) == 1
        assert node.faults[0].action.kind == "HALT"
        assert node.faults[0].action.argument == "not_found"

    def test_db_read_operation(self):
        tokens = Lexer(MINIMAL_GRAPH).tokenize()
        program = Parser(tokens).parse_program()
        node = program.graphs[0].nodes[0]
        assert isinstance(node.op, DbReadOp)
        assert node.op.table == "users"

    def test_budget_parsed(self):
        src = MINIMAL_GRAPH.replace("OUT   result<string>", "OUT   result<string>\n  BUDGET latency=500ms")
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        graph = program.graphs[0]
        assert len(graph.budget) == 1
        assert graph.budget[0].key == "latency"
        assert graph.budget[0].value == "500ms"

    def test_async_node(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE fetch OP db.read t WHERE id == IN.x OUT r<string>
  NODE notif OP email.send TO=fetch.email TEMPLATE=tmpl ASYNC true AFTER fetch
  RETURN fetch
"""
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        notif = next(n for n in program.graphs[0].nodes if n.name == "notif")
        assert notif.is_async is True

    def test_after_clause(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE a OP db.read t WHERE id == IN.x OUT r<string>
  NODE b OP db.read t WHERE id == IN.x OUT r<string> AFTER a
  RETURN b
"""
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        b = next(n for n in program.graphs[0].nodes if n.name == "b")
        assert "a" in b.after


# ─── Compiler Validation Tests ────────────────────────────────────────────────

class TestValidation:
    def test_missing_inverse_raises(self):
        src = """
GRAPH g IN x<string> OUT r<order_record>
  NODE create OP db.write orders {userId: IN.x}
    OUT r<order_record>
  RETURN create
"""
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        with pytest.raises(CompileError, match="INVERSE"):
            validate_graph(program.graphs[0])

    def test_bad_return_raises(self):
        src = MINIMAL_GRAPH.replace("RETURN fetch", "RETURN nonexistent")
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        with pytest.raises(CompileError, match="nonexistent"):
            validate_graph(program.graphs[0])

    def test_bad_after_raises(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE a OP db.read t WHERE id == IN.x OUT r<string> AFTER ghost
  RETURN a
"""
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        with pytest.raises(CompileError, match="ghost"):
            validate_graph(program.graphs[0])


# ─── Code Generation Tests ────────────────────────────────────────────────────

class TestCodeGen:
    def test_function_exported(self):
        out = compile_axon(MINIMAL_GRAPH)
        assert "export async function test_graph" in out

    def test_semantic_validator_emitted(self):
        out = compile_axon(MINIMAL_GRAPH)
        assert "Invalid user_id" in out

    def test_query_object_not_boolean(self):
        out = compile_axon(MINIMAL_GRAPH)
        # WHERE clause should produce { id: inputs.userId }, not id === inputs.userId
        assert "{ id: inputs.userId }" in out
        assert "id === inputs.userId" not in out

    def test_rollback_stack_present(self):
        src = """
GRAPH g IN x<string> OUT r<order_record>
  NODE create OP db.write orders {userId: IN.x}
    OUT r<order_record>
    INVERSE db.delete orders WHERE id == create.id
  RETURN create
  ROLLBACK ON FAULT [create]
"""
        out = compile_axon(src)
        assert "rollbackStack" in out
        assert "rollbackStack.push" in out

    def test_budget_timeout_emitted(self):
        src = MINIMAL_GRAPH.replace(
            "OUT   result<string>",
            "OUT   result<string>\n  BUDGET latency=300ms"
        )
        out = compile_axon(src)
        assert "Promise.race" in out
        assert "budget_exceeded" in out
        assert "300" in out

    def test_parallel_wave_emitted(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE a OP db.read ta WHERE id == IN.x OUT r<string>
  NODE b OP db.read tb WHERE id == IN.x OUT r<string>
  NODE c OP db.read tc WHERE id == IN.x OUT r<string> AFTER a, b
  RETURN c
"""
        out = compile_axon(src)
        assert "Promise.all" in out
        assert "Parallel" in out

    def test_async_node_fire_and_forget(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE fetch OP db.read t WHERE id == IN.x OUT r<string>
  NODE notif OP email.send TO=fetch.email TEMPLATE=tmpl ASYNC true AFTER fetch
  RETURN fetch
"""
        out = compile_axon(src)
        assert "void (async () =>" in out

    def test_compute_sum_correct(self):
        src = """
GRAPH g IN items<cart_item[]> OUT total<dollar_amount>
  NODE calc OP SUM items[].price * items[].quantity OUT total<dollar_amount>
  RETURN calc
"""
        out = compile_axon(src)
        assert "inputs.items.reduce" in out
        assert "i.price * i.quantity" in out

    def test_full_order_processor_compiles(self):
        src = open(os.path.join(os.path.dirname(__file__), 'order_processor.axon')).read()
        out = compile_axon(src)
        assert "export async function process_order" in out
        assert "Promise.all" in out      # parallelism
        assert "rollbackStack" in out    # rollback
        assert "Promise.race" in out     # budget
        assert "{ id: inputs.userId }" in out  # WHERE fix

    def test_full_auth_flow_compiles(self):
        src = open(os.path.join(os.path.dirname(__file__), 'auth_flow.axon')).read()
        out = compile_axon(src)
        assert "export async function authenticate_user" in out
        assert "Invalid email_address" in out   # semantic validation
        assert "Promise.race" in out             # budget


# ─── MCP Tests ───────────────────────────────────────────────────────────────

class TestMcp:
    def test_mcp_token_lexed(self):
        src = "mcp.brave.web_search"
        tokens = Lexer(src).tokenize()
        mcp_tokens = [t for t in tokens if t.type == TokenType.MCP]
        assert len(mcp_tokens) == 1
        assert mcp_tokens[0].value == "mcp.brave.web_search"

    def test_mcp_op_parsed(self):
        src = """
GRAPH g IN q<string> OUT r<string>
  NODE search
    OP      mcp.brave.web_search({query: IN.q})
    OUT     r<string>
  RETURN search
"""
        tokens = Lexer(src).tokenize()
        program = Parser(tokens).parse_program()
        node = program.graphs[0].nodes[0]
        assert isinstance(node.op, McpOp)
        assert node.op.server == "brave"
        assert node.op.tool == "web_search"
        assert "query" in node.op.args.pairs

    def test_mcp_ts_codegen(self):
        src = """
GRAPH g IN q<string> OUT r<string>
  NODE search
    OP      mcp.brave.web_search({query: IN.q})
    OUT     r<string>
  RETURN search
"""
        out = compile_axon(src)
        assert "await mcp.brave.web_search" in out
        assert "inputs.q" in out

    def test_mcp_py_codegen(self):
        src = """
GRAPH g IN q<string> OUT r<string>
  NODE search
    OP      mcp.brave.web_search({query: IN.q})
    OUT     r<string>
  RETURN search
"""
        out = compile_axon_py(src)
        assert "await mcp['brave']['web_search']" in out
        assert "inputs.get('q')" in out

    def test_full_mcp_workflow_compiles(self):
        src = open(os.path.join(os.path.dirname(__file__), 'mcp_workflow.axon')).read()
        out_ts = compile_axon(src)
        assert "await mcp.brave.web_search" in out_ts
        assert "await mcp.claude.summarize" in out_ts
        out_py = compile_axon_py(src)
        assert "mcp['brave']['web_search']" in out_py
        assert "mcp['claude']['summarize']" in out_py

    def test_mcp_no_args(self):
        src = """
GRAPH g IN q<string> OUT r<string>
  NODE ping
    OP      mcp.health.check()
    OUT     r<string>
  RETURN ping
"""
        out = compile_axon(src)
        assert "mcp.health.check({})" in out


# ─── Python Target Tests ─────────────────────────────────────────────────────

class TestPythonCodeGen:
    def test_function_emitted(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE fetch OP db.read t WHERE id == IN.x OUT r<string>
  RETURN fetch
"""
        out = compile_axon_py(src)
        assert "async def g(" in out

    def test_semantic_validator_emitted(self):
        src = """
GRAPH g IN userId<user_id> OUT r<string>
  NODE fetch OP db.read t WHERE id == IN.userId OUT r<string>
  RETURN fetch
"""
        out = compile_axon_py(src)
        assert "Invalid user_id" in out

    def test_parallel_uses_gather(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  NODE a OP db.read ta WHERE id == IN.x OUT r<string>
  NODE b OP db.read tb WHERE id == IN.x OUT r<string>
  NODE c OP db.read tc WHERE id == IN.x OUT r<string> AFTER a, b
  RETURN c
"""
        out = compile_axon_py(src)
        assert "asyncio.gather" in out

    def test_budget_uses_wait_for(self):
        src = """
GRAPH g IN x<string> OUT r<string>
  BUDGET latency=300ms
  NODE fetch OP db.read t WHERE id == IN.x OUT r<string>
  RETURN fetch
"""
        out = compile_axon_py(src)
        assert "asyncio.wait_for" in out
        assert "0.3" in out

    def test_rollback_emitted(self):
        src = """
GRAPH g IN x<string> OUT r<order_record>
  NODE create OP db.write orders {userId: IN.x}
    OUT r<order_record>
    INVERSE db.delete orders WHERE id == create.id
  RETURN create
  ROLLBACK ON FAULT [create]
"""
        out = compile_axon_py(src)
        assert "rollback_stack" in out
        assert "__rollback_create" in out

    def test_full_order_processor_compiles_py(self):
        src = open(os.path.join(os.path.dirname(__file__), 'order_processor.axon')).read()
        out = compile_axon_py(src)
        assert "async def process_order" in out
        assert "asyncio.gather" in out
        assert "rollback_stack" in out

    def test_full_auth_flow_compiles_py(self):
        src = open(os.path.join(os.path.dirname(__file__), 'auth_flow.axon')).read()
        out = compile_axon_py(src)
        assert "async def authenticate_user" in out
        assert "Invalid email_address" in out

    def test_python_output_is_valid_syntax(self):
        import ast as pyast
        for fname in ['order_processor.axon', 'auth_flow.axon', 'mcp_workflow.axon']:
            src = open(os.path.join(os.path.dirname(__file__), fname)).read()
            out = compile_axon_py(src)
            pyast.parse(out)  # raises SyntaxError if invalid


# ─── Token Count Benchmark ────────────────────────────────────────────────────

class TestEfficiency:
    def test_axon_is_smaller_than_output(self):
        """AXON source should be significantly smaller than generated TypeScript."""
        src = open(os.path.join(os.path.dirname(__file__), 'order_processor.axon')).read()
        out = compile_axon(src)
        axon_chars = len(src)
        ts_chars = len(out)
        # TS output will be larger (it's expanded) but AXON expresses the same logic
        # The key metric: AXON lines vs manually-written equivalent TS lines
        axon_lines = len([l for l in src.split('\n') if l.strip() and not l.strip().startswith('--')])
        ts_lines = len([l for l in out.split('\n') if l.strip() and not l.strip().startswith('//')])
        print(f"\n  AXON source: {axon_lines} logic lines")
        print(f"  Generated TS: {ts_lines} logic lines")
        print(f"  Expansion ratio: {ts_lines/axon_lines:.1f}x")
        # This is expected — AXON is the compressed form, TS is the expanded safe form
        assert axon_lines < ts_lines  # TS is always more verbose
