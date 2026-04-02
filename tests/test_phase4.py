"""
Tests for Phase 4 AXON features: FOR EACH and MATCH.
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.lexer import Lexer, TokenType
from src.parser import Parser
from src.codegen import TypeScriptGenerator
from src.codegen_python import PythonGenerator
from src.ast_nodes import *

def compile_ts(source: str) -> str:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    return TypeScriptGenerator().generate(program)

def compile_py(source: str) -> str:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    return PythonGenerator().generate(program)

PHASE4_AXON = """
GRAPH phase4_test
  IN    items<string[]>, mode<string>
  OUT   results<string[]>

  NODE loop
    OP FOR EACH item IN IN.items DO
         MATCH IN.mode {
           "upper" -> mcp.text.upper({val: item})
           "lower" -> mcp.text.lower({val: item})
         }
    OUT processed<string[]>

  RETURN loop
"""

def test_for_each_parsing():
    tokens = Lexer(PHASE4_AXON).tokenize()
    program = Parser(tokens).parse_program()
    node = program.graphs[0].nodes[0]
    assert isinstance(node.op, ForEachOp)
    assert node.op.iterator == "item"
    assert isinstance(node.op.operation, MatchOp)

def test_match_parsing():
    tokens = Lexer(PHASE4_AXON).tokenize()
    program = Parser(tokens).parse_program()
    fe_op = program.graphs[0].nodes[0].op
    match_op = fe_op.operation
    assert isinstance(match_op, MatchOp)
    assert len(match_op.arms) == 2
    assert match_op.arms[0][0] == "upper"

def test_ts_codegen_phase4():
    out = compile_ts(PHASE4_AXON)
    assert ".map(" in out
    assert "inputs.mode === \"upper\"" in out
    assert "await Promise.all" in out

def test_py_codegen_phase4():
    out = compile_py(PHASE4_AXON)
    assert "asyncio.gather" in out
    assert "inputs.get('mode') == \"upper\"" in out
