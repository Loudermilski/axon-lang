"""
AXON Compiler — Main Entry Point
Usage: python axonc.py <input.axon> [--out <output.ts>]
"""

import sys
import os
import argparse

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.lexer import Lexer
from src.parser import Parser
from src.codegen import TypeScriptGenerator


def compile_axon(source: str, source_name: str = "<stdin>") -> str:
    print(f"[axonc] Lexing {source_name}...")
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    print(f"[axonc] {len(tokens)} tokens")

    print(f"[axonc] Parsing...")
    parser = Parser(tokens)
    program = parser.parse_program()
    print(f"[axonc] {len(program.graphs)} graph(s) parsed")

    print(f"[axonc] Generating TypeScript...")
    gen = TypeScriptGenerator()
    output = gen.generate(program)
    print(f"[axonc] Done — {len(output.splitlines())} lines emitted")

    return output


def main():
    ap = argparse.ArgumentParser(description="AXON Compiler v0.1")
    ap.add_argument("input", help="AXON source file (.axon)")
    ap.add_argument("--out", help="Output TypeScript file (default: <input>.ts)")
    args = ap.parse_args()

    with open(args.input, "r") as f:
        source = f.read()

    output = compile_axon(source, args.input)

    out_path = args.out or args.input.replace(".axon", ".ts")
    with open(out_path, "w") as f:
        f.write(output)

    print(f"[axonc] Written to {out_path}")


if __name__ == "__main__":
    main()
