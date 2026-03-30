# AXON Language — Roadmap, Publishing Plan & Thesis
**Created:** 2026-03-30  
**Author:** Loudermilski  
**Tagline:** Engineer the unexpected. Change the game.

---

## The Core Thesis (One Paragraph)

Every generation of programming language traded control for expressiveness. Assembly gave way to C, C to objects, objects to dynamic languages, dynamic languages to AI prompting. Each step widened the gap between human intent and machine execution. AI blew that gap wide open — and introduced a new class of problems: non-determinism, unauditable reasoning, invisible cost, and no native rollback. AXON is a response to that gap. It is an AI-native execution language designed not for humans to write or read, but for AI to generate and runtimes to verify. Its primitives are not strings and integers — they are semantic types, dependency graphs, fault declarations, and mandatory reversibility. The compiler guarantees what developers used to guarantee manually. MCP becomes the trust boundary. AXON becomes the substrate.

---

## Publishing Roadmap

### Day 1 — Tomorrow (Establish Prior Art)
- [ ] Create GitHub repo: `axon-lang/axon`
- [ ] Push compiler v0.1 (lexer, parser, codegen, grammar, test)
- [ ] Write README (use thesis paragraph above + language sample)
- [ ] Tag release: `v0.1.0-alpha`
- [ ] Post on X/LinkedIn: "I've been thinking about what a language looks like when humans are no longer the author or the reader. Built a prototype. Here's the idea." Link repo.

### Week 1 — Solidify the Concept
- [ ] Write the Dev.to / Substack post (draft below)
- [ ] Submit to arXiv cs.PL — short paper (outline below)
- [ ] Add `LICENSE` (MIT for language spec, consider BSL for compiler)
- [ ] Register `axon-lang.dev` domain

### Month 1 — Build Credibility
- [ ] Extend compiler: fix WHERE clause codegen, add Python target
- [ ] Write 3 more example programs (auth flow, payment processor, agentic workflow)
- [ ] Publish comparison benchmark: AXON token count vs TypeScript token count
- [ ] Submit to Hacker News: "Show HN: AXON — a programming language designed for AI, not humans"

### Month 2-3 — Community & Commercial Signal
- [ ] VS Code syntax highlighting extension
- [ ] AXON Playground — web UI that compiles AXON to TypeScript in browser
- [ ] Reach out to 3 AI agent framework maintainers (LangChain, CrewAI, AutoGen)
- [ ] Write the MCP integration spec — AXON as native MCP orchestration language

---

## Language Development Roadmap

### Phase 1 — Core (DONE ✓)
- Lexer
- Parser
- AST node definitions
- TypeScript code generator
- Automatic parallelism via dependency graph
- Rollback stack from INVERSE declarations
- Semantic type validators
- FAULT / HALT / RETRY / FALLBACK

### Phase 2 — Correctness (Next Session)
- Fix WHERE clause → query object codegen
- Fix ref resolution across node boundaries
- Add circular dependency detection
- Add compile-time INVERSE enforcement (write without INVERSE = error)
- Add BUDGET runtime wrapper generation
- Unit test suite (pytest)

### Phase 3 — Power Features
- `CONFIDENCE` type modifier — `Confident<email_address>` vs `Uncertain<email_address>`
- `MCP` operation type — native MCP server call syntax
- `HUMAN` operation — `await human.approve(decision)` construct
- `TYPES` block — user-defined semantic types with validation rules
- Python compile target (alongside TypeScript)

### Phase 4 — Tooling
- VS Code extension (syntax highlighting + error squiggles)
- AXON Language Server Protocol (LSP) implementation
- Web playground (AXON in → TypeScript out, live)
- AXON formatter (canonical form enforcement)

### Phase 5 — Runtime
- AXON runtime library (npm package: `@axon-lang/runtime`)
- Native MCP boundary declarations
- Cost tracking middleware
- Execution graph visualizer

### Phase 6 — Ecosystem
- AXON Package Registry (`.axon` graph libraries)
- Standard library: `axon/http`, `axon/auth`, `axon/payments`
- Certified compiler for enterprise compliance use cases

---

## Compiler: Known Issues to Fix Tomorrow

```
Priority 1 — Correctness bugs:
  WHERE clause emits boolean expression instead of query object
    Current:  db.users.findOne(id === inputs.userId)
    Expected: db.users.findOne({ id: inputs.userId })

  Node output refs not resolved across nodes
    Current:  fetch_user.balance  (unresolved)
    Expected: (results.fetch_user as UserRecord).balance

  Compute expression raw passthrough needs structured parsing
    Current:  SUM items[].price * items[].quantity → raw string
    Expected: inputs.items.reduce((acc, i) => acc + i.price * i.quantity, 0)

Priority 2 — Compiler guarantees:
  Enforce: db.write without INVERSE → compile error
  Enforce: Unreachable nodes → compile warning
  Enforce: BUDGET latency → wrap execution in Promise.race with timeout
```

---

## arXiv Paper Outline
**Title:** AXON: A Graph-Structured Execution Language for AI-Native Software Systems  
**Category:** cs.PL (Programming Languages)  
**Target length:** 6-8 pages

```
1. Introduction
   - The abstraction progression: binary → assembly → procedural → OOP → dynamic → AI
   - The new problem class AI introduces
   - AXON's response

2. Motivation
   - Developer speed vs. CPU performance was the 20th century tradeoff
   - Capability vs. accountability is the 21st century tradeoff
   - Why existing languages are the wrong substrate for AI-generated code

3. Language Design
   3.1 Graph semantics vs. sequential execution
   3.2 Semantic type system
   3.3 Mandatory reversibility (INVERSE)
   3.4 First-class fault handling
   3.5 BUDGET as a compile-time primitive
   3.6 MCP as the trust boundary

4. Compiler Architecture
   4.1 Lexer and token model
   4.2 AST design
   4.3 Dependency graph analysis and parallelism inference
   4.4 TypeScript code generation
   4.5 Compiler guarantees

5. Evaluation
   5.1 Token count comparison (AXON vs TypeScript for equivalent programs)
   5.2 Parallelism gains (sequential vs. inferred parallel execution)
   5.3 Rollback correctness (lines of code eliminated)

6. Related Work
   - WebAssembly (compile target model)
   - Temporal.io (workflow reversibility)
   - Effect-TS (typed error handling)
   - MCP protocol (trust boundary)

7. Future Work
   - Confidence types
   - HUMAN operation
   - WASM compile target
   - Runtime cost enforcement

8. Conclusion
```

---

## Dev.to / Substack Post Draft
**Title:** I built a programming language that no human should ever write

**Hook:**
> Every programming language ever built has had one thing in common: a human had to read it. I'm not sure that constraint still makes sense.

**Body flow:**
1. Tell the abstraction story (2 paragraphs — binary to AI)
2. Name the new problem: the intent-execution gap
3. Introduce AXON and what makes it different
4. Show the TypeScript vs AXON comparison side by side
5. Explain what the compiler does automatically (parallelism, rollback, validation)
6. Make the MCP trust layer argument
7. Call to action: GitHub link, looking for contributors

---

## GitHub README Outline

```markdown
# AXON

> A programming language designed for AI to write, not humans.

## The Problem
[2 paragraphs — the abstraction arc, the new gap]

## What AXON Does Differently
- Graph execution, not sequential lines
- Semantic types (email_address, dollar_amount, user_id)
- Mandatory reversibility — every write declares its INVERSE
- Fault paths as first-class syntax
- Automatic parallelism from dependency analysis
- MCP as the native trust boundary

## Example
[AXON source and TypeScript output side by side]

## Getting Started
pip install axon-compiler  (coming soon)
python axonc.py myprogram.axon

## Roadmap
[Link to roadmap]

## Contributing
[Guidelines]

## License
MIT
```

---

## Session Handoff — Start Here Tomorrow

**Immediate next steps in order:**

1. Push compiler to GitHub first (prior art clock starts ticking)
2. Open new Claude session, say: **"Continue building the AXON language compiler. Load context from our conversation. Fix the WHERE clause codegen and node ref resolution bugs. Here are the known issues:"** then paste the Priority 1 bugs above.
3. Write README while compiler fixes compile
4. Submit arXiv draft by end of week

**Key files to have ready:**
- `src/lexer.py` — complete ✓
- `src/parser.py` — complete, bugs in ref resolution
- `src/ast_nodes.py` — complete ✓  
- `src/codegen.py` — complete, bugs in WHERE + node refs
- `axonc.py` — entry point ✓
- `tests/order_processor.axon` — working test case ✓
- `output/order_processor.ts` — compiled output ✓

**The one sentence to remember:**
> AXON is what programming languages look like when the developer's time and comprehension are no longer the constraint — only correctness, auditability, and intent.
