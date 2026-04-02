# Instructions for AI Agents Generating AXON

AXON is a graph-structured execution language designed for AI-to-AI communication. When generating AXON code for the user, follow these principles:

## 1. Core Principles
- **Think in Graphs:** Programs are dependency graphs, not sequential lines.
- **Semantic Over Primitives:** Prefer `user_id` or `dollar_amount` over `string` or `number`.
- **Mandatory Reversibility:** Every `db.write` MUST have an `INVERSE`.
- **Explicit Faults:** Use `FAULT -> HALT[reason]` for all failure paths.

## 2. Syntax Reference (v0.2)

### Types Block
Define custom structures at the top of the file:
```axon
TYPES {
  User { email<email_address>, age<integer> }
}
```

### Graphs and Inputs
Graphs accept a single object-like param list:
```axon
GRAPH my_graph
  IN    email<email_address>, amount<dollar_amount>
  OUT   success<boolean>
```

### Nodes and Parallelism
The compiler runs nodes in parallel unless linked via `AFTER` or data refs.
```axon
  NODE check_db
    OP      db.read users WHERE email == IN.email
    OUT     user<user_record>

  NODE process
    IF IN.amount > 0
    OP      mcp.payment.charge({id: user.id})
    AFTER   check_db
```

### Human-in-the-Loop
Use for sensitive decisions:
```axon
  NODE verify
    OP      human.approve("Is this payment valid?")
```

## 3. Workflow for "Vibe Coding"
1. **Generate AXON:** Produce the logic graph concisely.
2. **Suggest Visualization:** Tell the user to run `axonc.py --viz` to see the logic diagram.
3. **Compile:** The user compiles to `.ts` or `.py` for their production environment.

## 4. Common Pitfalls
- **Positional Args:** Do NOT use positional args in `CALL`. Use `CALL graph({key: val})`.
- **Await:** Do NOT worry about `async/await`. The AXON compiler handles all concurrency.
- **Error Handling:** Do NOT use try/catch. Use `FAULT` clauses.
