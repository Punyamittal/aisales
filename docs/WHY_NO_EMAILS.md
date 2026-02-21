# Why might we not find emails?

The app tries to find contact emails in two ways: **Hunter.io** (if you set `HUNTER_API_KEY`) and a **Beautiful Soup scraper** on the company’s website. Here’s why you might still see “No emails found” for some companies.

## 1. No domain to scrape

We need a **company domain** (e.g. `stripe.com`) to call Hunter or to scrape. It comes from:

- The model’s **company_domain** in suggested companies, or  
- **Inferred** from the company name (e.g. “Databricks” → `databricks.com`).

If we can’t infer a domain (e.g. generic “Series B SaaS in healthcare”), we don’t run Hunter or the scraper.

## 2. Hunter returns nothing

Hunter’s Domain Search only returns emails they have in their database. New or small companies may have few or no results. Free tier also has limits.

## 3. Scraping limitations

- **Contact forms only** – Many sites only have a form and no visible `mailto:` or plain-text emails, so the scraper finds nothing.
- **JavaScript-only content** – If emails are loaded by React/Vue/etc., our scraper only sees the initial HTML and misses them (we don’t run a browser).
- **Blocking / redirects** – Some servers return 403, captchas, or redirects for non-browser clients, so we get no usable HTML.
- **Obfuscation** – We try to decode patterns like “contact at company dot com”, but custom encodings or images won’t be detected.

## 4. What we do to find more emails

- We try **more paths**: `/contact`, `/about`, `/team`, `/people`, `/careers`, `/impressum`, etc.
- We use a **browser-like User-Agent** and decode **simple obfuscations** (at → @, dot → .).
- We **infer domain** from the company name when the model doesn’t give one.
- We always run the **scraper** if Hunter returns no contacts (or if Hunter isn’t configured).

For best coverage, use **Hunter.io** (API key) when you can; scraping is a best-effort fallback.
