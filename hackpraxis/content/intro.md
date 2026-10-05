# Welcome to HackPraxis

HackPraxis turns web application testing into a guided learning loop. For every
action you take, it shows you the **exact command** being run, **explains each
flag**, and gives you a **Learn** panel on the technique — so you understand the
*why*, not just the *what*, while you work a real target.

## The one rule: scope
HackPraxis will not send a request to any host that isn't on your active project's
**in-scope** list. This is enforced on the server, not just hidden in the UI.
Before you can run anything, create a project and define scope:

- **In scope** — the hosts you are authorized to test. One per line. Use
  `*.example.com` for subdomains, `example.com` for the apex (list both if you
  need both).
- **Out of scope** — hosts you must *not* touch. Out-of-scope always wins.

This isn't bureaucracy. Testing a system you don't have permission to test can
be a crime (in the US, the Computer Fraud and Abuse Act). In bug bounties, the
program's scope page *is* your authorization — copy it in here exactly.

## A sane workflow
1. **Project & scope** — paste the program's in/out-of-scope lists.
2. **Enumeration** — fingerprint with httpx, then discover content with
   ffuf/gobuster. Note anything `401`/`403`.
3. **401/403 Bypass** — take those protected endpoints and run the matrix.
4. **Path Traversal** — test file-handling parameters.
5. **Confirm by hand** — every automated "hit" is a lead. Re-run the exact
   command, read the real response, and only then call it a finding.

## What HackPraxis is and isn't
- It **wraps tools you install yourself** (ffuf, gobuster, httpx, curl). It does
  not ship exploits or attack anything on its own.
- It's a **learning and testing console**, not an autopilot. You choose the
  target, the technique, and when to stop.
- Findings are only as good as your permission to look for them. Stay in scope.
