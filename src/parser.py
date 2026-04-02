"""
AXON Compiler - Parser
Converts a token stream into an AST.
"""

from typing import List, Optional, Any
from .lexer import Token, TokenType
from .ast_nodes import *


class ParseError(Exception):
    def __init__(self, msg, token: Token):
        super().__init__(f"ParseError at L{token.line}:C{token.col} — {msg} (got {token.type.name} {token.value!r})")
        self.token = token


class Parser:
    def __init__(self, tokens: List[Token]):
        # Strip newlines for easier parsing — we use keywords as delimiters
        self.tokens = [t for t in tokens if t.type != TokenType.NEWLINE]
        self.pos = 0

    def peek(self, offset=0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def check(self, *types: TokenType) -> bool:
        return self.peek().type in types

    def expect(self, *types: TokenType) -> Token:
        if self.peek().type not in types:
            raise ParseError(
                f"Expected {' or '.join(t.name for t in types)}",
                self.peek()
            )
        return self.advance()

    def match(self, *types: TokenType) -> Optional[Token]:
        if self.peek().type in types:
            return self.advance()
        return None

    # -------------------------------------------------------------------------
    # Top Level
    # -------------------------------------------------------------------------

    def parse_program(self) -> Program:
        custom_types = []
        if self.match(TokenType.TYPES):
            self.expect(TokenType.LBRACE)
            while not self.check(TokenType.RBRACE, TokenType.EOF):
                custom_types.append(self.parse_custom_type())
            self.expect(TokenType.RBRACE)

        actors = []
        while self.match(TokenType.ACTOR):
            actors.append(self.parse_actor())

        graphs = []
        while not self.check(TokenType.EOF):
            graphs.append(self.parse_graph())
        return Program(custom_types=custom_types, actors=actors, graphs=graphs)

    def parse_actor(self) -> Actor:
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LBRACE)
        self.expect(TokenType.STATE)
        self.expect(TokenType.LBRACE)
        state = self.parse_param_list()
        self.expect(TokenType.RBRACE)

        graphs = []
        while self.check(TokenType.GRAPH):
            graphs.append(self.parse_graph())

        self.expect(TokenType.RBRACE)
        return Actor(name=name, state=state, graphs=graphs)

    def parse_custom_type(self) -> CustomType:
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LBRACE)
        fields = self.parse_param_list()
        self.expect(TokenType.RBRACE)
        return CustomType(name=name, fields=fields)

    def parse_graph(self) -> Graph:
        self.expect(TokenType.GRAPH)
        name = self.expect(TokenType.IDENTIFIER).value

        self.expect(TokenType.IN)
        inputs = self.parse_param_list()

        self.expect(TokenType.OUT)
        output = self.parse_typed_param()

        budget = []
        if self.match(TokenType.BUDGET):
            budget = self.parse_budget_list()

        nodes = []
        while self.check(TokenType.NODE):
            nodes.append(self.parse_node())

        self.expect(TokenType.RETURN)
        return_ref = self.parse_return_ref()

        rollback_nodes = []
        if self.match(TokenType.ROLLBACK):
            self.expect(TokenType.ON)
            self.expect(TokenType.FAULT)
            self.expect(TokenType.LBRACKET)
            rollback_nodes = self.parse_identifier_list()
            self.expect(TokenType.RBRACKET)

        return Graph(
            name=name,
            inputs=inputs,
            output=output,
            budget=budget,
            nodes=nodes,
            return_node=return_ref,
            rollback_nodes=rollback_nodes,
        )

    def parse_return_ref(self) -> str:
        """Parse RETURN node_name or RETURN node_name.OUT"""
        name = self.expect(TokenType.IDENTIFIER).value
        if self.match(TokenType.DOT):
            self.expect(TokenType.OUT)
        return name

    # -------------------------------------------------------------------------
    # Params & Types
    # -------------------------------------------------------------------------

    def parse_param_list(self) -> List[TypedParam]:
        params = [self.parse_typed_param()]
        while self.match(TokenType.COMMA):
            params.append(self.parse_typed_param())
        return params

    def parse_typed_param(self) -> TypedParam:
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LT)
        sem_type = self.parse_semantic_type()
        self.expect(TokenType.GT)
        return TypedParam(name=name, type=sem_type)

    def parse_semantic_type(self) -> SemanticType:
        # Type name may have underscores: user_id, dollar_amount
        parts = [self.expect(TokenType.IDENTIFIER).value]
        while self.check(TokenType.IDENTIFIER) or (
            self.peek().type == TokenType.IDENTIFIER
        ):
            # peek for underscore-joined names already handled by lexer
            break

        type_name = parts[0]
        is_collection = False
        if self.match(TokenType.LBRACKET):
            self.expect(TokenType.RBRACKET)
            is_collection = True
        return SemanticType(name=type_name, is_collection=is_collection)

    # -------------------------------------------------------------------------
    # Budget
    # -------------------------------------------------------------------------

    def parse_budget_list(self) -> List[BudgetConstraint]:
        constraints = [self.parse_budget_constraint()]
        while self.match(TokenType.COMMA):
            constraints.append(self.parse_budget_constraint())
        return constraints

    def parse_budget_constraint(self) -> BudgetConstraint:
        key = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.EQUALS)
        if self.check(TokenType.DURATION):
            value = self.advance().value
        elif self.check(TokenType.INTEGER):
            value = self.advance().value
        else:
            value = self.expect(TokenType.IDENTIFIER).value
        return BudgetConstraint(key=key, value=value)

    # -------------------------------------------------------------------------
    # Nodes
    # -------------------------------------------------------------------------

    def parse_node(self) -> Node:
        self.expect(TokenType.NODE)
        name = self.expect(TokenType.IDENTIFIER).value

        if_cond = None
        if self.match(TokenType.IF):
            if_cond = self.parse_condition()

        self.expect(TokenType.OP)
        op = self.parse_operation()

        out = None
        faults = []
        inverse = None
        is_async = False
        after = []

        # Parse optional clauses in any order
        while True:
            if self.match(TokenType.OUT):
                out = self.parse_typed_param()
            elif self.check(TokenType.FAULT):
                self.advance()
                faults.append(self.parse_fault_clause())
            elif self.match(TokenType.INVERSE):
                inverse = self.parse_operation()
            elif self.match(TokenType.ASYNC):
                val = self.expect(TokenType.BOOLEAN).value
                is_async = val == "true"
            elif self.match(TokenType.AFTER):
                after = self.parse_identifier_list_inline()
            else:
                break

        return Node(
            name=name,
            op=op,
            if_cond=if_cond,
            out=out,
            faults=faults,
            inverse=inverse,
            is_async=is_async,
            after=after,
        )

    # -------------------------------------------------------------------------
    # Operations
    # -------------------------------------------------------------------------

    def parse_operation(self) -> Operation:
        tok = self.peek()

        if tok.type == TokenType.DB_READ:
            return self.parse_db_read()
        elif tok.type == TokenType.DB_WRITE:
            return self.parse_db_write()
        elif tok.type == TokenType.DB_DELETE:
            return self.parse_db_delete()
        elif tok.type == TokenType.ASSERT:
            return self.parse_assert()
        elif tok.type in (TokenType.SUM, TokenType.AVG, TokenType.COUNT,
                          TokenType.MAP, TokenType.FILTER):
            return self.parse_compute()
        elif tok.type == TokenType.EMAIL_SEND:
            return self.parse_email()
        elif tok.type in (TokenType.HTTP_GET, TokenType.HTTP_POST,
                          TokenType.HTTP_PUT, TokenType.HTTP_DELETE):
            return self.parse_http()
        elif tok.type == TokenType.MCP:
            return self.parse_mcp()
        elif tok.type in (TokenType.HUMAN_APPROVE, TokenType.HUMAN_INPUT):
            return self.parse_human()
        elif tok.type == TokenType.CALL:
            return self.parse_call()
        elif tok.type == TokenType.FOR:
            return self.parse_for_each()
        elif tok.type == TokenType.WHILE:
            return self.parse_while()
        elif tok.type == TokenType.MATCH:
            return self.parse_match()
        elif tok.type == TokenType.STREAM:
            return self.parse_stream()
        else:
            raise ParseError("Expected an operation keyword", tok)

    def parse_db_read(self) -> DbReadOp:
        self.expect(TokenType.DB_READ)
        table = self.expect(TokenType.IDENTIFIER).value
        condition = None
        if self.match(TokenType.WHERE):
            condition = self.parse_condition()
        return DbReadOp(table=table, condition=condition)

    def parse_db_write(self) -> DbWriteOp:
        self.expect(TokenType.DB_WRITE)
        table = self.expect(TokenType.IDENTIFIER).value
        condition = None
        if self.match(TokenType.WHERE):
            condition = self.parse_condition()
        data = self.parse_json_object()
        return DbWriteOp(table=table, condition=condition, data=data)

    def parse_db_delete(self) -> DbDeleteOp:
        self.expect(TokenType.DB_DELETE)
        table = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.WHERE)
        condition = self.parse_condition()
        return DbDeleteOp(table=table, condition=condition)

    def parse_assert(self) -> AssertOp:
        self.expect(TokenType.ASSERT)
        condition = self.parse_condition()
        return AssertOp(condition=condition)

    def parse_compute(self) -> ComputeOp:
        func = self.advance().value
        # Collect the rest of the expression as raw text until next keyword
        expr_parts = []
        while not self.check(TokenType.OUT, TokenType.FAULT, TokenType.INVERSE,
                              TokenType.ASYNC, TokenType.AFTER, TokenType.NODE,
                              TokenType.RETURN, TokenType.ROLLBACK, TokenType.EOF):
            expr_parts.append(self.advance().value)
        return ComputeOp(function=func, expression=" ".join(expr_parts))

    def parse_email(self) -> EmailOp:
        self.expect(TokenType.EMAIL_SEND)
        # TO=ref
        if self.peek().type == TokenType.TO:
            self.advance()
        else:
            self.expect(TokenType.IDENTIFIER) # TO
        self.expect(TokenType.EQUALS)
        to = self.parse_ref()
        # TEMPLATE=name
        self.expect(TokenType.IDENTIFIER)  # TEMPLATE
        self.expect(TokenType.EQUALS)
        template = self.expect(TokenType.IDENTIFIER).value
        return EmailOp(to=to, template=template)

    def parse_http(self) -> HttpOp:
        method_map = {
            TokenType.HTTP_GET: "GET",
            TokenType.HTTP_POST: "POST",
            TokenType.HTTP_PUT: "PUT",
            TokenType.HTTP_DELETE: "DELETE",
        }
        method = method_map[self.advance().type]
        self.expect(TokenType.IDENTIFIER)  # URL
        self.expect(TokenType.EQUALS)
        if self.check(TokenType.STRING):
            url = self.advance().value
        else:
            url = self.parse_ref()
        return HttpOp(method=method, url=url)

    def parse_mcp(self) -> McpOp:
        tok = self.expect(TokenType.MCP)
        # Token value is "mcp.server.tool"
        parts = tok.value.split(".")
        server = parts[1]
        tool = parts[2]
        args = None
        if self.match(TokenType.LPAREN):
            if not self.check(TokenType.RPAREN):
                args = self.parse_json_object()
            self.expect(TokenType.RPAREN)
        return McpOp(server=server, tool=tool, args=args)

    def parse_human(self) -> HumanOp:
        tok = self.advance()
        kind = "approve" if tok.type == TokenType.HUMAN_APPROVE else "input"
        self.expect(TokenType.LPAREN)
        prompt = self.expect(TokenType.STRING).value
        self.expect(TokenType.RPAREN)
        return HumanOp(kind=kind, prompt=prompt)

    def parse_call(self) -> CallOp:
        self.expect(TokenType.CALL)
        name = self.expect(TokenType.IDENTIFIER).value
        args = None
        if self.match(TokenType.LPAREN):
            if not self.check(TokenType.RPAREN):
                args = self.parse_json_object()
            self.expect(TokenType.RPAREN)
        return CallOp(graph_name=name, args=args)

    def parse_for_each(self) -> ForEachOp:
        self.expect(TokenType.FOR)
        self.expect(TokenType.EACH)
        iterator = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.IN)
        collection = self.parse_ref()
        self.expect(TokenType.DO)
        operation = self.parse_operation()
        return ForEachOp(iterator=iterator, collection=collection, operation=operation)

    def parse_while(self) -> WhileOp:
        self.expect(TokenType.WHILE)
        condition = self.parse_condition()
        self.expect(TokenType.DO)
        operation = self.parse_operation()
        return WhileOp(condition=condition, operation=operation)

    def parse_match(self) -> MatchOp:
        self.expect(TokenType.MATCH)
        ref = self.parse_ref()
        self.expect(TokenType.LBRACE)
        arms = []
        while not self.check(TokenType.RBRACE, TokenType.EOF):
            val = self.parse_value()
            self.expect(TokenType.ARROW)
            op = self.parse_operation()
            arms.append((val, op))
            self.match(TokenType.COMMA)
        self.expect(TokenType.RBRACE)
        return MatchOp(ref=ref, arms=arms)

    def parse_stream(self) -> StreamOp:
        self.expect(TokenType.STREAM)
        op = self.parse_operation()
        self.expect(TokenType.TO)
        target = self.expect(TokenType.IDENTIFIER).value
        return StreamOp(operation=op, target=target)

    # -------------------------------------------------------------------------
    # Fault Handling
    # -------------------------------------------------------------------------

    def parse_fault_clause(self) -> FaultClause:
        condition = None
        # Check if there's a condition before the arrow
        if not self.check(TokenType.ARROW):
            condition = self.parse_condition()
        self.expect(TokenType.ARROW)
        action = self.parse_fault_action()
        return FaultClause(condition=condition, action=action)

    def parse_fault_action(self) -> FaultAction:
        if self.match(TokenType.HALT):
            self.expect(TokenType.LBRACKET)
            reason = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.RBRACKET)
            return FaultAction(kind="HALT", argument=reason)
        elif self.match(TokenType.RETRY):
            self.expect(TokenType.LBRACKET)
            count = self.expect(TokenType.INTEGER).value
            self.expect(TokenType.RBRACKET)
            return FaultAction(kind="RETRY", argument=count)
        elif self.match(TokenType.FALLBACK):
            self.expect(TokenType.LBRACKET)
            node_name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.RBRACKET)
            return FaultAction(kind="FALLBACK", argument=node_name)
        else:
            raise ParseError("Expected HALT, RETRY, or FALLBACK", self.peek())

    # -------------------------------------------------------------------------
    # Conditions & References
    # -------------------------------------------------------------------------

    def parse_condition(self) -> Condition:
        left = self.parse_value()
        op_tok = self.peek()
        if op_tok.type in (TokenType.EQEQ, TokenType.NEQ, TokenType.LT,
                           TokenType.GT, TokenType.LTE, TokenType.GTE):
            op = self.advance().value
        else:
            raise ParseError("Expected comparison operator", op_tok)
        right = self.parse_value()
        return Condition(left=left, op=op, right=right)

    def parse_ref(self) -> Ref:
        # First part can be IN (keyword) or an identifier
        if self.check(TokenType.IN):
            parts = [self.advance().value]
        else:
            parts = [self.expect(TokenType.IDENTIFIER).value]
        while self.match(TokenType.DOT):
            # Could be OUT, IN, ERR, or any identifier
            if self.check(TokenType.OUT):
                parts.append(self.advance().value)
            elif self.check(TokenType.IN):
                parts.append(self.advance().value)
            else:
                parts.append(self.expect(TokenType.IDENTIFIER).value)
        return Ref(parts=parts)

    def parse_value(self) -> Any:
        tok = self.peek()
        if tok.type == TokenType.NULL:
            self.advance()
            return None
        elif tok.type == TokenType.STRING:
            return self.advance().value
        elif tok.type == TokenType.INTEGER:
            return int(self.advance().value)
        elif tok.type == TokenType.FLOAT:
            return float(self.advance().value)
        elif tok.type == TokenType.BOOLEAN:
            return self.advance().value == "true"
        else:
            return self.parse_ref()

    def parse_json_object(self) -> JsonObject:
        self.expect(TokenType.LBRACE)
        pairs = {}
        while not self.check(TokenType.RBRACE, TokenType.EOF):
            key = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.COLON)
            value = self.parse_value()
            pairs[key] = value
            self.match(TokenType.COMMA)
        self.expect(TokenType.RBRACE)
        return JsonObject(pairs=pairs)

    def parse_identifier_list(self) -> List[str]:
        names = [self.expect(TokenType.IDENTIFIER).value]
        while self.match(TokenType.COMMA):
            names.append(self.expect(TokenType.IDENTIFIER).value)
        return names

    def parse_identifier_list_inline(self) -> List[str]:
        """Parse comma-separated identifiers without brackets."""
        names = [self.expect(TokenType.IDENTIFIER).value]
        while self.match(TokenType.COMMA):
            names.append(self.expect(TokenType.IDENTIFIER).value)
        return names
