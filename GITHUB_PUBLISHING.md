# Publishing QRYVANTA to GitHub

Target repository: `https://github.com/sabyapradhan01/QRYVanta.git`

This repository handoff is prepared on branch `main` with a local commit. To push it from Windows:

1. Extract the complete repository ZIP, including the hidden `.git` directory. Do not extract it into a project folder that already contains another Git repository.
2. Open the extracted project folder and review `git status --short --branch`.
3. Run `PUSH_TO_GITHUB.bat`, or use `git push -u origin main` in a terminal. Git may open its normal credential manager/browser sign-in flow.
4. Confirm the remote repo has no unrelated commits first. If it already contains a README, license, or other commit, fetch and integrate that history before pushing; do not force-push over it.

The project `.gitignore` excludes environment files, common secret/key files, local databases, Python caches, build output, installer output, archives, and logs. Review the staged/committed file list before publication nonetheless.

## Optional assets

These paths are referenced by the UI but were not present in the source ZIP available for this handoff:

- `assets/learn.mp4`
- `assets/Dev1.jpg`
- `assets/Dev2.jpg`
- `assets/fac.jpg`

Copy the approved original media into those paths before pushing if they should be public and included in the offline installer. If `learn.mp4` exceeds GitHub's regular per-file limit, use Git LFS or another distribution channel. Do not use screenshots as substitutes for the original photo files.

## License

No license was added because the project owner needs to choose reuse and redistribution terms.
