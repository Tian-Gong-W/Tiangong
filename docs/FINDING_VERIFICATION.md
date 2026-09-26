# Finding Verification

TONMEN treats three security claims as separate layers:

1. **Template Matched** — a scanner/template matcher reported a positive result.
2. **Evidence Confirmed** — captured request/response or other canonical Evidence materially demonstrates the observed behavior.
3. **Attribution** — the observed behavior is correlated to the claimed product/CVE/root cause.

A positive template result does **not** automatically prove CVE/root-cause attribution.

For multi-address hostnames, TONMEN also records backend correlation. If Nmap scans one DNS answer but Nuclei reaches another, the validation is scoped to the backend IP present in the Evidence. TONMEN does not generalize that result to every DNS answer without separate evidence.

Example:

- Nmap scanned `43.198.220.132`.
- Other resolved addresses were `18.166.185.90` and `43.198.193.28` and were not scanned by Nmap.
- Nuclei reached `18.166.185.90`.
- The response strongly demonstrated sensitive-file disclosure.
- The template claimed a Lighttpd CVE, while the response exposed `Server: kangle/3.5.19`.

The resulting classification is therefore:

- Template: `matched`
- Evidence: `confirmed / strong`
- Attribution: `contradicted`
- Backend: `different_resolved_backend`

This distinction is reflected in Intelligence facts and final JSON/Markdown reports.
