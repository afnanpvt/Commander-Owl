# Security Policy

Commander Owl can shut down, hibernate, sleep or lock the machine it runs on, so security reports matter.

## What it protects against

- **Other websites:** the dashboard only accepts requests whose `Host` header is `127.0.0.1:47821` or `localhost:47821`, and every write needs the custom `X-HHUB` header. A browser cannot send that header cross-site without a CORS preflight, which the server does not allow.
- **Network access:** the server binds to `127.0.0.1` only. It is not reachable from other machines on your network.

## What it does not protect against

- **Other programs on your machine.** Any process running as your user can send the same local request, including the `X-HHUB` header, and trigger a power action. Treat anything running as you as trusted.
- **Your prompts on disk.** `state.json` stores recent prompts and conversation titles in plain text. It is excluded from git. Anyone with access to your user profile can read it.

## Supported versions

Only the latest commit on `master` receives fixes.

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability reporting on this repository (Security tab, then "Report a vulnerability"). Include the steps to reproduce, your Windows and Python versions, and whether a power action could be triggered without your input.

You can expect an acknowledgement within 7 days.
