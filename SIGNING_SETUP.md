# Code Signing Setup for Auto-Updates

## Current Status
Version 2.0.4 has auto-updates implemented but not code-signed yet.

## SignPath.io Free Code Signing (Recommended)

### Step 1: Apply for Free OSS Plan
1. Go to: https://about.signpath.io/product/open-source
2. Fill out the application form:
   - **Project Name**: Event & Sales Manager
   - **Repository**: https://github.com/mattgrilli/event
   - **Description**: Event ticketing and sales management for PTAs
   - **License**: MIT (make sure LICENSE file exists in repo)
3. Wait for approval (usually 1-2 business days)

### Step 2: After Approval - Configure SignPath

Once approved, you'll receive:
- Organization ID
- API Token
- Project configuration instructions

Add these as GitHub Secrets:
1. Go to: https://github.com/mattgrilli/event/settings/secrets/actions
2. Add secrets:
   - `SIGNPATH_API_TOKEN` - Your API token from SignPath
   - `SIGNPATH_ORGANIZATION_ID` - Your org ID from SignPath

### Step 3: Configure SignPath Project

In SignPath dashboard:
1. Create a new project called "event-sales-manager"
2. Create signing policy called "release-signing"
3. Set artifact configuration to handle `.exe` files
4. Link to your GitHub repository

### Step 4: Enable Signing in GitHub Actions

Uncomment the SignPath signing step in `.github/workflows/release.yml`

## Using the Automated Release Workflow

Once SignPath is configured:

1. **Update version** in `package.json` and `src/renderer/index.html`
2. **Commit changes**: `git add . && git commit -m "Release v2.0.5"`
3. **Create tag**: `git tag v2.0.5`
4. **Push with tags**: `git push && git push --tags`

GitHub Actions will automatically:
- Build the app
- Submit to SignPath for signing
- Create GitHub release
- Upload signed `.exe` and `latest.yml`

## Testing Updates

After publishing a signed release:
1. Install the previous version on another machine
2. App will detect new version automatically
3. Download in-app
4. Install automatically (no signature errors!)

## Temporary Solution (Until SignPath Approved)

For now, users can:
1. See update notification
2. Click to download from GitHub
3. Manually install

The download/install buttons will show helpful error messages about manual installation.

## Alternative: Purchase Certificate

If SignPath application is rejected or you need immediate signing:
- **DigiCert**: ~$500/year for EV certificate
- **Sectigo**: ~$200/year for standard certificate

Store certificate as:
- File: Not committed to git (in .gitignore)
- Password: As environment variable or GitHub secret
