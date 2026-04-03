# AI_devs 4

Hey! This is a repository for my course of AI_devs 4.

## How to run

First, create `.env` file base one `.env.example`.

Then:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py <mission_number>
deactivate
```

## Code quality

Use `make` for the common checks:

```sh
make lint            # pylint on app/
make test            # all tests (unit + integration)
make test-unit       # unit tests only
make test-integration # integration tests only
```

[Pylint](https://pylint.readthedocs.io/) also runs automatically on every `git push` via a pre-push hook (errors & fatal only). To enable the hook:

```sh
git config core.hooksPath .githooks
```

Pylint and pytest configuration lives in `pyproject.toml`.
