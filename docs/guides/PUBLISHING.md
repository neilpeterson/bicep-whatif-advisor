# Publishing to PyPI

This guide covers how to publish `bicep-whatif-advisor` to PyPI using automated GitHub Actions workflows with Trusted Publishers.

## One-Time Setup

### 1. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Create an account and verify your email
3. **Enable 2FA** (required for trusted publishers)

### 2. Create TestPyPI Account (Optional but Recommended)

1. Go to https://test.pypi.org/account/register/
2. Create a separate account (TestPyPI is independent from PyPI)
3. Enable 2FA

### 3. Configure Trusted Publishers on PyPI

This allows GitHub Actions to publish without storing API tokens.

**For PyPI (production):**

1. Go to https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill in:
   - **PyPI Project Name:** `bicep-whatif-advisor`
   - **Owner:** `neilpeterson` (your GitHub username)
   - **Repository:** `bicep-whatif-advisor`
   - **Workflow name:** `publish-pypi.yml`
   - **Environment name:** `pypi`
4. Click "Add"

**For TestPyPI (testing):**

1. Go to https://test.pypi.org/manage/account/publishing/
2. Same steps as above but use environment name: `testpypi`

### 4. Configure GitHub Environments

1. Go to your GitHub repo → Settings → Environments
2. Create environment named `pypi`:
   - No protection rules needed (optional: add reviewers for manual approval)
3. Create environment named `testpypi`:
   - Same settings

## Publishing Process

### Method 1: Automated via GitHub Release (Recommended)

This is the standard workflow for production releases.

**Steps:**

1. **Update version in `pyproject.toml`:**
   ```bash
   # Edit pyproject.toml
   version = "1.0.1"  # Increment version
   ```

2. **Commit and push version bump:**
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 1.0.1"
   git push origin main
   ```

3. **Create a Git tag:**
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

4. **Create GitHub Release:**
   - Go to https://github.com/neilpeterson/bicep-whatif-advisor/releases/new
   - Select tag: `v1.0.1`
   - Release title: `v1.0.1`
   - Add release notes describing changes
   - Click "Publish release"

5. **GitHub Actions will automatically:**
   - Build the package
   - Publish to PyPI
   - Available at https://pypi.org/project/bicep-whatif-advisor/

**Verify installation:**
```bash
pip install bicep-whatif-advisor[anthropic]
bicep-whatif-advisor --version
```

### Method 2: Test with TestPyPI First

Before publishing to production PyPI, test with TestPyPI.

**Steps:**

1. Go to GitHub Actions → "Publish to PyPI" workflow
2. Click "Run workflow" → "Run workflow" (manual trigger)
3. This publishes to TestPyPI only

**Test the TestPyPI package:**
```bash
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  bicep-whatif-advisor[anthropic]
```

Note: TestPyPI doesn't have all dependencies, so we use `--extra-index-url` to pull dependencies from production PyPI.

### Method 3: Manual Publishing (Backup)

If GitHub Actions is unavailable, publish manually.

**Steps:**

1. **Install build tools:**
   ```bash
   pip install build twine
   ```

2. **Build the package:**
   ```bash
   python -m build
   ```

   This creates:
   - `dist/bicep_whatif_advisor-1.0.0-py3-none-any.whl`
   - `dist/bicep_whatif_advisor-1.0.0.tar.gz`

3. **Upload to PyPI:**
   ```bash
   twine upload dist/*
   ```

   You'll be prompted for:
   - Username: `__token__`
   - Password: (your PyPI API token)

**To create a PyPI API token:**
- Go to https://pypi.org/manage/account/token/
- Click "Add API token"
- Name: "bicep-whatif-advisor manual upload"
- Scope: "Project: bicep-whatif-advisor"
- Copy token (starts with `pypi-`)

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (1.0.0 → 2.0.0): Breaking changes
- **Minor** (1.0.0 → 1.1.0): New features, backward compatible
- **Patch** (1.0.0 → 1.0.1): Bug fixes, backward compatible

## Pre-release Versions

For alpha/beta releases:

```toml
# pyproject.toml
version = "1.1.0a1"  # Alpha
version = "1.1.0b1"  # Beta
version = "1.1.0rc1" # Release candidate
```

Users can install with:
```bash
pip install --pre bicep-whatif-advisor[anthropic]
```

## Troubleshooting

### "Project name is already taken"

The name `bicep-whatif-advisor` is unique. If taken, this means:
1. You already published it (check https://pypi.org/project/bicep-whatif-advisor/)
2. Someone else published first (rename your package)

### "Trusted publisher mismatch"

Check that:
- Workflow file is exactly `.github/workflows/publish-pypi.yml`
- Repository owner/name matches PyPI configuration
- Environment name is exactly `pypi` or `testpypi`

### "Version already exists"

PyPI doesn't allow re-uploading the same version. You must:
1. Increment version in `pyproject.toml`
2. Create new release

### Build fails

Clean build artifacts:
```bash
rm -rf dist/ build/ *.egg-info
python -m build
```

## Post-Publication Checklist

After publishing:

- [ ] Verify package appears on PyPI: https://pypi.org/project/bicep-whatif-advisor/
- [ ] Test installation: `pip install bicep-whatif-advisor[anthropic]`
- [ ] Test CLI: `bicep-whatif-advisor --version`
- [ ] Update README badges (optional)
- [ ] Announce release (GitHub, Twitter, etc.)

## Package Metadata

Current metadata (from `pyproject.toml`):

- **Name:** bicep-whatif-advisor
- **Version:** 1.0.0
- **License:** MIT
- **Python:** >=3.8
- **Homepage:** https://github.com/neilpeterson/bicep-whatif-advisor
- **Issues:** https://github.com/neilpeterson/bicep-whatif-advisor/issues

## Support

For PyPI-specific questions:
- PyPI Help: https://pypi.org/help/
- Packaging Guide: https://packaging.python.org/
- Trusted Publishers: https://docs.pypi.org/trusted-publishers/
