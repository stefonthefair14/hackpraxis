# Path Traversal

## What it is
Path (directory) traversal happens when an application builds a file path from
user input without properly containing it, so input like `../../../etc/passwd`
climbs out of the intended directory and reads arbitrary files. It shows up
anywhere a parameter names a file: `?file=`, `?page=`, `?template=`,
`?download=`, image loaders, language/locale selectors, PDF generators.

## Mark the injection point
Put the `FUZZ` keyword where the filename goes:
`https://target/download?file=FUZZ`. HackPraxis substitutes each payload there. If
you also set a **Target file** (e.g. `etc/passwd`), the traversal *prefixes*
(`../../../`) get that file appended automatically.

## Why the encodings exist
A naive filter blocks the literal string `../`. Attackers answer with the same
sequence wearing a disguise the filter doesn't recognise but the filesystem
still does once it's decoded:

- **URL-encoded**: `%2e%2e%2f` = `../`. The web server decodes it before the app
  sees it.
- **Double-encoded**: `%252e%252e%252f`. If something decodes twice (proxy, then
  app), this becomes `../` late in the pipeline, after the filter already passed
  it.
- **Overlong UTF-8 / illegal unicode**: `%c0%ae`, `%c0%af`, `..%u2215`. Older or
  permissive decoders accept non-canonical encodings of `.` and `/`.
- **Nested / strip-once**: `....//`, `..././`. If a filter removes `../` exactly
  once, the leftovers collapse back into `../`.
- **Reverse-proxy path param**: `..;/`. Some servers treat `;` segments
  specially, letting the climb survive proxy normalisation.
- **Null byte / truncation**: `...%00.png`. On old stacks the `%00` ends the
  string, defeating an appended extension.

Different payloads beat different defences, which is why the list is long: you
are probing *which* decoder sits where in the request pipeline.

## How to read the results
- **ffuf mode** (recommended) only shows a hit when the response body matches the
  success regex — by default `root:.*:0:0:`, the shape of the first line of a
  Unix `passwd` file. If you target a different file, change the regex to
  something unique to that file's contents.
- **curl mode** shows status and size per payload. A payload that returns a
  much larger body, or a `200` where siblings `404`, is worth opening by hand.
- Confirm a real read by looking at the actual content. A reflected error that
  merely *contains* your path is not a file read.

## If it reads a file
Escalate thoughtfully and only within scope:
- Config files (`.env`, `web.config`, `application.properties`) often hold
  credentials and are higher-impact proof than `/etc/passwd`.
- `/proc/self/environ` and `/proc/self/cmdline` can reveal secrets passed as
  environment variables.
On Windows, swap to `..\` and targets like `windows\win.ini`.

## Pitfalls
- Depth matters. You rarely know how deep the file root is, so the list sweeps
  1–8 levels; too few `../` and you never reach `/`.
- Some apps canonicalise correctly — a clean `404`/`400` across the whole list is
  a perfectly normal (secure) result. Note it and move on.
- Reading files is the ceiling of impact here; do not pivot to writing or code
  execution unless the program's scope explicitly allows it.
