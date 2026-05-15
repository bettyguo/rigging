# Contributing to rigging

> Short version: open an issue first if it's bigger than a typo. We try
> to respond in 48h. We are friendly to disagreement; we are unfriendly
> to design-by-committee.

Thank you for considering a contribution. This project's eventual quality
is bounded by the clarity of the thinking that precedes it, so we put a
moderate amount of process at the front and almost none at the back.

---

## What we welcome

**High value, please send PRs:**

- 🪝 New adapters (LangGraph, AutoGen, Goose, real-world MCP servers, …).
- 🧪 Adversarial scenarios for the benchmark.
- 🧱 A counter-ADR that disagrees with an existing one.
- 🐛 Bug reports with a minimal reproduction.
- 📐 Spec corrections (typos in normative MUST/SHOULD/MAY language are
  bugs).
- 📊 A scored run of `rig-bench v0` against an external rig
  implementation.

**Lower value, please open an issue first:**

- New top-level packages.
- New runtime invariants (these need an ADR).
- Performance optimisations that increase complexity.
- New external dependencies.

**Out of scope for v0** (please see [`docs/roadmap.md`](./docs/roadmap.md)):

- A new wire protocol.
- A model router or load balancer.
- A vector store / RAG layer.
- A web dashboard (use the GitHub Pages site).
- Production-grade auth (OIDC / OAuth flows).

---

## Setup

```bash
git clone https://github.com/bettyguo/rigging
cd rigging
python -m pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest tests/ -q
```

You should see **76 tests pass** in roughly three seconds.

Run the benchmark smoke suite:

```bash
python -m benchmarks.rig_bench.run
```

Lint & type-check:

```bash
ruff check .
mypy packages/
```

The CI workflow at [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
does all of the above on Python 3.12 and 3.13.

---

## Layout of a good PR

A good PR for a non-trivial change has four things:

1. **An issue link.** If your change has no issue, file one first. We do
   not merge surprise design changes.
2. **A focused diff.** One concept per PR. Refactors are separate from
   features are separate from formatting.
3. **A test that fails without the change and passes with it.**
   - For a new feature, add a unit test under `tests/unit/`.
   - For a new invariant, add a property test under `tests/property/`
     using Hypothesis.
   - For a new scenario, add a benchmark probe under
     `benchmarks/rig_bench/axes/`.
4. **A note on the design call, if any.**
   - For a small change, this is one or two lines in the PR description.
   - For a load-bearing change, this is a new ADR under
     [`docs/adr/`](./docs/adr/). Copy `0000-template.md`, give it the
     next four-digit number, and follow the Context / Decision /
     Consequences / Alternatives format.

---

## Commits

We don't enforce conventional-commits, but we like commit messages that
look like this:

```
Add LangGraph adapter (#42)

LangGraph supervisors expose `invoke()`; this commit wraps that in an
Agent protocol implementation, with the LangGraph thread-id mapped onto
the contract_id so traces correlate.

Closes #42.
```

The "what" of the change is in the diff. The "why" goes in the message.

---

## Adding an adapter

Adapters bridge an existing harness into the rig. They are deliberately
small — the three reference adapters are all under 200 LOC each.

1. Create a new module under
   [`packages/rigging-adapters/src/rigging/adapters/`](./packages/rigging-adapters/src/rigging/adapters/).
2. Implement the `Agent` protocol from
   [`rigging.core.protocols`](./packages/rigging-core/src/rigging/core/protocols.py).
3. Add at least one example demonstrating it under
   [`examples/`](./examples/).
4. Add an integration test under `tests/integration/`.
5. Add a one-paragraph note in
   [`docs/architecture.md`](./docs/architecture.md) describing the
   adapter and what it does *not* try to abstract.

Adapters are not where the cleverness goes. If your adapter is more than
~250 LOC, ask yourself whether the participant ought to be a real rig
agent rather than a wrapped one.

---

## Disagreeing with us

You will read an ADR, decide it's wrong, and want to fix it. This is the
single most useful kind of contribution.

The right move is:

1. Open an issue summarising the disagreement.
2. Draft a counter-ADR under [`docs/adr/`](./docs/adr/) with a number
   one higher than the highest current ADR. Title it `ADR-NNNN: revisit
   ADR-MMMM (...)`. Keep the same format.
3. PR the counter-ADR. We will engage.

We expect to discard at least one of the v0 ADRs by the time v1 ships.
That's how we know we built the right primitive.

---

## Code style

- **Python 3.12+.** Type annotations on everything in `packages/*/src/`.
- **Ruff** for linting. Configured in `pyproject.toml`.
- **mypy --strict** for typing in packages. Tests, examples, and
  benchmarks are looser.
- **structlog** for log output in library code. Never `print()` in a
  library module.
- **Docstrings:** Google style, at least for public symbols. Field
  descriptions on Pydantic models.
- **anyio**, not bare asyncio. The rig must remain usable from trio
  loops.

---

## Reporting security issues

**Do not file public issues for security reports.** See
[`SECURITY.md`](./SECURITY.md) for our disclosure policy.

---

## Code of conduct

See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md). In one sentence: act
in good faith and assume good faith. Disagreement is welcome; bad faith
is not.

---

## License

By submitting a contribution you agree to license it under
[Apache 2.0](./LICENSE), the project's license.
