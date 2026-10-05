# Enumeration

## What it is
Enumeration is the mapping phase: before you test anything, you build a picture
of what the target exposes - paths, files, endpoints - by requesting a big list
of candidate names and keeping the responses that look real. Most findings start
here. You cannot test an endpoint you never discovered.

## Why HackPraxis uses ffuf (and only ffuf)
There are a dozen content-discovery tools. Learning one of them well beats
poking at five, and ffuf is the one worth your time: it is fast, it fuzzes a
keyword (`FUZZ`) anywhere in the request, and it has the best filtering for
cutting through noise. Everything you learn here - match/filter logic, recursion,
extensions - transfers to the other tools if you ever need them.

HackPraxis runs ffuf with JSON output, parses it, and turns the results into the
**Discovered endpoints** list you see below the scan. Any endpoint that comes
back **401 or 403** is written to the project's `forbidden.txt` and shows up in
the **401/403 Bypass** tab, ready to test.

## How to read the output
- A wall of `200`s that are all the same size is usually a **soft-404** (the app
  returns a friendly "not found" page with status 200). Filter it out: add
  `-fs <size>` to hide that size, or `-fc 200`. Finding the right filter *is* the
  skill.
- `301`/`302` to a login page means the path exists but needs auth - note it.
- `401`/`403` is gold: the path exists and is protected. Those flow to the Bypass
  tab automatically.
- `405 Method Not Allowed` means the endpoint is real but wants a different verb.

## Tuning ffuf
- Start with a small wordlist, find your filters, *then* scale up. SecLists is the
  standard source - point the wordlist field at any file you like.
- Add extensions (`php,txt,bak,zip,old`) to catch leftover files.
- Threads make it faster and noisier. On someone else's production system, slower
  is politer and less likely to trip rate limits or alerts.
- `-mc` (match codes) keeps only the statuses you care about; `-fc`/`-fs`/`-fw`
  filter out the ones you don't.

## The other tools (for when you need them)
You do not need these to use HackPraxis, but a working tester knows they exist:

- **gobuster** - simple, fast directory/file brute-forcer. Fewer knobs than ffuf.
- **feroxbuster** - recursive content discovery, great defaults, written in Rust.
- **dirsearch** - Python brute-forcer with a strong built-in wordlist.
- **httpx** (ProjectDiscovery) - not a brute-forcer; it *probes* a list of hosts
  and reports status, title, tech and server headers. Use it to triage a wide
  scope before you fuzz.
- **katana / gau / waybackurls** - pull known URLs from crawling and archives,
  a different angle from brute-forcing.

## Common mistakes
- Blasting a huge wordlist before you've identified the soft-404 behaviour, then
  drowning in false positives.
- Ignoring `robots.txt`, `sitemap.xml` and `.well-known/` - free endpoint lists
  the app hands you directly.
- Forgetting the target's tech: `.php` paths on a .NET app are wasted requests.
