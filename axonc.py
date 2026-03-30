"""
AXON Compiler — Main Entry Point
Usage: python axonc.py <input.axon> [--out <output.ts>]
"""

import sys
import os
import argparse

# Add project root to path for package imports
sys.path.insert(0, os.path.dirname(__file__))

from src.lexer import Lexer
from src.parser import Parser
from src.codegen import TypeScriptGenerator
from src.codegen_python import PythonGenerator

TARGET_EXT = {"ts": ".ts", "py": ".py"}
TARGET_GEN = {"ts": TypeScriptGenerator, "py": PythonGenerator}


def compile_axon(source: str, target: str = "ts", source_name: str = "<stdin>") -> str:
    print(f"[axonc] Lexing {source_name}...")
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    print(f"[axonc] {len(tokens)} tokens")

    print(f"[axonc] Parsing...")
    parser = Parser(tokens)
    program = parser.parse_program()
    print(f"[axonc] {len(program.graphs)} graph(s) parsed")

    label = "TypeScript" if target == "ts" else "Python"
    print(f"[axonc] Generating {label}...")
    gen = TARGET_GEN[target]()
    output = gen.generate(program)
    print(f"[axonc] Done — {len(output.splitlines())} lines emitted")

    return output


def main():
    ap = argparse.ArgumentParser(description="AXON Compiler v0.2")
    ap.add_argument("input", help="AXON source file (.axon)")
    ap.add_argument("--out", help="Output file (default: <input>.<ext>)")
    ap.add_argument("--target", choices=["ts", "py"], default="ts",
                    help="Compile target: ts (TypeScript) or py (Python)")
    args = ap.parse_args()

    with open(args.input, "r") as f:
        source = f.read()

    output = compile_axon(source, target=args.target, source_name=args.input)

    out_path = args.out or args.input.replace(".axon", TARGET_EXT[args.target])
    with open(out_path, "w") as f:
        f.write(output)

    print(f"[axonc] Written to {out_path}")


if __name__ == "__main__":
    main()
