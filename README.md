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

[Pylint](https://pylint.readthedocs.io/) runs automatically on every `git push` via a pre-push hook (errors & fatal only). To enable the hook:

```sh
git config core.hooksPath .githooks
```

To run pylint manually:

```sh
.venv/bin/pylint app/ services/ missions/ config.py main.py
```

Configuration lives in `pyproject.toml`.
