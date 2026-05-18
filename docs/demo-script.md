# Demo script — 5 minutes from clone to blame chain

> Voice this aloud. Record with [`asciinema`](https://asciinema.org/);
> linkable cast goes into the README.
>
> Pacing assumes a viewer who knows what an agent is but has never
> heard the word "rigging". 5 minutes hard cap.

---

## 0:00–0:20 — Setup shot (no narration)

Terminal opens. `pwd` shows a fresh directory. Run `git clone` and
`cd`:

```bash
git clone https://github.com/bettyguo/rigging
cd rigging
python -m pip install -e . pydantic anyio cryptography typer rich \
    structlog opentelemetry-sdk pytest hypothesis pytest-anyio
```

(Optionally pre-installed for the recording.)

## 0:20–0:50 — The pitch

> "Every team building multi-agent systems eventually writes the same
> function: `route_to_agent`. They open-code identity, cost,
> verification, and blame. Rigging is what that function should have
> been all along — a typed, signed, auditable substrate that composes
> harnessed agents into a coherent system. Three minutes to see why
> this matters."

## 0:50–1:30 — A signed identity, made in one command

```bash
RIG_PASS=hunter2 rig identity create --passphrase-env RIG_PASS
```

> "An Ed25519 keypair, stored encrypted, with a `did:rig:` identifier
> derived from the public key. This is the bedrock — every contract
> and every output in the system will trace back to a key like this
> one."

`cat rig.key.did` shows the DID. Point at it.

## 1:30–2:30 — The minimum viable rig

```bash
rig run 01-two-agent-handoff
```

Output appears: two DIDs, a worker's output, a 4-span trace.

> "Two agents, two signed cards, one delegation contract. The worker
> signed its output with its identity key. The rig recorded the
> contract, the execution, and the cost in a structured trace. No
> hand-coded glue."

## 2:30–4:00 — The adversarial subagent

```bash
rig run 03-adversarial-subagent
```

> "Now the worker has been configured to return obviously-wrong
> output. The planner doesn't know this. In an ad-hoc setup, the
> planner would happily move on. But the contract names a verifier;
> the rig invokes it; the verifier rejects; and — here's the punch
> line — the rig produces a blame chain pointing at the worker's DID.
> Not the rig. Not the planner. The worker."

Point at the `Blame chain` and `Proximate cause` lines in the output.

> "This is the whole reason rigs exist. When a multi-agent system
> fails, *which agent is to blame* is a mechanically answerable
> question."

## 4:00–4:40 — The trace inspector

If a trace was dumped to a file (extend example 03 to write
`trace.json` if needed):

```bash
rig trace inspect trace.json
```

> "The same data, rendered. Anyone with the trace can verify the
> signatures, reconstruct the blame chain, and answer cost questions.
> No backend required."

## 4:40–5:00 — Close

> "MCP is the wire between an agent and its tools. A2A is the wire
> between agents. Rigging is the layer above both — the typed,
> signed, opinionated runtime that turns ad-hoc supervisor patterns
> into a substrate you can audit. Read `CONCEPT.md` for the long
> form; the benchmark numbers are in `benchmarks/results`."

Pan out. End on the repository's top-level `tree` output.

---

## Cuts

If under-time, drop the `rig trace inspect` segment (it is the
clearest cut). If over-time, drop section 1:30–2:30 (the smallest
example is the most expendable; the adversarial one carries the
demo).

## Recording notes

- Use a clean shell prompt (`PS1='> '` or equivalent).
- Set `COLUMNS=120`.
- Pre-run `rig identity create` before recording so the passphrase
  prompt doesn't show.
- Capture at 1080p, 24fps; voice as separate audio track for
  re-cutability.
