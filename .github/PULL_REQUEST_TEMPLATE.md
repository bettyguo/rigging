<!--
Thank you for the PR! A few notes before submitting:

- For load-bearing changes (runtime invariants, spec edits, new top-level
  packages), please open an issue first and link it below. We do not
  merge surprise design changes.

- For security fixes, please follow SECURITY.md instead of opening a
  public PR until disclosure is coordinated.
-->

## Summary

<!-- One or two sentences. What does this PR change and why? -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New adapter
- [ ] New benchmark probe / axis
- [ ] Runtime invariant (requires ADR)
- [ ] Spec / ADR edit
- [ ] Docs / site
- [ ] Refactor without behaviour change

## How was this tested?

<!-- Which tests? Which examples? Hand-tested any traces? -->

```
pytest tests/ -q
python -m benchmarks.rig_bench.run
ruff check .
mypy packages/
```

## Spec / ADR implications

<!--
Does this change any v0 spec? Does it deserve an ADR? If so, link to it
under `docs/adr/`. If it explicitly supersedes an earlier ADR, name it.
-->

- [ ] No spec change
- [ ] Adds / updates an ADR (link: `docs/adr/NNNN-...`)
- [ ] Supersedes ADR-MMMM

## Checklist

- [ ] Added or updated tests where applicable.
- [ ] Updated relevant docs (README, FAQ, EXAMPLES, architecture, spec).
- [ ] No new external runtime dependencies (or justified in description).
- [ ] No `print()` calls in library code; structlog instead.
- [ ] If touching the live site, ran it locally with a static server.
