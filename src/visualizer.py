"""
AXON Compiler - Graph Visualizer
Generates Mermaid diagram definitions from AXON AST.
"""

from .ast_nodes import Program, Graph, Node, DbWriteOp, DbReadOp, DbDeleteOp, McpOp, HumanOp, CallOp

def generate_mermaid(program: Program) -> str:
    lines = ["flowchart TD"]

    for graph in program.graphs:
        lines.append(f"  subgraph {graph.name}")

        # Inputs
        for inp in graph.inputs:
            lines.append(f"    IN_{inp.name}[/IN: {inp.name}<{inp.type}>/]")

        # Nodes
        for node in graph.nodes:
            label = _get_node_label(node)
            shape = _get_node_shape(node)
            lines.append(f"    {node.name}{shape[0]}{label}{shape[1]}")

            # Connections from AFTER
            for dep in node.after:
                lines.append(f"    {dep} --> {node.name}")

            # Connections from Inputs if used in OP (basic heuristic)
            # This could be more sophisticated by scanning Ref in node.op

        # Return
        lines.append(f"    {graph.return_node} --> OUT_{graph.name}[/OUT: {graph.output.name}/]")

        lines.append("  end")

    return "\n".join(lines)

def _get_node_label(node: Node) -> str:
    op_type = type(node.op).__name__.replace('Op', '')
    label = f"<b>{node.name}</b><br/>{op_type}"
    if node.if_cond:
        label = f"IF {str(node.if_cond)}<br/>" + label
    return f'"{label}"'

def _get_node_shape(node: Node) -> tuple[str, str]:
    if isinstance(node.op, (DbWriteOp, DbReadOp, DbDeleteOp)):
        return "[", "]" # Rect
    if isinstance(node.op, McpOp):
        return "{{", "}}" # Hexagon
    if isinstance(node.op, HumanOp):
        return "([", "])" # Stadium
    if isinstance(node.op, CallOp):
        return "[[", "]]" # Subroutine
    return "(", ")" # Round
