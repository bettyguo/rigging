# Deploying the live site

> The live site at <https://bettyguo.github.io/rigging/> auto-deploys
> from [`site/`](./site/) via [`.github/workflows/pages.yml`](.github/workflows/pages.yml).
> No build step. No external dependencies.

The repo ships with `enablement: true` on the `actions/configure-pages`
step, which means the **first time the workflow runs successfully it will
auto-create the GitHub Pages site** with `source = GitHub Actions`. You
do not have to flip a setting in the repo Settings UI manually.

---

## TL;DR — three commands

```bash
# 1. Make sure everything is pushed.
git push origin main

# 2. Manually trigger the workflow once (the first time). Pick one:
#    a) via the GitHub UI:      Repo → Actions → "pages" → Run workflow
#    b) via the GitHub CLI:     gh workflow run pages.yml
#
# 3. Wait ~60–90 seconds. The site comes up at:
#    https://bettyguo.github.io/rigging/
```

If you would rather the deploy be entirely passive: any further push to
`main` will redeploy automatically.

---

## Why the URL was 404'ing

Until the `pages` workflow runs successfully **once**, GitHub Pages is
not configured for the repo, and `https://bettyguo.github.io/rigging/`
serves 404. The fix is to run the workflow once — that's it. The
workflow's `enablement: true` setting will create the Pages site on its
first successful run.

You can verify Pages is configured at
[Settings → Pages](https://github.com/bettyguo/rigging/settings/pages).
After the first successful deploy, the page should report:

> *Your site is live at <https://bettyguo.github.io/rigging/>*
> *Source: GitHub Actions*

---

## What gets deployed

The Pages workflow uploads the entire `site/` directory as a Pages
artifact and deploys it:

```
site/
├── index.html          # Landing page + interactive blame-chain explorer
├── cheatsheet.html     # Printable one-page reference
├── styles.css
├── script.js
└── assets/             # SVG hero, diagrams, brand, favicon, OG image
```

No bundler. No transpiler. No node_modules. Pure static HTML/CSS/JS.

---

## Iterating locally

The site is just static files; any HTTP server will do.

```bash
cd site && python -m http.server 8080
# then open http://localhost:8080
```

Make a change, refresh. No watch process needed.

---

## Auditing internal links before pushing

The repo ships with [`scripts/audit_links.py`](./scripts/audit_links.py),
which scans every Markdown and HTML file for broken internal references.
It runs in CI on every PR. Run it locally with:

```bash
python scripts/audit_links.py --strict
```

`--strict` also verifies that every `…#fragment` anchor resolves to an
actual heading in the target Markdown file. Exits non-zero if anything
breaks.

---

## Troubleshooting

### Workflow ran but the site is still 404

Two reasons this happens:

1. **The workflow failed.** Check the Actions tab → most recent run of
   `pages`. The `Setup Pages` step needs `permissions: pages: write`
   (already set) **and** an admin-class token. If your org has
   restricted workflow tokens, you may need to allow `pages: write`
   under Settings → Actions → General → *Workflow permissions*.
2. **DNS cache.** GitHub's edge sometimes lags. Try the URL in a
   private window or curl it directly:
   ```bash
   curl -I https://bettyguo.github.io/rigging/
   ```

### "Resource not accessible by integration" on configure-pages

This means the workflow's token doesn't have permission to enable
Pages. Two fixes:

- **Recommended:** Repo Settings → Actions → General → Workflow
  permissions → *Read and write permissions* + check "Allow GitHub
  Actions to create and approve pull requests".
- **Manual fallback:** Repo Settings → Pages → Source: *GitHub
  Actions*. After this, the workflow no longer needs to create the
  site, just push to it.

### I changed something and the site didn't update

The workflow runs on every push to `main` (no path filter). If it did
not run, check Actions → Workflows → make sure `pages` is not disabled.

To manually redeploy without committing:

```bash
gh workflow run pages.yml      # via gh CLI
# OR: Actions tab → pages → Run workflow
```

---

## Customising the site

- **Brand colours / typography** — see CSS custom properties at the top
  of [`site/styles.css`](./site/styles.css).
- **Interactive scenarios** — the blame-chain explorer's scenarios are
  defined in `SCENARIOS = { … }` at the top of [`site/script.js`](./site/script.js).
- **Hero image / OG card** — [`site/assets/hero.svg`](./site/assets/hero.svg)
  and [`site/assets/og.svg`](./site/assets/og.svg).

The site is intentionally low-tech so that any contributor can read and
modify it without learning a stack.

---

## Why no `gh-pages` branch?

GitHub's *Deploy from a branch* mode supports only `/` or `/docs` as the
publish directory. We use `docs/` for documentation, not for the site.
The Actions-based deploy lets us publish from `site/` without renaming.

If you have a strong reason to use the branch-based deploy, you can:

1. Settings → Pages → Source: *Deploy from a branch* → `main` → `/docs`.
2. Set up a workflow (or pre-commit hook) that mirrors `site/` → `docs/site/`.
3. Delete `.github/workflows/pages.yml`.

We do not recommend this. The Actions deploy is simpler.
