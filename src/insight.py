"""
AXON Compiler - Insight Engine
Analyzes AXON programs for structural efficiency and safety.
"""

from .ast_nodes import Program, Graph, Node, DbWriteOp
from .codegen import build_deps, topo_waves

def analyze_program(program: Program) -> str:
    report = ["AXON INSIGHT REPORT", "===================", ""]

    total_nodes = 0
    total_waves = 0
    unsafe_writes = 0

    for graph in program.graphs:
        nodes = graph.nodes
        total_nodes += len(nodes)

        deps = build_deps(nodes)
        waves = topo_waves(deps)
        total_waves += len(waves)

        parallelism = (len(nodes) / len(waves)) if waves else 1.0

        # Safety audit
        fault_coverage = len([n for n in nodes if n.faults]) / len(nodes) if nodes else 1.0

        report.append(f"GRAPH: {graph.name}")
        report.append(f"  - Complexity: {len(nodes)} nodes")
        report.append(f"  - Concurrency Waves: {len(waves)}")
        report.append(f"  - Parallelism Score: {parallelism:.2f}x")
        report.append(f"  - Fault Coverage: {fault_coverage*100:.1f}%")

        for node in nodes:
            if isinstance(node.op, DbWriteOp) and not node.inverse:
                report.append(f"  [!] WARNING: NODE '{node.name}' has db.write without INVERSE")
                unsafe_writes += 1

        report.append("")

    report.append("SUMMARY")
    report.append(f"  Total Graphs: {len(program.graphs)}")
    report.append(f"  Avg Parallelism: {(total_nodes / total_waves if total_waves else 0):.2f}x")
    report.append(f"  Safety Issues: {unsafe_writes}")

    return "\n".join(report)
