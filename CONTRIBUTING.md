# Contributing to FarmBreath AI

Thanks for your interest in contributing. This project started as a Samsung Solve for Tomorrow hackathon submission, so the workflow below is intentionally lightweight rather than a full enterprise process.

## Getting Set Up

1. Fork the repository and clone your fork locally.
2. Follow the [Installation](./README.md#installation) steps in the README to set up your virtual environment and install dependencies.
3. Run the dashboard locally with `streamlit run dashboard/app.py` to confirm everything works before making changes.

## Making Changes

1. Create a new branch for your change:
   ```bash
   git checkout -b fix/short-description
   ```
2. Make your changes. Keep commits focused — one logical change per commit where possible.
3. Test your change locally by actually running the dashboard and confirming the affected feature works as expected. There is currently no automated test suite, so manual verification matters.
4. Follow standard Python style (PEP 8). If you're adding a new function, a short docstring explaining what it does is appreciated.

## Submitting a Pull Request

1. Push your branch to your fork.
2. Open a pull request against the `main` branch of this repository.
3. In the PR description, briefly explain:
   - What the change does
   - Why it's needed
   - How you tested it (e.g. "ran the dashboard locally with date set to October and confirmed the banner updates")
4. Be responsive to review feedback — this is a small project, so review turnaround is usually quick.

## Reporting Bugs or Suggesting Features

Open a GitHub issue describing:
- What you expected to happen
- What actually happened (include the full error traceback if there's a crash)
- Steps to reproduce, if applicable

## Code of Conduct

Be respectful and constructive. This is a student project built under hackathon time pressure — patience and clear communication go a long way.
