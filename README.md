# HackPraxis

**The only way to learn is to try.**

HackPraxis is a learning-first console for **authorized** web application testing.
It puts a clean local GUI in front of the command-line tools bug bounty hunters
already use — ffuf and curl — and does one thing those tools
don't: for every action, it shows you the **exact command being run**,
**explains each flag**, and gives you a **Learn** panel on the technique. You
learn the *why* while you work a real, in-scope target.

It runs entirely on your machine at `http://127.0.0.1:7337`.

> ⚖️ **Authorized testing only.** HackPraxis refuses to send a request to any host
> that isn't in your active project's scope — the gate is enforced server-side,
> not just hidden in the UI. Testing systems you don't have permission to test
> is illegal in most jurisdictions (in the US, the Computer Fraud and Abuse
> Act). Use this on your own systems, deliberately vulnerable labs, or targets
> explicitly in a bug bounty program's scope.

---

## Quick start

```bash
git clone https://github.com/<you>/hackpraxis.git
chmod +x hackpraxis/setup.sh    # make the installer executable
./hackpraxis/setup.sh           # moves the folder to /opt/hackpraxis, installs a venv + the `hackpraxis` command
hackpraxis                      # launches and opens http://127.0.0.1:7337
```

`setup.sh` **moves** the folder to `/opt/hackpraxis` (the standard place for
installed tools), builds an isolated virtual environment inside it, and drops a
launcher at `/usr/bin/hackpraxis` so you start it with a single word:

```
 _   _            _    ____                 _
| | | | __ _  ___| | _|  _ \ _ __ __ ___  _(_)___
| |_| |/ _` |/ __| |/ / |_) | '__/ _` \ \/ / / __|
|  _  | (_| | (__|   <|  __/| | | (_| |>  <| \__ \
|_| |_|\__,_|\___|_|\_\_|   |_|  \__,_/_/\_\_|___/

   The only way to learn is to try
```

Because it uses a venv, HackPraxis **never touches your system Python** — so you
won't see the `externally-managed-environment` pip error that trips people up on
modern Debian/Ubuntu/Fedora.

> Prefer not to install system-wide? Just run it from the checkout:
> ```bash
> python3 -m venv .venv && . .venv/bin/activate
> pip install .
> hackpraxis            # or: python -m hackpraxis
> ```

To remove it later: `./uninstall.sh` (add `--purge` to delete saved projects too).

### Where your data lives
Projects and scopes are saved to **`/opt/hackpraxis/data`** — deliberately *not*
your home directory — so they persist across restarts and reinstalls. Override
the location with the `HACKPRAXIS_HOME` environment variable. The launcher sets it
for you; running from a source checkout falls back to `./.hackpraxis-data`.

---

## The security tools (you install these yourself)

HackPraxis **orchestrates** two tools; it does not bundle them. The sidebar shows
which are found on your `PATH`.

| Tool | Used by | Install |
| --- | --- | --- |
| **ffuf** | Enumeration, Path Traversal | `go install github.com/ffuf/ffuf/v2@latest` · `brew install ffuf` · `apt install ffuf` |
| **curl** | Bypass, Path Traversal, XSS, SQLi (manual) | Pre-installed on macOS/Linux. |
| **sqlmap** | SQL Injection (sqlmap engine) | `pipx install sqlmap` · `brew install sqlmap` · `apt install sqlmap` |

Bigger wordlists (recommended) come from
[SecLists](https://github.com/danielmiessler/SecLists); point the wordlist field
at any file you like. See [`docs/tools.md`](docs/tools.md) for detail.

---

## Modules

The workflow is three steps, and each one whittles the target set down for the
next: enumeration finds URLs, the bypass step gets through the forbidden ones,
and the injection step tests what's reachable.

| Step | Module | What it does | Engine |
| --- | --- | --- | --- |
| 1 | **Enumeration** | Discover paths/files with ffuf; results group by status in the GUI | `ffuf` |
| 2 | **401/403 Bypass** | Replay every forbidden endpoint through header/path/method tricks; wins are saved to the project | `curl` |
| 3 | **Injection → Path Traversal** | Fuzz traversal payloads into a `FUZZ` point and surface a file read | `ffuf` · `curl` |
| 3 | **Injection → SQL Injection** | Drive sqlmap (command built + explained) or send manual payloads; try it live in an embedded iframe | `sqlmap` · `curl` |
| 3 | **Injection → XSS** | Sweep for unescaped reflection, and try payloads by hand in the embedded iframe | `curl` |

### The reachable pool
Every URL that responds (2xx/3xx from enumeration, plus every endpoint the bypass
step gets through) is saved to `reachable.txt` in the project folder. The
injection steps read that pool into a type-ahead target dropdown, so you pick a
real URL (including one that only works *with* a bypass) instead of retyping it.

Enumeration uses one tool on purpose: learn ffuf well rather than five tools
shallowly. Other enumerators (gobuster, httpx, feroxbuster, dirsearch) are
covered in the module's Learn tab.

### Scan findings flow
When you run an enumeration scan, HackPraxis writes ffuf's JSON output, parses
it, and saves the results as plain-text lists in the project's own folder:

```
/opt/hackpraxis/data/projects/<your-project>/
├── project.json       scope + metadata
├── discovered.txt     every endpoint found    "<status>  <length>  <url>"
├── forbidden.txt      only 401 / 403 ones      "<status>  <url>"
└── scans/             raw ffuf JSON, one per run
```

The **Enumeration** tab shows everything discovered; any **401/403** endpoint
appears in the **401/403 Bypass** tab as a ready-to-test target. It's all on disk
per project, so your results are still there after you restart HackPraxis: just
reselect the project.

Payload lists live in `hackpraxis/data/wordlists/` as plain text; edit freely.
They're compiled from standard public references (HackTricks, PortSwigger,
PayloadsAllTheThings).

## Usage

1. **Create a project** and paste the program's in-scope and out-of-scope hosts
   (`*.example.com` for subdomains, `example.com` for the apex).
2. **Enumerate.** Run the ffuf scan. Discovered endpoints appear in the GUI and
   are saved to the project folder; any `401`/`403` flow to the Bypass tab.
3. **Bypass.** Pick a forbidden endpoint (or paste one), run the 401/403 matrix,
   and watch for a row that behaves differently from the baseline.
4. **Traverse.** Mark the injection point with `FUZZ` and test it.
5. **Confirm by hand.** Every automated hit is a *lead*. Copy the exact command
   HackPraxis shows, run it yourself, read the real response, then call it a
   finding. Reproducibility is what gets a bounty paid.

## How scope is enforced

Scope lives in `hackpraxis/scope.py` and is checked inside the runner immediately
before any subprocess is spawned (`hackpraxis/runner.py` → `run_step`). The front
end previews scope decisions, but the authoritative gate is server-side, so
editing the page in your browser can't route a tool at an out-of-scope host.
Out-of-scope rules always beat in-scope rules.

## Project layout

```
hackpraxis/
├── setup.sh / uninstall.sh   one-word install via an isolated venv
├── pyproject.toml            package + `hackpraxis` console entry point
├── hackpraxis/
│   ├── __main__.py           launcher + ASCII banner
│   ├── app.py                FastAPI app + JSON API
│   ├── scope.py              scope engine + project persistence  ← safety core
│   ├── paths.py              persistent data dir (not $HOME)
│   ├── runner.py             command construction + execution
│   ├── md.py                 tiny Markdown renderer (no deps)
│   ├── modules/              one file per technique
│   ├── data/wordlists/       editable payload & content lists
│   ├── content/              the Learn guides (Markdown)
│   └── static/               the single-page GUI (HTML/CSS/JS, no build step)
├── docs/
└── tests/
```

Adding a module is a single file exposing `META` and `build(params) -> Plan`,
registered in `hackpraxis/modules/__init__.py`. See
[`docs/architecture.md`](docs/architecture.md).

## Roadmap (v2+)

- XSS and IDOR modules
- Response diffing and a findings log you can export to Markdown
- Server-Sent Events for live streaming of long scans
- Burp/ZAP proxy hand-off and per-request throttling

## Disclaimer

HackPraxis is a tool for **authorized** security testing and education. You are
responsible for ensuring you have explicit permission to test any target. The
authors accept no liability for misuse. See [`LICENSE`](LICENSE).
