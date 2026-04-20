# Release Process

This document outlines the critical steps for releasing new versions of the HA Config Git Sync integration. **Follow this checklist exactly to prevent deployment issues.**

## Pre-Release Checklist (MUST DO BEFORE TAGGING)

### 1. Update `manifest.json` Version ⚠️ CRITICAL
Before creating any release tag, the `manifest.json` file **MUST** be updated to match the version being released.

**File:** `custom_components/ha_config_git_sync/manifest.json`

```json
{
  "version": "1.9.2"  // ← Update this FIRST, before tagging
}
```

**Why this is critical:**
- Home Assistant reads the version from `manifest.json` to determine if an update is available
- If manifest version ≠ release tag version, users will see stale version numbers in the UI
- This causes confusion about which version is actually installed

**What NOT to do:**
- ❌ Tag the release FIRST, then update the manifest
- ❌ Update the manifest AFTER creating the tag
- ❌ Assume the manifest is already updated

### 2. Update `CHANGELOG.md`
Add a new entry at the top with the version, date, and all changes.

**Format:**
```markdown
## [X.Y.Z] — YYYY-MM-DD

### Added
- Feature 1
- Feature 2

### Fixed
- Bug 1
- Bug 2

### Changed
- Change 1
```

### 3. Run Full Test Suite
```bash
pytest tests/ -v
```
Ensure all tests pass before proceeding.

### 4. Commit Changes
Commit the manifest and changelog updates:
```bash
git add custom_components/ha_config_git_sync/manifest.json CHANGELOG.md
git commit -m "Release v1.9.2"
```

### 5. Push to Main Branch
```bash
git push origin main
```

## Release Tag Creation (ONLY AFTER ABOVE STEPS)

Once the manifest is updated and committed, create the release tag:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z: Description of changes"
git push origin vX.Y.Z
```

**Example:**
```bash
git tag -a v1.9.2 -m "Release v1.9.2: Automatic config backup

Features:
- Automatic tar.gz backup before git pull
- Intelligent backup cleanup
- File-level recovery mechanism"

git push origin v1.9.2
```

## GitHub Release (Manual)

1. Go to [Releases](https://github.com/ongas/ha-config-git-sync/releases)
2. Click "Draft a new release"
3. Select the tag you just created
4. Copy the changelog entry as the release notes
5. Click "Publish release"

## Post-Release Verification

### Verify manifest in Release Tag
```bash
git show vX.Y.Z:custom_components/ha_config_git_sync/manifest.json | grep version
```

This should show the correct version matching the tag.

### Verify HACS Update Detection
- After release is published, HACS should detect the new version within 24 hours
- Home Assistant installations see the update available in Settings → System → Updates

### Verify Installations
- Test that existing installations see the version bump in the UI
- Confirm the integration updates correctly from HACS

## Common Mistakes to Avoid

| Mistake | Impact | Solution |
|---------|--------|----------|
| Tagging BEFORE updating manifest.json | Users see old version in UI after update | Always update manifest.json first, then tag |
| Manifest version ≠ tag version | Confusion about installed version | Ensure manifest matches release tag exactly |
| Forgetting to push the tag | Release not available to users | Run `git push origin vX.Y.Z` after tagging |
| Updating manifest but forgetting to commit | Tag points to wrong commit | Commit manifest changes before tagging |
| Multiple commits without version bump | Release contains outdated code | Tag immediately after manifest update |

## Automated Safety Check (Future Enhancement)

Consider adding a pre-commit hook to prevent pushing without manifest update:

```bash
#!/bin/bash
# .git/hooks/pre-commit

VERSION_IN_MANIFEST=$(grep -oP '"version":\s*"\K[^"]+' custom_components/ha_config_git_sync/manifest.json)
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)

if [[ $VERSION_IN_MANIFEST == $LAST_TAG ]]; then
  echo "ERROR: manifest.json version matches last tag. Did you forget to bump the version?"
  exit 1
fi
```

## Deployment Timeline for HA Prod

Once released on GitHub:

1. **Hours 0-24**: HACS discovers the release
2. **Hours 24+**: Users see update available in HA Settings
3. **User-triggered**: Installation on user systems (including HA Prod)

To deploy to HA Prod immediately:
- Pull latest from GitHub in HA Prod's config directory: `git pull origin main`
- Or manually update to the release tag: `git checkout vX.Y.Z`

## Example: v1.9.2 Release (What Happened)

**What went wrong:**
1. Code was committed with backup features (fa16da0)
2. Release tag v1.9.2 was created pointing to code WITHOUT manifest update
3. Manifest.json still showed version "1.8.0" in the release
4. HA Prod deployed v1.9.2 code but manifest said 1.8.0
5. UI showed outdated version number, HACS didn't recognize the update

**How it was fixed:**
1. Updated manifest.json to "1.9.2"
2. Committed the fix (b50cc2b)
3. Force-updated the v1.9.2 tag to point to the fixed commit
4. HA Prod now correctly sees version 1.9.2

**Lesson:**
The manifest.json version is the **single source of truth** for version numbers in Home Assistant. Never tag a release without ensuring the manifest matches the release version.
