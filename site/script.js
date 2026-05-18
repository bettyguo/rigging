/* ============================================================
   rigging — site/script.js
   - copy-to-clipboard
   - interactive blame chain explorer
   - contract negotiation animation
   ============================================================ */
(() => {
  // ============================================================
  // copy buttons
  // ============================================================
  document.querySelectorAll('.copy').forEach((btn) => {
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy || '');
        const before = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.color = '#10b981';
        setTimeout(() => { btn.textContent = before; btn.style.color = ''; }, 1400);
      } catch (e) {
        btn.textContent = 'Failed';
      }
    });
  });

  // ============================================================
  // trace explorer
  // ============================================================
  /**
   * Each scenario: { title, sub, verdict, steps[] }
   * each step: { kind, agent, did, payload, cost, sig, status, tag, proximate? }
   */
  const SCENARIOS = {
    happy: {
      title: 'Happy path · planner → worker → verifier ✓',
      sub: '3 signed envelopes · verdict accept',
      verdict: { tone: 'ok',
        text: 'Operator received <strong>ExecuteResult</strong> with output signed by the worker, verdict signed by the verifier, and a clean trace of 3 envelopes. <strong class="ok">All signatures match.</strong>' },
      steps: [
        { kind: 'contract.propose', agent: 'planner', did: 'did:rig:k0m…7zE',
          payload: 'translate_pdf({uri:"s3://…", lang:"fr"})',
          cost: 'budget=usd 0.50', sig: 'sig ✓', status: 'ok', tag: 'PROPOSE' },
        { kind: 'execute',          agent: 'worker',  did: 'did:rig:9rT…qN2',
          payload: 'output: {pages:14, language:"fr"}',
          cost: 'cost=usd 0.12',     sig: 'sig ✓', status: 'ok', tag: 'EXECUTE' },
        { kind: 'verify',           agent: 'quality', did: 'did:rig:fY1…8wB',
          payload: 'verdict: accept',
          cost: 'cost=usd 0.01',     sig: 'sig ✓', status: 'ok', tag: 'VERIFY' },
      ],
    },

    adversarial: {
      title: 'Adversarial worker · verifier rejects ✗',
      sub: '3 signed envelopes · proximate cause = worker',
      verdict: { tone: 'bad',
        text: 'Operator received <strong class="bad">VerifierRejected</strong>. Walking the chain backwards: verdict is signed by the verifier; verdict references the worker\'s output envelope; that envelope, if replaced by ground truth, would have made the verifier accept. <strong>Proximate cause: <code>did:rig:9rT…qN2</code> (worker).</strong>' },
      steps: [
        { kind: 'contract.propose', agent: 'planner', did: 'did:rig:k0m…7zE',
          payload: 'translate_pdf(…)',     cost: 'budget=usd 0.50',
          sig: 'sig ✓', status: 'ok',  tag: 'PROPOSE' },
        { kind: 'execute',          agent: 'worker',  did: 'did:rig:9rT…qN2',
          payload: 'output: {pages:0, language:"??"} ← injected adversarial output',
          cost: 'cost=usd 0.05', sig: 'sig ✓', status: 'bad', tag: 'EXECUTE',
          proximate: true },
        { kind: 'verify',           agent: 'quality', did: 'did:rig:fY1…8wB',
          payload: 'verdict: reject · reason: schema_violation',
          cost: 'cost=usd 0.01', sig: 'sig ✓', status: 'bad', tag: 'REJECT' },
      ],
    },

    budget: {
      title: 'Budget overrun on subcontract · A inviolable',
      sub: 'C exceeds; B sees overrun; A\'s ledger is untouched',
      verdict: { tone: 'warn',
        text: 'Operator received <strong class="warn">BudgetOverrun</strong> on contract <code>C</code>. The cost ledger debits <strong>B\'s</strong> sub-allocation, not A\'s. <strong>A\'s budget is inviolable.</strong>' },
      steps: [
        { kind: 'contract.propose', agent: 'A→B', did: '— · budget=usd 1.00',
          payload: 'plan_subwork(…)',
          cost: 'budget=usd 1.00',     sig: 'sig ✓', status: 'ok', tag: 'PROPOSE' },
        { kind: 'contract.propose', agent: 'B→C', did: '— · sub-budget=usd 0.20',
          payload: 'render_table(…)',
          cost: 'budget=usd 0.20',     sig: 'sig ✓', status: 'ok', tag: 'SUBCONTRACT' },
        { kind: 'execute',          agent: 'C',   did: 'did:rig:cFa…2pX',
          payload: 'output: {…} (used 0.33 usd)',
          cost: 'cost=usd 0.33 > 0.20', sig: 'sig ✓', status: 'warn',  tag: 'OVERRUN',
          proximate: true },
        { kind: 'cost.debit',       agent: 'B',   did: 'did:rig:b22…uYw',
          payload: 'debited from B\'s ledger; A.remaining = usd 1.00 (unchanged)',
          cost: '—', sig: '—', status: 'warn', tag: 'LEDGER' },
      ],
    },

    expired: {
      title: 'Contract expired mid-execute',
      sub: 'Cancel scope fires; contract voided; no silent retry',
      verdict: { tone: 'warn',
        text: 'Operator received <strong class="warn">ContractExpired</strong>. The runtime <em>refuses</em> to silently substitute another worker. Retry is the caller\'s explicit decision, with a new signed contract.' },
      steps: [
        { kind: 'contract.propose', agent: 'A→B', did: 'expires=T+30s',
          payload: 'long_task(…)',
          cost: 'budget=usd 0.50', sig: 'sig ✓', status: 'ok', tag: 'PROPOSE' },
        { kind: 'execute',          agent: 'B',   did: 'did:rig:9rT…qN2',
          payload: 'work in progress…',
          cost: 'cost=usd 0.10', sig: '—', status: 'warn', tag: 'EXECUTE' },
        { kind: 'contract.void',    agent: 'rig', did: 'reason=expired',
          payload: 'cancel scope fired at T+30s',
          cost: '—', sig: '—', status: 'warn', tag: 'VOID',
          proximate: true },
      ],
    },

    forged: {
      title: 'Forged signature on output envelope',
      sub: 'JWS check fails; rig refuses to admit unverified output',
      verdict: { tone: 'bad',
        text: 'Operator received <strong class="bad">SignatureInvalid</strong>. The envelope claims to be from the worker, but the JWS does not verify against the worker\'s registered card. <strong>The rig refuses to admit it.</strong>' },
      steps: [
        { kind: 'contract.propose', agent: 'A→B', did: '—',
          payload: 'render_chart(…)',
          cost: 'budget=usd 0.20', sig: 'sig ✓', status: 'ok', tag: 'PROPOSE' },
        { kind: 'execute',          agent: 'B?', did: '— · sig over wrong pubkey',
          payload: 'output: {…}',
          cost: 'cost=usd 0.05', sig: 'sig ✗', status: 'bad', tag: 'EXECUTE',
          proximate: true },
        { kind: 'contract.void',    agent: 'rig', did: 'reason=signature_invalid',
          payload: 'envelope rejected before verifier was invoked',
          cost: '—', sig: '—', status: 'bad', tag: 'VOID' },
      ],
    },
  };

  const traceList = document.getElementById('trace-list');
  const tTitle    = document.getElementById('scenario-title');
  const tSub      = document.getElementById('scenario-sub');
  const verdict   = document.getElementById('verdict');
  const scenarios = document.querySelectorAll('.scenario');

  function renderScenario(key) {
    const scn = SCENARIOS[key];
    if (!scn || !traceList) return;

    tTitle.textContent = scn.title;
    tSub.textContent = scn.sub;
    traceList.innerHTML = '';

    scn.steps.forEach((s, i) => {
      const li = document.createElement('li');
      li.className = `${s.status}${s.proximate ? ' proximate' : ''}`;
      li.innerHTML = `
        <span class="step-num">${i + 1}</span>
        <span>
          <strong>${s.kind}</strong>
          <span class="step-meta"> · ${s.agent} · ${s.did}</span>
          <div class="step-meta">${s.payload}</div>
          <div class="step-meta">${s.cost} · ${s.sig}</div>
        </span>
        <span class="step-tag">${s.tag}</span>
      `;
      traceList.appendChild(li);
    });

    verdict.innerHTML = scn.verdict.text;
    verdict.dataset.tone = scn.verdict.tone;
  }

  scenarios.forEach((btn) => {
    btn.addEventListener('click', () => {
      scenarios.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderScenario(btn.dataset.scenario);
    });
  });
  if (traceList) renderScenario('happy');

  // ============================================================
  // negotiation animation
  // ============================================================
  const negArrows = document.querySelectorAll('.neg-arrow');
  const negSteps  = document.querySelectorAll('#neg-steps li');
  const negStep   = document.getElementById('neg-step');
  const negPlay   = document.getElementById('neg-play');
  const negReset  = document.getElementById('neg-reset');

  let negCurrent = 0;
  let negTimer   = null;

  function setNegStep(n) {
    negCurrent = n;
    if (negStep) negStep.textContent = String(n);

    negArrows.forEach((g) => {
      const step = Number(g.dataset.step);
      g.classList.toggle('visible', step <= n);
      g.classList.toggle('flashing', step === n);
    });
    negSteps.forEach((li, i) => {
      li.classList.toggle('done', i + 1 < n);
      li.classList.toggle('current', i + 1 === n);
    });
  }

  function playNeg() {
    if (negTimer) return;
    if (negCurrent >= 6) setNegStep(0);
    negTimer = setInterval(() => {
      const next = negCurrent + 1;
      if (next > 6) {
        clearInterval(negTimer); negTimer = null;
        if (negPlay) negPlay.textContent = '↺ Replay';
        return;
      }
      setNegStep(next);
    }, 900);
    if (negPlay) negPlay.textContent = '⏸ Pause';
  }
  function pauseNeg() {
    if (negTimer) { clearInterval(negTimer); negTimer = null; }
    if (negPlay) negPlay.textContent = '▶ Play';
  }
  function resetNeg() {
    pauseNeg();
    setNegStep(0);
    if (negPlay) negPlay.textContent = '▶ Play';
  }

  if (negPlay) {
    negPlay.addEventListener('click', () => {
      if (negTimer) pauseNeg();
      else playNeg();
    });
  }
  if (negReset) negReset.addEventListener('click', resetNeg);
  if (negArrows.length) setNegStep(0);

  // ============================================================
  // cost simulator
  // ============================================================
  const simA = document.getElementById('sim-a-budget');
  const simB = document.getElementById('sim-b-budget');
  const simC = document.getElementById('sim-c-spend');
  const simOut = {
    a:   document.getElementById('sim-a-budget-out'),
    b:   document.getElementById('sim-b-budget-out'),
    c:   document.getElementById('sim-c-spend-out'),
    barA: document.getElementById('sim-bar-a'),
    barB: document.getElementById('sim-bar-b'),
    aMax: document.getElementById('sim-a-max'),
    aDebit: document.getElementById('sim-a-debit'),
    aRem: document.getElementById('sim-a-remaining'),
    bMax: document.getElementById('sim-b-max'),
    bDebit: document.getElementById('sim-b-debit'),
    bStatus: document.getElementById('sim-b-status'),
    verdict: document.getElementById('sim-verdict'),
  };
  function fmt(v) { return '$' + Number(v).toFixed(2); }
  function pct(num, denom) {
    if (denom <= 0) return 0;
    return Math.max(0, Math.min(100, (num / denom) * 100));
  }

  function renderSim() {
    if (!simA || !simB || !simC) return;
    const a = Number(simA.value);
    let b = Number(simB.value);
    const c = Number(simC.value);
    if (b > a) { b = a; simB.value = String(b); }

    simOut.a.textContent = fmt(a);
    simOut.b.textContent = fmt(b);
    simOut.c.textContent = fmt(c);

    // A's ledger: committed to B is b; remaining is a - b.
    simOut.aMax.textContent   = fmt(a);
    simOut.aDebit.textContent = fmt(b);
    simOut.aRem.textContent   = fmt(a - b);
    simOut.aRem.className = (a - b) >= 0 ? 'good' : 'bad';
    simOut.barA.style.setProperty('--p', pct(b, a) + '%');
    simOut.barA.parentElement.classList.remove('full');

    // B's ledger: sub-budget=b, spent on C=c, overrun if c>b.
    simOut.bMax.textContent   = fmt(b);
    simOut.bDebit.textContent = fmt(c);
    const overrun = c > b;
    simOut.bStatus.textContent = overrun ? 'overrun' : 'ok';
    simOut.bStatus.className   = overrun ? 'bad' : 'good';
    simOut.barB.style.setProperty('--p', pct(c, b) + '%');
    simOut.barB.parentElement.classList.toggle('full', overrun);

    if (overrun) {
      simOut.verdict.className = '';
      simOut.verdict.innerHTML =
        '<strong class="bad">BudgetOverrun</strong> raised against the B→C contract' +
        ' (' + fmt(c) + ' > ' + fmt(b) + ').' +
        '<br/><span class="muted small">A is unaffected. The blame chain points at C.</span>';
    } else {
      simOut.verdict.className = 'ok';
      simOut.verdict.innerHTML =
        '<strong class="good">within budget.</strong> C spent ' + fmt(c) +
        ' of B\'s ' + fmt(b) + ' sub-budget.' +
        '<br/><span class="muted small">A\'s ledger remains at ' + fmt(a - b) + ' uncommitted.</span>';
    }
  }
  [simA, simB, simC].forEach((el) => { if (el) el.addEventListener('input', renderSim); });
  renderSim();

  // ============================================================
  // intersection-observer fade-in for bands
  // ============================================================
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.style.opacity = '1';
            e.target.style.transform = 'translateY(0)';
            io.unobserve(e.target);
          }
        }
      },
      { rootMargin: '-40px 0px' }
    );
    document.querySelectorAll('.band').forEach((el) => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(12px)';
      el.style.transition = 'opacity 500ms ease, transform 500ms ease';
      io.observe(el);
    });
  }
})();
