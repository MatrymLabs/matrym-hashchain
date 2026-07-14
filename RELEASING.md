# Releasing `matrym-hashchain` to PyPI

Publishing uses **PyPI Trusted Publishing** (OpenID Connect): no API token is ever stored
in the repo or in GitHub secrets. The `Release to PyPI` workflow
(`.github/workflows/release.yml`) builds and publishes automatically when a GitHub Release
is published. The build has already been verified locally (`python -m build` + `twine check`,
both pass) and the name `matrym-hashchain` is available on PyPI.

## One-time setup (on PyPI - about 3 minutes)

1. Create or log in to a PyPI account: <https://pypi.org/account/register/> (enable 2FA).
2. Add a **pending publisher** so the first release can create the project. Go to
   <https://pypi.org/manage/account/publishing/> and under "Add a new pending publisher" enter:
   - **PyPI Project Name:** `matrym-hashchain`
   - **Owner:** `MatrymLabs`
   - **Repository name:** `matrym-hashchain`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
   - Save.
3. (Recommended) In the GitHub repo, create the matching environment: **Settings -> Environments
   -> New environment -> `pypi`**. Optionally add yourself as a required reviewer, so every
   publish waits for a one-click approval.

## Cutting a release (each version)

1. Confirm the version matches in all three places: `version` in `pyproject.toml`,
   `__version__` in `src/hashchain/__init__.py`, and the top entry of `CHANGELOG.md`.
2. Create the GitHub Release (this is the trigger):

   ```bash
   gh release create v0.1.0 --title "v0.1.0" --notes "First public release."
   ```

   (or GitHub UI: Releases -> Draft a new release -> tag `v0.1.0` -> Publish).
3. Watch the `Release to PyPI` workflow: `gh run watch` (or the Actions tab). If you added a
   required reviewer to the `pypi` environment, approve the publish job when prompted.
4. Verify (give PyPI a minute to index):

   ```bash
   pip install matrym-hashchain
   ```

After the first successful publish the "pending" publisher becomes a normal trusted publisher
and the project exists on PyPI. Bumping a future version is just steps 1-4 again with a new tag.

## Why trusted publishing (not an API token)

No long-lived secret to leak, rotate, or accidentally commit. The workflow proves its identity
to PyPI via short-lived OIDC, scoped to this exact repo + workflow + environment - which matches
the fleet's "secrets never enter git" discipline. A stored PyPI API token would be the weaker,
riskier alternative.
