# Contributing to Commander Owl

Thanks for helping out. Commander Owl is deliberately small: standard library only, no build step, no frameworks.

## Ground rules

- **No new dependencies** unless the feature cannot reasonably be built without one. Discuss it in an issue first.
- **Keep the power actions safe.** Any change touching `execute()`, `fire()` or `cancel()` in `server.py` needs a dry-run test (`Dry run` toggle on) and a note in the pull request describing the test.
- **Never commit `state.json`** or anything containing prompts, transcripts or paths from your own machine.
- **Match the existing style:** plain functions, short comments only where the reason is not obvious.

## Running locally

```bash
python server.py     # engine + dashboard on http://127.0.0.1:47821/
```

Turn on **dry run** in the header before testing rules that would power the machine off.

## Pull requests

1. Open an issue for anything larger than a bug fix.
2. Describe what you changed and how you tested it.
3. Keep unrelated changes out of the same pull request.

## Reporting bugs

Include your Windows version, Python version, the relevant lines from the Activity log in the dashboard, and whether dry run was on.
