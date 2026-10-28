# Publishing QRYVANTA to GitHub

This folder is the GitHub-ready source tree. It includes the application source, offline study documents, tests, PyInstaller configuration, and the Inno Setup script. Do not commit installers, build output, credentials, `.env` files, or local database files.

## 1. Create the GitHub repository

On GitHub, create a new repository named `QRYVANTA`. To publish the source, choose Public or Private according to your preference. For the first push, create it **without** a README, `.gitignore`, or license file because this project already has a README and `.gitignore`.

## 2. Open PowerShell in this project folder

Replace the URL below with the URL copied from your own GitHub repository:

```powershell
git init
git branch -M main
git add .
git status --short
```

Before committing, verify the staged list contains no `.env`, private key/certificate, local database, user connection settings, `dist/`, `build/`, or installer output. The project `.gitignore` excludes common secret and build paths; still review the staged files manually.

Set your own commit identity if Git asks for it, then commit and push:

```powershell
git config user.name "YOUR NAME"
git config user.email "YOUR GITHUB-VERIFIED EMAIL"
git commit -m "Prepare QRYVANTA 1.1.0 offline learning and installer"
git remote add origin https://github.com/YOUR-USERNAME/QRYVANTA.git
git push -u origin main
```

Use Git Credential Manager or GitHub's supported authentication flow when Git prompts you. Do not place a personal access token in the repository, a command checked into a script, or a chat message.

If `origin` already exists, inspect it with `git remote -v` instead of adding a second remote. If the repository already contains commits, fetch and integrate those commits before pushing rather than forcing an overwrite.

## License note

No license has been added because the project owner must choose the reuse terms. Making a repository public does not, by itself, grant a general license to reuse, modify, or redistribute its code. Choose and add a license before presenting it as open-source software.
