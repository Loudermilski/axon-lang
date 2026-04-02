"""
Tests for new AXON features: Custom Types, IF clause, Human Ops, CALL op, and Visualization.
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.lexer import Lexer, TokenType
from src.parser import Parser
from src.codegen import TypeScriptGenerator, CompileError
from src.codegen_python import PythonGenerator
from src.visualizer import generate_mermaid
from src.ast_nodes import *

def compile_ts(source: str) -> str:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    return TypeScriptGenerator().generate(program)

def compile_py(source: str) -> str:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    return PythonGenerator().generate(program)

NEW_FEATURES_AXON = """
TYPES {
  Address {
    street<string>,
    city<string>,
    zip<integer>
  }
}

GRAPH sub_graph
  IN    val<integer>
  OUT   res<integer>
  NODE double OP SUM IN.val * 2 OUT res<integer>
  RETURN double

GRAPH main_graph
  IN    email<email_address>, age<integer>
  OUT   status<string>

  NODE check_age
    IF IN.age < 18
    OP db.read restrictions WHERE type == "minor"
    OUT restricted<boolean>

  NODE ask_human
    IF IN.age >= 18
    OP human.approve("Is this user allowed?")
    OUT allowed<boolean>

  NODE call_sub
    OP CALL sub_graph({val: IN.age})
    OUT sub_res<integer>

  NODE get_input
    OP human.input("Please enter your name")
    OUT name<string>

  RETURN ask_human
"""

def test_custom_types_parsing():
    tokens = Lexer(NEW_FEATURES_AXON).tokenize()
    program = Parser(tokens).parse_program()
    assert len(program.custom_types) == 1
    ct = program.custom_types[0]
    assert ct.name == "Address"
    assert len(ct.fields) == 3
    assert ct.fields[0].name == "street"

def test_if_clause_parsing():
    tokens = Lexer(NEW_FEATURES_AXON).tokenize()
    program = Parser(tokens).parse_program()
    main = next(g for g in program.graphs if g.name == "main_graph")
    check_age = next(n for n in main.nodes if n.name == "check_age")
    assert check_age.if_cond is not None
    assert check_age.if_cond.left.parts == ["IN", "age"]

def test_human_op_parsing():
    tokens = Lexer(NEW_FEATURES_AXON).tokenize()
    program = Parser(tokens).parse_program()
    main = next(g for g in program.graphs if g.name == "main_graph")
    ask_human = next(n for n in main.nodes if n.name == "ask_human")
    assert isinstance(ask_human.op, HumanOp)
    assert ask_human.op.kind == "approve"
    assert "Is this user allowed?" in ask_human.op.prompt

def test_call_op_parsing():
    tokens = Lexer(NEW_FEATURES_AXON).tokenize()
    program = Parser(tokens).parse_program()
    main = next(g for g in program.graphs if g.name == "main_graph")
    call_sub = next(n for n in main.nodes if n.name == "call_sub")
    assert isinstance(call_sub.op, CallOp)
    assert call_sub.op.graph_name == "sub_graph"

def test_ts_codegen_new_features():
    out = compile_ts(NEW_FEATURES_AXON)
    assert "class Address" in out
    assert "(inputs.age < 18)" in out
    assert "human.approve" in out
    assert "sub_graph({ val: inputs.age })" in out
    assert "human.input" in out

def test_py_codegen_new_features():
    out = compile_py(NEW_FEATURES_AXON)
    assert "class Address:" in out
    assert "inputs.get('age') >= 18" in out
    assert "await human.approve" in out
    assert "await sub_graph({'val': inputs.get('age')})" in out
    assert "await human.input" in out

def test_visualization():
    tokens = Lexer(NEW_FEATURES_AXON).tokenize()
    program = Parser(tokens).parse_program()
    viz = generate_mermaid(program)
    assert "flowchart TD" in viz
    assert "subgraph main_graph" in viz
    assert "ask_human" in viz
    assert "check_age" in viz
    assert "([\"" in viz # HumanOp shape heuristic
