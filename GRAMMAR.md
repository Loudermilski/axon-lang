# AXON Language Grammar Specification v0.1

## Design Principles
- One canonical form for every construct
- Semantic types over primitive types
- Reversibility mandatory on all writes
- Fault paths declared at node level
- Parallelism inferred from graph dependencies

---

## Top Level

```ebnf
program         ::= types_block? graph+

types_block     ::= "TYPES" "{" type_def* "}"
type_def        ::= identifier "{" param_list "}"

graph           ::= "GRAPH" identifier
                    "IN"     param_list
                    "OUT"    typed_param
                    budget?
                    node+
                    "RETURN"   node_ref
                    rollback?

budget          ::= "BUDGET" budget_constraint ("," budget_constraint)*
budget_constraint ::= "latency=" duration
                    | "tokens=" integer
                    | "cost=" dollar_amount

param_list      ::= typed_param ("," typed_param)*
typed_param     ::= identifier "<" semantic_type ">"
```

---

## Nodes

```ebnf
node            ::= "NODE" identifier
                    if_clause?
                    op_clause
                    out_clause?
                    fault_clause*
                    inverse_clause?
                    async_clause?
                    after_clause?

if_clause       ::= "IF" condition
op_clause       ::= "OP" operation
out_clause      ::= "OUT" typed_param
fault_clause    ::= "FAULT" fault_condition "->" fault_action
inverse_clause  ::= "INVERSE" operation
async_clause    ::= "ASYNC" boolean
after_clause    ::= "AFTER" identifier ("," identifier)*
```

---

## Operations

```ebnf
operation       ::= db_read
                  | db_write
                  | db_delete
                  | assert_op
                  | compute_op
                  | email_op
                  | http_op
                  | mcp_op
                  | human_op
                  | call_op
                  | for_each_op
                  | match_op

db_read         ::= "db.read" identifier "WHERE" condition
db_write        ::= "db.write" identifier (filter)? json_object
db_delete       ::= "db.delete" identifier "WHERE" condition

assert_op       ::= "ASSERT" expression
compute_op      ::= "SUM" | "AVG" | "COUNT" | "MAP" | "FILTER" expression

email_op        ::= "email.send" "TO=" ref "TEMPLATE=" identifier
http_op         ::= "http." method "URL=" string_literal (payload)?
mcp_op          ::= "mcp." identifier "." identifier (args)?
human_op        ::= "human.approve" "(" string_literal ")"
                  | "human.input" "(" string_literal ")"
call_op         ::= "CALL" identifier "(" json_object? ")"
for_each_op     ::= "FOR EACH" identifier "IN" ref "DO" operation
while_op        ::= "WHILE" condition "DO" operation
match_op        ::= "MATCH" ref "{" (value "->" operation)* "}"
```

---

## Fault Handling

```ebnf
fault_condition ::= ref "==" "null"
                  | ref comparison_op literal
                  | boolean_expr
                  | (empty means "on any fault")

fault_action    ::= "HALT" "[" reason_code "]"
                  | "RETRY" "[" integer "]"
                  | "FALLBACK" "[" node_ref "]"
```

---

## Rollback

```ebnf
rollback        ::= "ROLLBACK" "ON" "FAULT" "[" identifier_list "]"
identifier_list ::= identifier ("," identifier)*
```

---

## Semantic Types

```ebnf
semantic_type   ::= primitive_type
                  | domain_type
                  | collection_type

primitive_type  ::= "string" | "integer" | "boolean" | "float"

domain_type     ::= "user_id"         -- validated UUID, user namespace
                  | "email_address"   -- RFC 5322 validated
                  | "dollar_amount"   -- decimal, 2 places, non-negative
                  | "order_record"    -- structured db entity
                  | "user_record"     -- structured db entity
                  | "cart_item"       -- {id, price, quantity, sku}
                  | "timestamp"       -- ISO 8601
                  | "url"             -- validated URL
                  | "phone_number"    -- E.164 format
                  | "jwt_token"       -- validated JWT structure
                  | identifier        -- custom type (declared in TYPES block)

collection_type ::= semantic_type "[]"
```

---

## References

```ebnf
ref             ::= "IN." identifier                  -- graph input
                  | node_ref "." ("OUT" | "ERR")      -- node output
                  | identifier                        -- local binding

node_ref        ::= identifier  -- must match a NODE name in scope
```

---

## Literals & Primitives

```ebnf
identifier      ::= [a-z_][a-z0-9_]*
integer         ::= [0-9]+
boolean         ::= "true" | "false"
duration        ::= integer ("ms" | "s" | "m")
string_literal  ::= '"' [^"]* '"'
json_object     ::= "{" (identifier ":" value ("," identifier ":" value)*)? "}"
```

---

## Compilation Targets
- TypeScript (primary)
- Python (secondary)  
- WASM (future)

## Compiler Guarantees
1. Every NODE with a db.write MUST have an INVERSE or compilation fails
2. Every FAULT path MUST be declared or compilation fails
3. Circular graph dependencies are a compile error
4. BUDGET violations emit warnings, not errors (runtime enforced)
