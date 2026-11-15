# Contributing

Al-Narjis AI is a live site. A merge to `main` deploys to https://karmaai.online.
Work on a branch and open a pull request. Do not push to `main`.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
python -m pytest
```

`python -m pytest` is the command that works. Bare `pytest` can fail to import `src`.

## Rules that already protect production

- Do not write, log, or commit secrets. `.env` stays local.
- Do not invent customers, testimonials, logos, revenue, or review scores.
- Prices, plan names, and the agent count come from `src/services/catalog.py`.
- Public pages are Arabic at `/ar/...` and English at `/en/...`. Use the SEO head
  the other public pages use, and add the path to `src/services/seo.py` so the
  sitemap and hreflang stay in sync.
- Brand colors are black, white, and orange `#FF5A36`.

## Adding a testimonial or a case study

Nothing is shown until a real customer has approved the text.

1. Edit `content/testimonials.json` or `content/case_studies.json`.
2. Each entry is an object. `approved` must be `true`. A testimonial needs `name`
   and `quote` (optional `quote_ar`, `company`). A case study needs `title` and
   `summary` (optional `title_ar`, `summary_ar`, `url`, `sector`).
3. Leave the file as `[]` when there is nothing approved. Do not add a sample name.
4. The home page and the about page render the section only when the loader
   returns a row. There is no admin screen. The owner edits the JSON and ships
   it through a pull request.

## Checks

GitHub Actions runs `python -m pytest` on push to `main` and on pull requests.
The check name is `tests / pytest`. Ruff runs on the platform modules added for
the public pages, and a security job runs `pip-audit` and `bandit` without
blocking the merge.

## Version

The public version is `src/version.py`. The owner tags and publishes GitHub
releases. Do not create the tag from a pull request.
