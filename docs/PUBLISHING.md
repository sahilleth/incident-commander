# Publishing to PyPI

Your PyPI **trusted publisher** is configured as **pending** until the first successful upload from GitHub Actions.

| PyPI setting | Value |
|--------------|--------|
| Project | `incident-commander` |
| Publisher | GitHub |
| Repository | `sahilleth/incident-commander` |
| Workflow | `publish.yml` |
| Environment | Any |

## 1. Push the repo to GitHub

```bash
cd /path/to/incident-commander
git init
git add .
git status   # confirm .env is NOT listed

git commit -m "Initial release v0.1.0"
git branch -M main
git remote add origin https://github.com/sahilleth/incident-commander.git
git push -u origin main
```

## 2. Run the publish workflow

**Option A — Manual (fastest)**

1. Open [Actions → Publish to PyPI](https://github.com/sahilleth/incident-commander/actions/workflows/publish.yml)
2. **Run workflow** → branch `main` → Run

**Option B — GitHub Release**

1. [Create a new release](https://github.com/sahilleth/incident-commander/releases/new)
2. Tag: `v0.1.0`, title `v0.1.0`
3. Publish release → workflow runs automatically

**Option C — Git tag push**

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 3. Confirm on PyPI

After the workflow succeeds:

- Pending publisher becomes an **active** trusted publisher
- Package appears at https://pypi.org/project/incident-commander/
- README PyPI badge turns green

```bash
pip install incident-commander
incident-commander eval
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Workflow not listed on PyPI | Ensure `publish.yml` is on `main` and filename matches exactly |
| `403` from PyPI | Trusted publisher repo/workflow name must match; re-check pending publisher details |
| Package version exists | Bump `version` in `pyproject.toml` before re-publishing |

Manual token upload (alternative): `PYPI_API_TOKEN=pypi-... make publish`
