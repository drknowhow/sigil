# Effect-row spot check — requests 2.34.2 (Phase 1 exit gate)

30 functions sampled deterministically (every Nth of 256, sorted by file/name),
hand-labeled against source. Date: 2026-06-11. Scoring: an inferred `!unsafe?`
covers any true effect (it is the honest "cannot resolve statically" marker and
is counted separately, never as silence).

| # | Function | True effects | Inferred | Verdict |
|---|----------|--------------|----------|---------|
| 1 | check_compatibility | !io (warnings.warn) | !io | ok |
| 2 | BaseAdapter.__init__ | pure | pure? | ok |
| 3 | HTTPAdapter.cert_verify | !fs (os.path.exists) | pure? → **!fs after fix** | **UNDER-REPORT → fixture case_031, fixed** |
| 4 | HTTPAdapter.proxy_headers | pure | !unsafe? | over (cross-module call, honest) |
| 5 | api.patch | !net | !unsafe? | covered (cross-module) |
| 6 | HTTPBasicAuth.__ne__ | pure | pure? | ok |
| 7 | HTTPDigestAuth.handle_redirect | pure | pure? | ok |
| 8 | MockRequest.get_host | pure (urlparse) | !unsafe? | over (honest) |
| 9 | MockRequest.get_new_headers | pure | pure? | ok |
| 10 | get_cookie_header | pure | !net | over (http.cookiejar annotation; refined) |
| 11 | RequestsCookieJar.iteritems | pure | pure? | ok |
| 12 | RequestsCookieJar.__getitem__ | pure | pure? | ok |
| 13 | RequestsCookieJar.__setstate__ | pure | !unsafe | over (threading; honest) |
| 14 | cookiejar_from_dict | pure | !unsafe? | over (honest) |
| 15 | default_hooks | pure | pure? | ok |
| 16 | RequestEncodingMixin._encode_files | !fs (reads handles) | !unsafe? | covered |
| 17 | PreparedRequest.__repr__ | pure | pure? | ok |
| 18 | PreparedRequest.prepare_auth | pure | !unsafe? | over (honest) |
| 19 | Response.__repr__ | pure | pure? | ok |
| 20 | Response.apparent_encoding | pure | !unsafe? | over (unknown import chardet, honest) |
| 21 | Response.text | pure | pure? | ok |
| 22 | SessionRedirectMixin.get_redirect_target | pure | !unsafe? | over (honest) |
| 23 | Session.__exit__ | !net (closes pools) | pure? | **UNDER-REPORT — untracked-local method call; documented D-008, v2 candidate** |
| 24 | Session.patch | !net !env !clock | !clock !env !unsafe? | covered |
| 25 | Session.__setstate__ | pure | !mut | over (setattr rule; honest) |
| 26 | CaseInsensitiveDict.__len__ | pure | pure? | ok |
| 27 | LookupDict.__getitem__ | pure | pure? | ok |
| 28 | extract_zipped_paths | !fs | !env !fs | ok (+env over) |
| 29 | unquote_header_value | pure | pure? | ok |
| 30 | iter_slices | pure | pure? | ok |

**Result: 2/30 under-reports (6.7%) — gate is <10%. PASS.**
One miss fixed via fixture case_031 (os.path I/O predicates); one documented as
the known v1 limitation (method calls on untracked locals are silent — the
mitigation is origin tracking, the real answer is dynamic tracing, roadmap).
Under-reporting is the failure metric; over-reporting is acceptable noise
(9/30 here, mostly honest !unsafe? on cross-module calls).

**Postscript (2026-06-12, D-025):** return-taint propagation landed; `HTTPAdapter.close`
and 9 other rows now carry honest `!unsafe?` markers instead of `pure?`. Under-report #2
(the Session.close chain) is partially closed: the adapter side is flagged; full closure
still requires container tracking (v2).
