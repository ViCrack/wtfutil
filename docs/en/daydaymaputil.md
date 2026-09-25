# wtfutil.daydaymaputil and the daydaymap CLI

A Python SDK and streaming CLI for existing DayDayMap assets. Every public SDK `count` / `search` and CLI query excludes **honeypots already labelled by the platform**. This cannot identify or guarantee exclusion of unlabelled honeypots. Region, domain and IPv4 filters are otherwise off by default.

`daydaymaputil.py` contains the SDK, key pool, aggregate counts, pagination and splitting, plus the private icon/certificate transport. `daydaymap.py` exports only CLI `main`.

## Quick start

Run `python -m pip install -e .` in the project to install `daydaymap`, or use `python -m wtfutil.daydaymap`. Store keys in an external UTF-8 file, one per line. The CLI discovers `daydaymap_keys.txt`; keys need not appear in command arguments.

```bash
# Bash / Git Bash: default search, JSONL records
daydaymap 'domain="example.com"' --fields ip,port,domain,url -o assets.jsonl

# Count only: free aggregation first; fallback with a key may consume credits
daydaymap --count 'domain="example.com"'

# Mainland China excluding Hong Kong/Macao/Taiwan, domain assets, URL output
daydaymap 'domain="example.com"' --is-china --is-domain --format url --limit 100

# Automatic incremental stdin, escaped template values
printf '%s\n' example.com example.org | daydaymap --template 'domain="{}"' --format url

# Explicit stdin when mixing sources; -o - means stdout
printf '%s\n' 'port="443"' | daydaymap -q 'domain="example.com"' --query-file - -o -

# Standalone icon/certificate inputs
daydaymap --icon-file favicon.ico --is-china
daydaymap --icon-url https://example.com/favicon.ico --count
daydaymap --cert-url https://example.com:8443 --proxy http://127.0.0.1:8080

# AND the fingerprint with every input query
daydaymap --query-file queries.txt --icon-file favicon.ico --key-file custom-keys.txt
```

Search is the default; use `--count` for counts. Bare positional `search` / `count` are not accepted as queries; use `-q search` / `-q count` for those literal words. Honeypot exclusion applies to every query.

The SDK wraps raw `a || b` as `(a || b) && ip.tag!="蜜罐"`. `build_query()` previews or exports the complete condition. Pass raw queries to `count` / `search` rather than calling the builder first and wrapping twice.

For PowerShell, UTF-8 files avoid version-dependent native argument quoting:

```powershell
'domain="example.com"', 'domain="example.org"' | Set-Content -Encoding utf8 queries.txt
daydaymap --query-file queries.txt --is-china --format url -o urls.txt

# Explicit UTF-8 for Unicode text piped into Python
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-Content -Encoding utf8 queries.txt | daydaymap --count
```

## CLI options

Usage: `daydaymap [QUERY] [options]`. Search is the default; `--count` outputs counts only.

| Option | Meaning / default |
|---|---|
| `QUERY` | One raw query, or a value when using a template |
| `-q QUERY` / `--query QUERY` | Additional query; repeatable |
| `--count` | Count only; free aggregate first, API fallback may charge with keys. Explicit search-only options fail before requests |
| `--query-file FILE` | UTF-8, one query per line; repeatable; `-` means stdin |
| `--template TEMPLATE` | E.g. `domain="{}"`; placeholders must be inside double quotes |
| `--icon-file FILE` / `--icon-url URL` | Local icon / direct HTTP(S) image URL; mutually exclusive |
| `--cert-url URL` | HTTPS leaf certificate; combines with icons and text queries |
| `--is-china` | Mainland-China clauses excluding Hong Kong/Macao/Taiwan; off by default |
| `--is-domain` | Add `is_domain="true"`; off by default |
| `--key-file FILE` | External key file; repeatable |
| `-o FILE` / `--output FILE` | Overwrite UTF-8 output; omitted or `-` means stdout |
| `--timeout N` | Per-request timeout, >0 seconds; default 30 |
| `--interval N` | SDK request interval, >=0; default 0.5 seconds |
| `--max-retries N` | Extra connect-timeout/429/2006 retries, 0..20; default 2 |
| `--proxy URL` | HTTP(S)/SOCKS proxy; install `wtfutil[socks]` for SOCKS |
| `--quiet` | Search only: hide pre-counts and summaries, not errors |
| `--fields LIST` | Comma-separated search fields; overrides exclusions |
| `--exclude-fields LIST` | Comma-separated search field exclusions |
| `--page-size N` | Search page width, 1..10000; default 500 |
| `-l N` / `--limit N` | Output cap per input query; default 10000; 0 removes the local cap |
| `--format {jsonl,url}` | Search output; default JSONL; counts always use JSONL |
| `--max-effort` | Try one-level aggregate partitioning beyond the result window |
| `--max-effort-depth N` | Maximum child queries, 1..1000; default 10, not recursion depth |
| `-h` / `--help` | Show help |

Explicit `--fields`, `--exclude-fields`, `--page-size`, `--limit`, `--max-effort`, `--max-effort-depth`, `--format` and `--quiet` belong to search only; pairing them with `--count` fails before reading keys or opening output. `--max-effort-depth` also requires `--max-effort`. If these options are omitted, search uses the defaults listed above.

## Input order, templates and file protection

Process the positional query, repeated `-q` values, then query files in their specified order. Files/stdin ignore a first-line BOM, blank lines and whole-line `#` comments. Query deduplication preserves first occurrence; its set grows with distinct queries, but whole files are never loaded up front. Repeated `--query-file -` consumes stdin once.

Stdin is automatic only when it is not a terminal and there is no explicit positional query, `-q`, query file, icon or certificate. Use `--query-file -` to combine a pipe with explicit sources. Each query runs before the next line is read, without waiting for EOF. Counts, records and summaries are per query; totals are not combined, and assets are not deduplicated across separate inputs.

Templates apply to positional, `-q` and line-based inputs. `domain="{}" || cert.subject.cn="{}"` inserts the same escaped value twice. Escape backslashes to `\\` first, then double quotes to `\"`. Missing placeholders, unknown braces, placeholders outside quotes, unclosed quotes and backslash-escaped placeholders fail locally.

Icons/certificates are resolved once and AND-combined with every parenthesized query. Without a text source, fingerprints work alone; two fingerprints are also AND-combined. An explicitly supplied but empty text source is an error rather than a fallback to a broader fingerprint query.

Before opening output, the CLI validates keys, options, all named query files and path collisions, and resolves fingerprints. Output cannot overwrite a used key, query or icon file, including symbolic or hard links. Regular files redirected into stdin are also protected by filesystem identity. Missing files, empty input, invalid templates and source failures preserve existing output. Errors after streaming begins retain partial output. `--key-file -` refers to a literal file named `-`, whereas `-o -` always means stdout.

## Query filters

All public count/search entry points apply:

```text
(raw query) && ip.tag!="蜜罐"
```

`--is-china` / `is_china=True` also adds:

```text
ip.country="CN" && ip.province!="香港" && ip.province!="澳门" && ip.province!="台湾" && ip.city!="香港" && ip.city!="澳门"
```

`--is-domain` / `is_domain=True` adds `is_domain="true"`. These conditions persist through free aggregation, paid fallback, pagination and child queries. They rely on platform labels/geolocation; no extra local inference is performed.

## Icons, certificates and proxies

- Icons use MD5 of the original image contents to produce `web.icon="MD5"`, not Base64/MMH3 or normalized pixels. Format recognition covers ICO, PNG, JPEG, GIF, WebP, BMP and SVG; at most 2 MiB and five HTTP(S) redirects. Empty/HTML content is rejected. Recognition is not a full image decode. Supply a direct image URL; HTML favicon discovery is not performed.
- Certificates use a TLS handshake with the HTTPS host, port and SNI, hashing the leaf certificate's DER bytes into `cert.md5="MD5"`. No website HTTP request or redirect is performed; path/query do not change the TLS origin. Self-signed and expired target certificates are accepted. This sampling connection also accepts self-signed HTTPS proxy certificates and never carries DayDayMap keys. Platform API requests and image downloads still verify TLS.
- The platform exposes MD5 fields, but its documentation does not fully specify image preprocessing/certificate byte encoding. This implementation chooses original image bytes and leaf DER; calibrate with a known indexed sample. Dynamic images, certificate rotation, CDN/SNI, multiple certificates and index delays may yield no matches. Successful sampling does not guarantee a matching indexed record.
- Source URLs must be HTTP(S), HTTPS only for certificates, and must not contain user information. Proxies accept HTTP, HTTPS, SOCKS5 and SOCKS5H with optional authentication. Errors do not echo URLs, proxy passwords, keys or response payloads.
- Explicit `--proxy` overrides environment proxies and is not bypassed by `NO_PROXY`. Otherwise Requests environment/system proxies and `NO_PROXY` apply. Proxy failure never falls back to a direct connection. SOCKS5 resolves locally; SOCKS5H resolves at the proxy. Install with `python -m pip install 'wtfutil[socks]'`.

## Key discovery, state and retries

UTF-8 key files may have a BOM. Blank lines and whole-line comments are ignored; deduplication preserves order. Use your external file; these example values are fictitious:

```text
# External API key file
example-key-a
example-key-b
```

CLI precedence: repeated `--key-file` paths → one `DAYDAYMAP_KEY_FILE` → one `DAYDAYMAP_API_KEY` → the first discovered `daydaymap_keys.txt`. Discovery checks the working directory, its `resource/` directory, then the user home. Lower-priority sources are not mixed in. An empty, invalid or unreadable first file does not fall through. Without keys, free counts can still work; search exits 2. The default key filename is gitignored.

The SDK does not read these CLI credential environment variables. `load_keys()` and `DayDayMapClient.from_key_file()` can discover files; the ordinary constructor does not. Credential loading does not use an INI section, database or browser cookies.

Successful requests return the key to the end of the queue. Codes 2001 (invalid), 2003 (permission) and 2004 (credits) remove the key and retry the same page with the next one. Code 2005 is a result-window limit, not a rotation trigger; 2002/470 indicates bad syntax/arguments. State exists only during the client's lifetime, with no assumed daily reset. `available_keys` counts active leased and idle keys.

Connect timeouts, 429 and 2006 have bounded retries. A 429 retries the same key and observes Retry-After; waits over 60 seconds stop with a rate-limit error. Read timeouts and other possibly charged failures are not automatically replayed. Internal API/web sessions are separate, disable lower-level POST retries, reject redirects and verify TLS. Callers supplying sessions own their authentication, cookies, proxy and retry policies.

## Counts, pagination and output

`--count` first calls anonymous `/api/v1/raymap/search/aggregate/query` without an API key. It takes the maximum sum across usable bucket dimensions, including an “other” bucket, always labelled **estimated**. `ip_num` is only `ip_count`, not an asset total. Empty/invalid buckets are not treated as zero.

```json
{"query":"(domain=\"example.com\") && ip.tag!=\"蜜罐\"","total":100,"estimated":true,"source":"aggregate","ip_count":80}
```

Numbers are illustrative. When aggregation is unavailable and a key exists, both CLI and SDK `count()` automatically use `/api/v1/raymap/search/all` with `page=1,page_size=1,fields=ip` to obtain `data.total`, returning `estimated=false,source=api`. **This fallback may consume credits**, including discovered keys. Bad syntax and persistent rate limits do not trigger it. To ensure a count never makes a billed API request, construct the SDK client without keys, or run the CLI without keys (including no automatically discovered key file). Web aggregation behavior may change; billing, permissions and rate limits belong to the platform.

Search emits a `type=count` object on stderr before assets, then a `type=summary` object at completion. When free preflight fails, the first normal search response provides the total; there is no additional paid count probe. An estimated zero does not skip search. The SDK exposes the same event through `on_count(DayDayMapCount)`.

- stdout contains data only: search JSONL/URLs or count JSONL. Progress and sanitized errors go to stderr. Every output line is flushed. `--quiet` hides pre-counts/summaries, not errors.
- `limit` is per input. Zero removes the local cap, not the remote 10000-record window; rotating keys does not bypass the window either.
- Small limits reduce the first page width, which remains fixed within a child query. The final request may fetch less than one extra page; `fetched` tracks actual retrieved records. A short non-final page raises `incomplete_page` rather than silently skipping offsets.
- JSONL preserves official fields, with fields taking precedence. URLs prefer the official url and otherwise combine service/domain/ip/port, bracketing IPv6. Required URL fields are requested automatically.
- `max_effort` partitions one level using province, port, service or icon buckets. Children retain filters and parentheses; identity deduplication precedes projection. Root detail retrieval is skipped when immediate partitioning is possible. Buckets can omit, overlap or exceed the window, so actual partitioning always reports `truncated=true,reason=best_effort`, not guaranteed completeness.
- Ordinary pagination does not deduplicate identical projected rows; different ports on one IP can be different assets. Pages, children and input queries are serial.
- A consumer closing stdout closes the generator and stops further pages, exiting 0. Windows broken-pipe EINVAL is handled too; ordinary permission/file errors remain failures. Ctrl+C retains partial output.

Summary fields: `query,total,estimated,returned,fetched,queries,truncated,limit_reached,reason,keys_remaining`. `queries` counts executed root/child queries, not HTTP requests. `returned` counts records handed to the caller, not confirmed consumer persistence.

| Exit code | Meaning |
|---|---|
| 0 | Completed, or downstream consumer closed early |
| 1 | Network, source, response, file or unavailable free aggregation |
| 2 | Invalid arguments/syntax, empty input or required keys missing |
| 3 | All keys exhausted or unusable |
| 4 | Truncation/incomplete results, including limit, remote window or best-effort splitting |
| 130 | Interrupted |

Batch processing stops at the first error and retains partial output. Otherwise any truncated query makes the final exit code 4.

## Python SDK

```python
from wtfutil.daydaymaputil import DayDayMapClient, DayDayMapError, query_from_icon, query_from_certificate

icon = query_from_icon('favicon.ico')
cert = query_from_certificate('https://example.com:8443', proxy='http://127.0.0.1:8080')
with DayDayMapClient.from_key_file(timeout=30, interval=0.5) as client:
    print(client.count(icon, is_china=True).to_dict())
    try:
        for asset in client.search(cert, is_domain=True, limit=100,
                                   on_count=lambda result: print(result.to_dict())):
            print(asset)
    except DayDayMapError as error:
        print(error.reason, error.code)
    if client.last_summary is not None:
        print(client.last_summary.to_dict())
```

| Public API | Contract |
|---|---|
| `DEFAULT_BASE_URL` | Default platform root constant |
| `build_query(query, *, is_china=False, is_domain=False)` | Pure builder, mandatory honeypot exclusion; returns str |
| `query_from_icon(path=None, *, url=None, timeout=30, proxy=None)` | Exactly one image source; raw `web.icon` clause |
| `query_from_certificate(url, *, timeout=30, proxy=None)` | HTTPS leaf DER MD5; raw `cert.md5` clause |
| `find_key_file()` | First discovered Path or None |
| `load_keys(path=None)` | Validated/deduplicated list[str]; [] if no default file |
| `DayDayMapClient(keys=(), *, session=None, web_session=None, timeout=30, interval=0.5, max_retries=2, retry_backoff=1, proxy=None)` | keys is a string or sequence; no automatic file loading |
| `DayDayMapClient.from_key_file(path=None, **kwargs)` | File-loading convenience constructor; supports discovery |
| `client.count(query, *, is_china=False, is_domain=False)` | DayDayMapCount; free aggregate first, automatic API fallback if needed |
| `client.search(query, *, fields=None, exclude_fields=None, page_size=500, limit=10000, max_effort=False, max_effort_depth=10, is_china=False, is_domain=False, on_count=None)` | dict generator; performs requests during iteration |
| `client.available_keys` / `client.last_summary` | Active keys / latest started search summary, initially None |
| `client.close()` / context manager | Close internally created sessions only |
| `DayDayMapCount` | Immutable query/total/estimated/source/ip_count, with to_dict() |
| `DayDayMapSearchSummary` | Summary fields above, with to_dict() |
| `DayDayMapError` | Sanitized reason/code/status_code/to_dict(), also used for source failures |

Invalid arguments raise `ValueError`. Source failures raise `DayDayMapError`, such as `icon_file`, `icon_download`, `invalid_icon`, `certificate_fetch` or `proxy_dependency`. Close the search generator when stopping iteration early so its summary is finalized promptly.

## Local verification and references

```bash
python -W error::ResourceWarning -m unittest tests.test_daydaymap tests.test_daydaymap_inputs tests.test_daydaymap_transport tests.test_daydaymap_pipeline tests.test_public_api -q
python -m wtfutil.daydaymap --help
```

Tests do not contact the real platform by default. TLS/HTTP CONNECT/HTTPS-proxy/SOCKS cases use temporary certificates and local servers; certificate generation requires OpenSSL, and SOCKS requires PySocks. Applicable cases skip when those tools are absent. Subprocess pipeline tests use a local API and clearly fictitious keys.

- [Official syntax](https://www.daydaymap.com/help/document?type=syntax-search)
- [Official data API](https://www.daydaymap.com/help/document?type=api-data)
- [Official response fields](https://www.daydaymap.com/help/document?type=api-filed)
