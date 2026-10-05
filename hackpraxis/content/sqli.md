# SQL Injection (SQLi)

## What it is
SQLi is when user input is concatenated into a SQL query instead of being passed
as a parameter, letting you change the query's meaning: read other users' data,
bypass logins, dump whole tables, sometimes run commands on the database host.

## The two ways to practice here
- **sqlmap (automated).** The industry-standard SQLi tool. HackPraxis builds the
  `sqlmap` command, explains every flag, and runs it. Start low (`--level 1
  --risk 1`) and read the output: sqlmap tells you the parameter, the injection
  type, and the back-end DBMS when it finds one.
- **curl (by hand).** Send classic test payloads at a `FUZZ` point and watch the
  response. HackPraxis flags any response containing a known database error
  message - the clearest beginner signal that input is reaching the query.
- **The iframe.** Try payloads in the real login form or search box yourself, so
  you see the app's actual behaviour, not just a status code.

## The injection types (how you detect it)
- **Error-based** - a broken query returns a database error. Fastest to spot;
  that's what the curl sweep looks for (`'`, `"`, `)`).
- **Boolean-based blind** - no error, but `' AND 1=1` and `' AND 1=2` return
  *different* pages. You infer data one true/false question at a time.
- **Time-based blind** - no visible difference, so you ask the DB to **wait**:
  `' OR SLEEP(5)-- -` (MySQL), `' OR pg_sleep(5)-- -` (Postgres),
  `'; WAITFOR DELAY '0:0:5'-- -` (MSSQL). A 5-second delay confirms it.
- **UNION-based** - append `UNION SELECT …` to pull data into the page. First find
  the column count with `ORDER BY n` until it errors.

## Reading sqlmap output
- "parameter 'id' is vulnerable" plus a payload = confirmed injection, your
  finding.
- It names the technique(s) and the DBMS. `--dbs` then lists databases; deeper
  flags (`--tables`, `--dump`) go further - only within your authorized scope and
  rules of engagement.
- Nothing found at level/risk 1 doesn't mean safe; raising `--level`/`--risk`
  tests more places and more payloads (and sends more traffic).

## A note on `--risk`
Risk 2-3 includes payloads that can modify data (e.g. `OR`-based on a UPDATE).
Know the target can take it before you turn it up. On someone's production system,
stay low and slow.

## Confirming responsibly
Proving an injection point exists (and naming the DBMS) is usually enough for a
report. Don't dump real users' personal data to "prove" impact - describe it.
Stay in scope.
