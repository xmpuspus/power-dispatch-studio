# Reporting a security problem

Use GitHub's private vulnerability reporting on this repository:
**Security > Report a vulnerability**. That reaches the maintainer without
opening the report to the public first.

Expect a first reply within seven days.

## What this project is, and what that means for scope

The site is static. It serves prebuilt JSON and GeoJSON, runs the dispatch model
in the visitor's own browser, and keeps no accounts, no sessions, no cookies and
no server-side state. It takes no user input beyond the URL query string, and it
holds no personal data.

In scope:

- Anything that runs code in a visitor's browser from a crafted link, for
  example an injection through `?q=`, `?finding=`, or the scenario fields the
  map reads out of the URL.
- A supply-chain problem in a declared dependency: `highspy` for Python, or the
  packages in `studio/package-lock.json`.
- A path traversal or similar defect in `web/serve.py`, which is a development
  server and is not meant to face the internet.

Out of scope:

- The published market figures. A number you think is wrong is a data issue, so
  open a normal issue instead. Say which figure and where you read it.
- Anything about the upstream publishers' own systems.
