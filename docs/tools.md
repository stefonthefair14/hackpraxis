# Installing the external tools

HackPraxis runs two tools that live on your system `PATH`. It never bundles or
auto-installs them, so you always know exactly what's on your machine. The
sidebar shows a dot for each tool it can find.

## ffuf (required)
Fast web fuzzer. Used by **Enumeration** and **Path Traversal**.
- **Go:** `go install github.com/ffuf/ffuf/v2@latest`
- **Homebrew:** `brew install ffuf`
- **Debian/Ubuntu:** `apt install ffuf`
- **Releases:** https://github.com/ffuf/ffuf/releases

## curl (required)
Used by **401/403 Bypass** and curl-mode traversal.
- **macOS / Linux:** already installed.
- **Windows:** ships with Windows 10+ (`curl.exe`), or `winget install curl`.

## Other enumerators (optional, for your own learning)
HackPraxis focuses on ffuf, but the Enumeration **Learn** tab points you at these
if you want to explore. None are required to use HackPraxis.
- **gobuster:** `go install github.com/OJ/gobuster/v3@latest`
- **feroxbuster:** `cargo install feroxbuster` or `brew install feroxbuster`
- **httpx (ProjectDiscovery):** `go install github.com/projectdiscovery/httpx/cmd/httpx@latest`

## PATH note for Go installs
`go install` drops binaries in `~/go/bin` (or `$GOBIN`). Add it to your PATH:

```bash
echo 'export PATH="$PATH:$HOME/go/bin"' >> ~/.zshrc   # or ~/.bashrc
```

Then restart HackPraxis so it re-checks your PATH.

## Wordlists
The shipped lists get you started. For serious enumeration, install
[SecLists](https://github.com/danielmiessler/SecLists):

```bash
git clone https://github.com/danielmiessler/SecLists.git
```

Then point the **Wordlist path** field at, e.g.,
`.../SecLists/Discovery/Web-Content/raft-medium-directories.txt`.
