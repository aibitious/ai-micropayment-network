"""Product-facing, privacy-preserving pages for the free Agent404 experiment."""
from __future__ import annotations

from html import escape
import json
from .lab import TOOLS, LIMITATIONS

EXAMPLES = {
    "json_guard": {"document": {"id": 3}, "schema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}},
    "csv_doctor": {"csv_text": "id,name\n1,Ana\n1,\n2,Bo\n", "key_columns": ["id"]},
    "invoice_audit": {"currency": "PLN", "lines": [{"quantity": "2", "unit_price": "10.00", "tax_rate": "23"}], "declared_gross": "24.60"},
    "secret_shield": {"text": "Example text without real credentials"},
    "openapi_preflight": {"spec": {"openapi": "3.1.0", "info": {"title": "Sample API", "version": "1.0"}, "paths": {}}},
    "mcp_preflight": {"server": {"name": "io.github.example/sample", "version": "0.1.0", "description": "Synthetic MCP server", "remotes": [{"type": "streamable-http", "url": "https://example.org/mcp"}]}},
    "header_audit": {"headers": {"content-type": "text/html", "x-content-type-options": "nosniff"}},
    "robots_check": {"robots_txt": "User-agent: *\nDisallow: /private\n", "path": "/private/data"},
    "schema_diff": {"before": {"id": 1, "name": "Example"}, "after": {"id": "1", "label": "Example"}},
}

STYLE = """
:root{color-scheme:dark;--bg:#0b1220;--card:#141f30;--text:#edf3fc;--muted:#9cadc3;--accent:#7cc7ff;--line:#30445d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--accent)}a:hover{text-decoration:underline}a:focus-visible,button:focus-visible,textarea:focus-visible{outline:3px solid #f8d46c;outline-offset:3px}
header{border-bottom:1px solid var(--line);background:#101b2c}header nav{max-width:1120px;margin:auto;display:flex;flex-wrap:wrap;gap:1.2rem;align-items:center;padding:1rem 1.3rem}
.brand{font-weight:800;color:var(--text);text-decoration:none;letter-spacing:.04em;margin-right:auto}
main{max-width:1120px;margin:auto;padding:2.5rem 1.3rem 4rem}h1{font-size:clamp(2rem,5vw,3.6rem);letter-spacing:-.035em;line-height:1.1;max-width:880px}h2{font-size:1.5rem;line-height:1.25;margin-top:2.4rem}
.lead{font-size:1.14rem;color:#c6d4e5;max-width:760px}.muted,small{color:var(--muted)}.pill{display:inline-block;border:1px solid #345e73;padding:.25rem .7rem;border-radius:50px;color:#b3e4f9;font-size:.82rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:1rem}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.3rem}
.card h3{margin-top:0}.card p{color:#b9c7d8}.button,button{display:inline-block;background:#9bd8ff;color:#092037;border:0;border-radius:8px;padding:.7rem 1.1rem;font:inherit;font-weight:750;cursor:pointer;text-decoration:none}
.button:hover,button:hover{background:#c8eaff;text-decoration:none}.secondary{background:transparent;color:var(--accent);border:1px solid #4d7795}
.actions{display:flex;flex-wrap:wrap;gap:.8rem;margin:1.6rem 0}
pre,textarea,code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}pre{background:#07101c;color:#d0e3ef;padding:1rem;border:1px solid var(--line);border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere}
textarea{width:100%;min-height:210px;border:1px solid #54708b;background:#081626;color:#eaf3fc;border-radius:8px;padding:1rem;font-size:.93rem}
footer{border-top:1px solid var(--line);padding:1.4rem;text-align:center;color:var(--muted)}
.notice{border-left:3px solid #f8d46c;padding:.8rem 1rem;background:#1d2734;color:#dce7f5}
"""

def _page(title: str, description: str, canonical: str, body: str) -> str:
    doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="@DESC@">
<meta property="og:title" content="@TITLE@"><meta property="og:description" content="@DESC@">
<link rel="canonical" href="@CANON@"><title>@TITLE@</title><style>@STYLE@</style>
</head><body><header><nav><a class="brand" href="/404/">AIBITIOUS / 404 LAB</a>
<a href="/404/tools/">Tools</a><a href="/404/docs">API reference</a>
<a href="/404/llms.txt">For AI agents</a><a href="https://github.com/aibitious/ai-micropayment-network/tree/main/experiments/agent-404">Source</a></nav></header>
<main>@BODY@</main><footer>Experimental tools · Free to test · No payments · No production data or secrets</footer></body></html>"""
    for key, val in (("@TITLE@", escape(title, quote=True)), ("@DESC@", escape(description, quote=True)),
                     ("@CANON@", escape(canonical, quote=True)), ("@STYLE@", STYLE), ("@BODY@", body)):
        doc = doc.replace(key, val)
    return doc

def landing() -> str:
    body = """<span class="pill">Public 30-day experiment · 10 free tools</span>
<h1>Catch data and integration errors before they reach production.</h1>
<p class="lead">Small, deterministic checks for developers and AI agents. Inspect JSON, CSV, invoices, API contracts, MCP metadata and schema drift. Use REST or a public Streamable HTTP MCP server.</p>
<div class="actions"><a class="button" href="/404/tools/?src=landing">Try a working demo</a>
<a class="button secondary" href="/404/v1/lab/catalog?src=landing">Machine-readable catalog</a></div>
<section class="grid">
<article class="card"><h3>Broken input?</h3><p>Spot missing JSON fields, inconsistent CSV rows and unexpected schema changes before an agent acts on them.</p><a href="/404/tools/json_guard?src=landing">Run JSON Guard</a></article>
<article class="card"><h3>Uncertain API integration?</h3><p>Inspect supplied OpenAPI metadata and MCP registration documents without executing third-party code.</p><a href="/404/tools/openapi_preflight?src=landing">Check an API contract</a></article>
<article class="card"><h3>Wrong calculated totals?</h3><p>Recalculate sample invoice line totals with decimal arithmetic; no claim of legal or tax certification.</p><a href="/404/tools/invoice_audit?src=landing">Try invoice arithmetic</a></article></section>
<h2>Connect from your agent</h2>
<p>Use <a href="/404/mcp/">MCP Streamable HTTP</a> or standard <a href="/404/openapi.json">OpenAPI</a>. Explore the <a href="/404/v1/lab/catalog">tool catalog</a> for exact input schemas.</p>
<pre>https://aibitious.com/404/mcp/</pre>
<h2>Transparent by design</h2>
<p>All nine validators work on supplied data in memory. Only CVE Verify queries the official NIST NVD database. The public experiment has usage limits and no billing. The tools are advisory and cannot certify security, regulatory compliance or factual truth.</p>
<p class="notice">Use synthetic or public examples. Never submit credentials, personal information, private invoices or production records. The demo does not need registration.</p>
<p><a href="/404/tools/">See all ten experiments</a> · <a href="/404/health">Service status</a> · <a href="/404/llms.txt">Agent discovery reference</a></p>"""
    return _page("AIBITIOUS 404 LAB — Free REST and MCP validation tools",
                 "Try ten free data-quality and API-preflight tools with REST and MCP. Runnable synthetic demos, no account or payments.",
                 "https://aibitious.com/404/", body)

def directory() -> str:
    cards = ''.join('<article class="card"><h3><a href="/404/tools/'+escape(slug)+'?src=directory">'+escape(title)+'</a></h3><p>'+escape(desc)+'</p><a href="/404/tools/'+escape(slug)+'?src=directory">Try with synthetic data</a></article>' for slug,(title,desc) in TOOLS.items())
    body = ('<span class="pill">9 offline validators + CVE evidence</span>'
            '<h1>Choose the error you need to catch.</h1>'
            '<p class="lead">Every validator has a prefilled safe example, a live result preview, and a matching REST/MCP interface.</p>'
            '<section class="grid">'+cards+'</section>'
            '<h2>10. CVE Verify</h2><p>Retrieve public vulnerability records from NIST NVD. '
            'This is an older baseline, separate from the nine new offline validators. '
            '<a href="/404/docs">Open the CVE API reference</a>.</p>'
            '<p class="notice">Tests are free, but not certifications or security audits. Only use synthetic or public data.</p>')
    return _page("10 Free AI Agent Tools — AIBITIOUS 404 LAB",
                 "Try JSON validation, CSV quality, invoice math, schema diff and API/MCP contract checks without signing up.",
                 "https://aibitious.com/404/tools/", body)

def tool_detail(slug: str) -> str:
    title, desc = TOOLS[slug]
    sample = json.dumps(EXAMPLES[slug], indent=2, ensure_ascii=False)
    body = ('<span class="pill">Free live demo · Synthetic input</span>'
            '<h1>'+escape(title)+'</h1><p class="lead">'+escape(desc)+'</p>'
            '<p class="notice">'+escape(LIMITATIONS[slug])+
            ' Do not paste private records, credentials or production data.</p>'
            '<h2>Try it now</h2><p>The example is synthetic. Edit it if needed. '
            'The request is sent to the same public API used by agents.</p>'
            '<form id="demo" data-slug="'+escape(slug,quote=True)+'"><label for="payload">JSON request body</label>'
            '<textarea id="payload" maxlength="20000" spellcheck="false">'+escape(sample)+'</textarea>'
            '<div class="actions"><button type="submit">Run free check</button></div></form>'
            '<h2>Result</h2><pre id="output" aria-live="polite">Run the synthetic example to see the response.</pre>'
            '<h2>Connect via REST or MCP</h2><pre>POST https://aibitious.com/404/v1/lab/'+escape(slug)+'</pre>'
            '<p>MCP endpoint: <a href="/404/mcp/">/404/mcp/</a>. '
            '<a href="/404/v1/lab/catalog">Exact catalog</a> · '
            '<a href="/404/docs">OpenAPI reference</a> · '
            '<a href="/404/tools/">All tools</a></p>')
    body += """<script>
const form = document.getElementById('demo');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const output=document.getElementById('output');
  output.textContent='Running...';
  try {
    const endpoint=new URL('../v1/lab/'+encodeURIComponent(form.dataset.slug),location.href);
    const response=await fetch(endpoint,{method:'POST',headers:{
      'Content-Type':'application/json','X-404-Client-Surface':'web-playground'
    },body:document.getElementById('payload').value});
    const text=await response.text();
    try {output.textContent=JSON.stringify(JSON.parse(text),null,2);} catch {output.textContent=text.slice(0,3000);}
    if(!response.ok) output.textContent='HTTP '+response.status+'\\n'+output.textContent;
  } catch {
    output.textContent='Network error. Check availability and retry.';
  }
});
</script>"""
    return _page(title + " — Free Live Demo | AIBITIOUS 404",
                 desc + " Try a synthetic example with REST or MCP. No account or payments required.",
                 "https://aibitious.com/404/tools/"+slug, body)
