# Cross-Site Scripting (XSS)

## What it is
XSS is when an application takes input you control and puts it into a page
without properly escaping it, so your input is parsed as HTML/JavaScript and runs
in another user's browser. Impact ranges from stealing sessions to full account
takeover.

## The two ways to practice here
- **The iframe (by hand).** The live page is embedded on the right. Type payloads
  into its real forms and watch what happens in a real browser context. This is
  how you learn to read the page's behaviour - where input lands, what gets
  encoded, what the filter does.
- **curl (reflection sweep).** HackPraxis fires each payload at your `FUZZ` point
  and flags any that come back in the response **unescaped**. That's a strong
  reflected-XSS lead; you then confirm it fires by pasting the same payload into
  the iframe.

> Some sites refuse to be framed (X-Frame-Options / CSP `frame-ancestors`). If the
> iframe stays blank, use "open in new tab".

## The three types
- **Reflected** - payload is in the request and echoed straight back in the
  response (search boxes, error messages). Non-persistent; needs a crafted link.
- **Stored** - payload is saved (a comment, profile field) and served to everyone
  who views it. Highest impact.
- **DOM-based** - the vulnerability is entirely in client-side JS that writes your
  input into the page (`innerHTML`, `document.write`, `location.hash`). The server
  may never see the payload, so a reflection sweep can miss it - this is where the
  iframe matters.

## Context is everything
The same input is safe or dangerous depending on where it lands:
- **HTML body:** `<script>…</script>`, `<img src=x onerror=…>`
- **HTML attribute:** break out first - `"><svg onload=…>` or `" onmouseover="…`
- **JavaScript string:** `';alert(1);//`
- **URL / `href`:** `javascript:alert(1)`

Read the reflection, identify the context, then pick the payload that breaks out
of it. A payload that works in the body often does nothing in an attribute.

## Reading the results
- **Reflected unescaped** = the raw payload is present in the response body. Open
  it in the iframe to see if it actually executes (reflection in a safe context,
  or with the right characters encoded, may not fire).
- Nothing flagged doesn't mean safe - try stored and DOM sinks by hand.

## Confirming responsibly
Use a harmless proof like `alert(document.domain)`. Don't pivot to stealing real
users' data; a popup that proves execution is enough for a report. Stay in scope.
