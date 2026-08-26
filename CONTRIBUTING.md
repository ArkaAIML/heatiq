# Contributing to HeatIQ

This document explains the Git workflow we use for HeatIQ.

**Do not develop directly on `main`.** All development should happen on feature branches and enter `main` through Pull Requests.

## 1. First-Time Setup

After accepting the GitHub collaborator invitation, clone the repository:

```bash
git clone <REPOSITORY-URL>
cd heatiq
```

Set up the Python environment:

```bash
uv sync
```

If you're using VS Code, select the project interpreter:

```text
Ctrl + Shift + P
→ Python: Select Interpreter
→ .venv
```

Verify the environment:

```bash
uv run python --version
```

## 2. Before Starting New Work

Always start from an up-to-date `main`:

```bash
git switch main
git pull origin main
```

Never start a new feature from an outdated branch.

## 3. Create a Feature Branch

Create a branch describing the work you're about to do:

```bash
git switch -c feature/<feature-name>
```

Examples:

```bash
git switch -c feature/thermal-indices
git switch -c feature/data-pipeline
git switch -c feature/backend-api
git switch -c feature/frontend-dashboard
git switch -c feature/gis-map
```

Use these branch prefixes:

* `feature/` — new functionality
* `fix/` — bug fixes
* `docs/` — documentation
* `test/` — tests
* `experiment/` — ML experiments

Avoid names such as `my-branch`, `final`, `test123`, or personal names.

Check which branch you're currently on:

```bash
git branch
```

The branch with `*` beside it is your current branch.

## 4. Work on Your Feature

Make your changes normally.

Check what has changed:

```bash
git status
```

Stage the relevant files:

```bash
git add <file>
```

Or, when appropriate:

```bash
git add .
```

Commit your work:

```bash
git commit -m "feat: implement UTCI calculation"
```

Useful commit prefixes:

```text
feat:     new functionality
fix:      bug fix
docs:     documentation
test:     tests
refactor: code restructuring
chore:    project/tooling maintenance
```

Try to make meaningful commits instead of messages such as:

```text
update
stuff
changes
final
final-final
```

## 5. Keep Your Branch Updated

If other Pull Requests have been merged into `main` while you're working, update your local `main`:

```bash
git switch main
git pull origin main
```

Return to your feature branch:

```bash
git switch feature/<feature-name>
```

Bring the latest `main` into your feature branch:

```bash
git merge main
```

If there are merge conflicts, resolve them carefully before continuing.

**Do not merge your feature branch into local `main`.**

The feature will be merged into `main` through a GitHub Pull Request.

## 6. Push Your Feature Branch

The first time you push a new branch:

```bash
git push -u origin feature/<feature-name>
```

For example:

```bash
git push -u origin feature/thermal-indices
```

After the upstream branch has been configured, future pushes can simply use:

```bash
git push
```

## 7. Create a Pull Request

Go to the HeatIQ repository on GitHub.

GitHub will usually show a **Compare & pull request** button after you push your branch.

Create a Pull Request with:

```text
base:    main
compare: feature/<feature-name>
```

In the PR description, briefly explain:

* What you changed
* Why you changed it
* How you tested it
* Anything reviewers should know

Do not merge the PR yourself before the required review.

## 8. Review

At least one teammate must review and approve the Pull Request.

Reviewers should check things such as:

* Does the code work?
* Is the implementation understandable?
* Are files in appropriate folders?
* Are there obvious bugs?
* Were secrets or API keys accidentally committed?
* Were large datasets accidentally committed?
* Does the change break existing functionality?

If a reviewer starts a conversation, resolve it before merging.

## 9. Merge

After approval, merge the Pull Request into `main`.

For most small feature branches, prefer:

```text
Squash and merge
```

This keeps the `main` branch history clean.

## 10. After Your PR Is Merged

Update your local `main`:

```bash
git switch main
git pull origin main
```

Delete the finished local feature branch:

```bash
git branch -d feature/<feature-name>
```

GitHub also provides an option to delete the remote feature branch after merging.

For your next task, create a **new branch from the updated `main`**:

```bash
git switch -c feature/<next-feature>
```

## Important Rules

1. **Never develop directly on `main`.**
2. **Always update `main` before creating a new branch.**
3. **One branch should represent one logical piece of work.**
4. **All changes enter `main` through Pull Requests.**
5. **Never commit `.env`, API keys, passwords, or other secrets.**
6. **Do not commit `.venv/`, large datasets, generated model files, or `node_modules/`.**
7. **Use meaningful branch names and commit messages.**
8. **If you're unsure about a Git operation, ask before force-pushing, resetting, or deleting branches.**

## Quick Reference

```bash
# Start new work
git switch main
git pull origin main
git switch -c feature/my-feature

# Work and commit
git status
git add .
git commit -m "feat: describe what was added"

# Push
git push -u origin feature/my-feature

# Create PR on GitHub:
# feature/my-feature → main

# After PR is reviewed and merged
git switch main
git pull origin main
git branch -d feature/my-feature
```
