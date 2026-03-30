# AXON

> A programming language designed for AI to write — not humans.

## The Problem

Every programming language ever built assumed a human would write and read it.
That assumption is breaking down.

When AI generates your code, the constraints that shaped language design for
50 years stop mattering: developer readability, manual error handling, explicit
rollback logic, sequential thinking. AI doesn't need any of that. But it still
produces languages that were designed for humans — TypeScript, Python — because
that's all that exists.

AXON is what a language looks like when the developer is no longer the bottleneck.

## What Makes AXON Different

**Graph execution, not sequential lines**
AXON programs are dependency graphs. The compiler infers which nodes can run
in parallel automatically — no async/await juggling, no Promise.all() by hand.

**Semantic types**
Not `string`. `email_address`. Not `number`. `dollar_amount`. The type system
carries meaning, and the runtime validates it without you writing a single guard.

**Mandatory reversibility**
Every `db.write` must declare its `INVERSE`. The compiler refuses to compile
without it. Rollback isn't something you remember to write — it's something
you're required to declare.

**First-class fault handling**
No try/catch scattered through your logic. Every node declares its `FAULT`
paths explicitly. The failure modes are part of the program structure.

**BUDGET as a compile primitive**
`BUDGET latency=500ms` wraps your entire graph in a typed timeout. Cost and
latency are constraints you declare, not surprises you discover in production.

## Example
```axon
GRAPH process_order
  IN    userId<user_id>, items<cart_item[]>
  OUT   order<order_record>
  BUDGET latency=500ms

  NODE fetch_user
    OP      db.read users WHERE id == IN.userId
    OUT     user<user_record>
    FAULT   fetch_user == null -> HALT[not_found]

  NODE calc_total
    OP      SUM items[].price * items[].quantity
    OUT     total<dollar_amount>

  NODE check_funds
    OP      ASSERT fetch_user.balance >= calc_total
    FAULT   -> HALT[insufficient_funds]
    AFTER   fetch_user, calc_total

  NODE create_order
    OP      db.write orders {userId: IN.userId, total: calc_total, status: "pending"}
    OUT     order<order_record>
    INVERSE db.delete orders WHERE id == create_order.id
    AFTER   check_funds

  NODE notify
    OP      email.send TO=fetch_user.email TEMPLATE=order_confirmed
    ASYNC   true
    AFTER   create_order

  RETURN  create_order
  ROLLBACK ON FAULT [create_order]
```

The compiler automatically:
- Runs `fetch_user` and `calc_total` **in parallel** (no dependency between them)
- Generates typed rollback from the `INVERSE` declaration
- Validates `userId` is a non-empty string before execution
- Wraps the entire graph in a 500ms timeout

## Getting Started
```bash
git clone https://github.com/Loudermilski/axon-lang
cd axon-lang
python axonc.py tests/order_processor.axon --out output/order_processor.ts
```

**Requirements:** Python 3.10+

## Compiler Architecture
```
.axon source
    ↓ Lexer      (src/lexer.py)    — tokenizes source
    ↓ Parser     (src/parser.py)   — builds AST
    ↓ Validator  (src/codegen.py)  — enforces compiler guarantees
    ↓ Codegen    (src/codegen.py)  — emits TypeScript
    → .ts output (deployable to Vercel, Azure, Node — unchanged)
```

## Compiler Guarantees

The AXON compiler **refuses to compile** programs that violate these rules:

1. `db.write` without `INVERSE` → compile error
2. `RETURN` references nonexistent node → compile error
3. `AFTER` references nonexistent node → compile error
4. Circular node dependencies → compile error

## Roadmap

- [ ] Python compile target
- [ ] `CONFIDENCE` types — `Confident<email_address>` vs `Uncertain<T>`
- [ ] `MCP` operation — native Model Context Protocol calls
- [ ] `HUMAN` operation — `await human.approve(decision)`
- [ ] VS Code extension (syntax highlighting + error squiggles)
- [ ] AXON Playground — compile in the browser
- [ ] WASM compile target

## Status

Early prototype. Compiler is functional. Two example programs compile and
produce correct TypeScript. 29 tests passing.

**This is a research language exploring what AI-native execution looks like.**
Contributions and critique welcome.

## License

MIT
