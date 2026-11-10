"""AIBITIOUS 404 LAB: nine bounded, offline, deterministic agent utilities.

Inputs are processed in memory. Never fetch arbitrary URLs, execute supplied code,
persist raw documents or present heuristic results as compliance certification.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import csv
import io
import json
import math
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

class LabInputError(ValueError):
    """Invalid / unsupported experimental tool input."""

TOOLS = {
    "json_guard": ("JSON Guard", "Validate JSON data against a safe subset of JSON Schema 2020-12."),
    "csv_doctor": ("CSV Doctor", "Find absent values, ragged rows and duplicate keys in small CSV data."),
    "invoice_audit": ("Invoice Audit", "Recalculate invoice line totals using decimal arithmetic."),
    "secret_shield": ("Secret Shield", "Flag likely secrets in supplied text without revealing matching values."),
    "openapi_preflight": ("API Contract Check", "Check basic OpenAPI document completeness without network access."),
    "mcp_preflight": ("MCP Preflight", "Lint MCP server registration metadata without contacting the registry."),
    "header_audit": ("Header Audit", "Check supplied HTTP response security headers for common weaknesses."),
    "robots_check": ("Robots Check", "Interpret supplied robots.txt for a requested agent and path."),
    "schema_diff": ("Schema Diff", "Compare shapes of two JSON objects and classify structural changes."),
}
LIMITATIONS = {
    "json_guard": "Safe subset only; remote refs, regex patterns and advanced composition are not supported.",
    "csv_doctor": "Static CSV sample only; does not establish the truth of individual values.",
    "invoice_audit": "Arithmetic only; does not confirm VAT rules, invoice authenticity or tax compliance.",
    "secret_shield": "Pattern matching only; false positives and missed secrets are possible.",
    "openapi_preflight": "Structure lint only; not a full OpenAPI parser or live endpoint test.",
    "mcp_preflight": "Static metadata inspection only; not an official registry validation.",
    "header_audit": "Supplied header values only; not a live security audit.",
    "robots_check": "Best-effort parser; not permission to scrape, and not a terms-of-service review.",
    "schema_diff": "Shape comparison, not semantic validation; examples may omit possible fields.",
}

def describe_tools():
    return [{"slug": slug, "name": title, "description": description,
             "method": "POST", "path": f"/v1/lab/{slug}",
             "price": {"amount": 0, "currency": "USD"},
             "limitations": LIMITATIONS[slug]}
            for slug, (title, description) in TOOLS.items()]

def _fail(condition, message):
    if not condition:
        raise LabInputError(message)

def _finding(code, message, severity="warning", path=""):
    return {"code": code, "severity": severity, "path": str(path)[:160], "message": message}

def _result(slug, findings, **details):
    return {"tool": slug, "status": "issues" if findings else "ok",
            "findings": findings[:30], "details": details,
            "limitations": LIMITATIONS[slug]}

def _safe_key(value):
    return str(value).replace("\n", " ")[:100]

def _check_size(payload):
    _fail(isinstance(payload, dict), "Tool input must be a JSON object")
    try:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        raise LabInputError("Tool input must be serializable JSON") from None
    _fail(len(data.encode("utf-8")) <= 20000, "Tool input exceeds 20 KB")
    return payload

def json_guard(p):
    from jsonschema import Draft202012Validator, exceptions
    document, schema = p.get("document"), p.get("schema")
    _fail(isinstance(schema, dict), "schema must be an object")
    allowed = {"type", "properties", "required", "items", "additionalProperties",
               "minimum", "maximum", "minLength", "maxLength", "minItems",
               "maxItems", "enum", "description", "title", "$schema"}
    def walk(node, depth=0):
        _fail(depth <= 8, "schema nesting too deep")
        _fail(isinstance(node, dict), "schema item must be an object")
        for key, value in node.items():
            _fail(key in allowed, f"Unsupported schema keyword: {key[:60]}")
            if key == "properties":
                _fail(isinstance(value, dict) and len(value) <= 100, "properties must be an object of at most 100 fields")
                for child in value.values(): walk(child, depth+1)
            if key == "items": walk(value, depth+1)
            if key == "additionalProperties" and isinstance(value, dict): walk(value, depth+1)
    walk(schema)
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(document), key=lambda e: str(e.path))[:25]
    except (exceptions.SchemaError, ValueError, TypeError) as exc:
        raise LabInputError("Invalid schema; inspect type and supported keywords") from exc
    findings = [_finding("schema_violation", f"Constraint failed: {e.validator}", "error",
                          "/"+"/".join(map(str, e.absolute_path))) for e in errors]
    return _result("json_guard", findings, valid=not bool(errors), violations=len(errors))

def csv_doctor(p):
    text, delimiter = p.get("csv_text"), p.get("delimiter", ",")
    _fail(isinstance(text, str) and 0 < len(text) <= 18000, "csv_text must contain 1 to 18000 characters")
    _fail(delimiter in (",", ";", "\t"), "delimiter must be comma, semicolon or tab")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
    except csv.Error:
        raise LabInputError("CSV parse error") from None
    _fail(len(rows) <= 501 and len(rows) >= 1, "CSV must contain between 1 and 501 rows")
    headings = rows[0]
    _fail(0 < len(headings) <= 40, "CSV must contain 1 to 40 header columns")
    _fail(len(set(headings)) == len(headings), "Duplicate column names are not supported")
    findings = []
    empty = Counter()
    keys = p.get("key_columns") or []
    _fail(isinstance(keys, list) and len(keys) <= 5 and all(isinstance(k, str) and k in headings for k in keys), "key_columns must name up to five existing columns")
    seen=set()
    duplicate=0
    for n, row in enumerate(rows[1:], 2):
        if len(row) != len(headings):
            findings.append(_finding("ragged_row", f"Row has {len(row)} cells; expected {len(headings)}", "error", f"row/{n}"))
        for j, head in enumerate(headings):
            if j >= len(row) or not row[j].strip(): empty[head] += 1
        if keys:
            key=tuple((row[headings.index(k)] if headings.index(k)<len(row) else "") for k in keys)
            if key in seen: duplicate+=1
            else: seen.add(key)
    if duplicate: findings.append(_finding("duplicate_key", f"Found {duplicate} repeated key rows", "warning"))
    for name,count in empty.most_common():
        if count: findings.append(_finding("empty_cells", f"{count} rows have an empty value in this column", "warning", _safe_key(name)))
    return _result("csv_doctor", findings, rows=len(rows)-1, columns=len(headings), duplicates=duplicate,
                   columns_with_missing=len(empty))

def _money(v):
    _fail(isinstance(v, (str, int, float)) and not isinstance(v, bool), "Amount must be numeric")
    try: d=Decimal(str(v))
    except InvalidOperation: raise LabInputError("Invalid money amount") from None
    _fail(d.is_finite() and abs(d) <= Decimal("1000000000"), "Non-finite or excessive amount")
    return d

def invoice_audit(p):
    lines=p.get("lines")
    _fail(isinstance(lines, list) and 0 < len(lines) <= 100, "lines must contain 1 to 100 entries")
    net=Decimal("0"); tax=Decimal("0"); findings=[]
    for i,line in enumerate(lines):
        _fail(isinstance(line,dict) and all(k in line for k in ("quantity","unit_price")), "Each line needs quantity and unit_price")
        q=_money(line["quantity"]); unit=_money(line["unit_price"])
        rate=_money(line.get("tax_rate",0))
        _fail(Decimal("0") <= rate <= Decimal("100") and Decimal("0") <= q <= Decimal("1000000"), "Invalid quantity or tax_rate")
        amount=(q*unit).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        vat=(amount*rate/Decimal("100")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        net+=amount;tax+=vat
        if "declared_net" in line and abs(_money(line["declared_net"])-amount)>Decimal("0.01"):
            findings.append(_finding("line_mismatch", "Declared line net differs from recalculated net", "error", f"lines/{i}"))
    gross=net+tax
    for key,actual in (("declared_net",net),("declared_tax",tax),("declared_gross",gross)):
        if key in p and abs(_money(p[key])-actual)>Decimal("0.01"):
            findings.append(_finding("total_mismatch", f"{key} differs from recalculated amount", "error", key))
    return _result("invoice_audit",findings,computed_net=str(net),computed_tax=str(tax),computed_gross=str(gross),
                   currency=str(p.get("currency",""))[:10])

SECRET_PATTERNS = (
    ("private_key","high",re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws_access_key","high",re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github_token","high",re.compile(r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9]{30,}\b")),
    ("github_fine_grained","high",re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("bearer_token","medium",re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b",re.I)),
    ("stripe_key","high",re.compile(r"\b(?:sk_live_|rk_live_)[A-Za-z0-9]{12,}\b")),
)
def secret_shield(p):
    text=p.get("text")
    _fail(isinstance(text,str) and len(text)<=14000,"text must be a string of at most 14000 characters")
    findings=[]
    for name,severity,pattern in SECRET_PATTERNS:
        matches=list(pattern.finditer(text))[:20]
        if matches: findings.append(_finding(name,f"Found {len(matches)} possible matches; raw tokens are never returned",severity))
    return _result("secret_shield",findings,possible_secret_categories=len(findings),scanned_characters=len(text))

def openapi_preflight(p):
    doc=p.get("spec")
    _fail(isinstance(doc,dict),"spec must be an OpenAPI JSON object")
    f=[]
    if not isinstance(doc.get("openapi"),str) or not str(doc["openapi"]).startswith("3."):
        f.append(_finding("version","OpenAPI 3.x version is required","error"))
    info=doc.get("info") or {}
    if not isinstance(info,dict) or not info.get("title") or not info.get("version"):
        f.append(_finding("info","info.title and info.version are required","error"))
    paths=doc.get("paths")
    _fail(isinstance(paths,dict) and len(paths)<=100,"paths must be an object with at most 100 entries")
    operations=0;ids=set()
    for route,definition in paths.items():
        if not isinstance(route,str) or not route.startswith("/") or not isinstance(definition,dict):
            f.append(_finding("invalid_path","Paths must begin with / and contain operations","error"))
            continue
        for method, op in definition.items():
            if method.lower() not in ("get","post","put","patch","delete","head","options","trace"): continue
            operations+=1
            if not isinstance(op,dict):
                f.append(_finding("invalid_operation","Operation must be an object","error",route));continue
            ident=op.get("operationId")
            if not ident:f.append(_finding("missing_operation_id","operationId absent","warning",route))
            elif ident in ids:f.append(_finding("duplicate_operation_id","operationId is duplicated","error",route))
            else: ids.add(ident)
            if not op.get("responses"):f.append(_finding("no_responses","No responses declared","error",route))
    if operations==0:f.append(_finding("empty_paths","No HTTP operations found","error"))
    return _result("openapi_preflight",f,operations=operations,paths=len(paths))

def mcp_preflight(p):
    doc=p.get("server")
    _fail(isinstance(doc,dict),"server must be a server.json object")
    f=[]
    name=doc.get("name","")
    if not isinstance(name,str) or len(name)<3 or "/" not in name:
        f.append(_finding("server_name","name should use a scoped package name","error"))
    ver=doc.get("version")
    if not isinstance(ver,str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?",ver):
        f.append(_finding("version","version should be SemVer, e.g. 0.1.0","warning"))
    remotes=doc.get("remotes") or []
    if not isinstance(remotes,list) or len(remotes)>10:
        raise LabInputError("remotes must be a list of up to 10 items")
    for index, remote in enumerate(remotes):
        if not isinstance(remote,dict):
            f.append(_finding("bad_remote","Remote entry must be an object","error",str(index)));continue
        url=remote.get("url","")
        parsed=urlparse(url) if isinstance(url,str) else None
        if not parsed or parsed.scheme!="https" or not parsed.hostname:
            f.append(_finding("https_required","Remote URL must use HTTPS","error",str(index)))
        if remote.get("type") not in ("streamable-http","sse"):
            f.append(_finding("transport","Unknown remote transport type","error",str(index)))
    if not remotes and not doc.get("packages"):
        f.append(_finding("missing_transport","No remote or package transport defined","error"))
    if not doc.get("description"):f.append(_finding("missing_description","Description is recommended","warning"))
    return _result("mcp_preflight",f,remote_count=len(remotes))

def header_audit(p):
    supplied=p.get("headers")
    _fail(isinstance(supplied,dict) and len(supplied)<=80,"headers must be an object with at most 80 entries")
    h={str(k).lower():str(v)[:500] for k,v in supplied.items()}
    f=[]
    for header in ("strict-transport-security","content-security-policy","x-content-type-options","referrer-policy"):
        if header not in h:f.append(_finding("missing_header",f"Missing {header}","warning",header))
    if "x-content-type-options" in h and h["x-content-type-options"].lower().strip()!="nosniff":
        f.append(_finding("nosniff_missing","x-content-type-options should be nosniff","warning"))
    if "content-security-policy" in h and "'unsafe-inline'" in h["content-security-policy"]:
        f.append(_finding("unsafe_inline","CSP contains unsafe-inline","warning"))
    if "x-frame-options" not in h and "frame-ancestors" not in h.get("content-security-policy",""):
        f.append(_finding("frame_control","No X-Frame-Options or CSP frame-ancestors","warning"))
    return _result("header_audit",f,headers_supplied=len(h))

def robots_check(p):
    rules=p.get("robots_txt");agent=p.get("agent","*");path=p.get("path","/")
    _fail(isinstance(rules,str) and len(rules)<=14000,"robots_txt must be text of at most 14000 chars")
    _fail(isinstance(agent,str) and 1<=len(agent)<=120,"agent must be a short user-agent string")
    _fail(isinstance(path,str) and path.startswith("/") and len(path)<=2000,"path must start with /")
    f=[]
    advanced=any("*" in line.split(":",1)[-1] or "$" in line for line in rules.splitlines()
                 if ":" in line and line.lower().strip().startswith(("disallow:","allow:")))
    if advanced:f.append(_finding("complex_patterns","Wildcard and end-anchor semantics may differ across crawlers","warning"))
    parser=RobotFileParser()
    parser.parse(rules.splitlines()[:500])
    allowed=bool(parser.can_fetch(agent,"https://example.invalid"+path))
    return _result("robots_check",f,can_fetch_by_parser=allowed,agent=agent,path=path,
                   note="Parser result is not permission to access a service")

def _shape(value, base="", depth=0, dest=None):
    if dest is None: dest={}
    _fail(depth <= 7 and len(dest)<=300,"Object too deeply nested or too many fields")
    kind="object" if isinstance(value,dict) else ("array" if isinstance(value,list) else type(value).__name__)
    dest[base or "$"]=kind
    if isinstance(value,dict):
        for key,item in value.items():
            _fail(isinstance(key,str) and len(key)<=100,"Object keys must be short strings")
            _shape(item,base+"/"+key.replace("/","~1"),depth+1,dest)
    elif isinstance(value,list) and value:
        _shape(value[0],base+"/[]",depth+1,dest)
    return dest

def schema_diff(p):
    before,after=p.get("before"),p.get("after")
    _fail(isinstance(before,(list,dict)) and isinstance(after,(list,dict)),
          "before and after must be JSON objects or arrays")
    a=_shape(before);b=_shape(after)
    old=set(a);new=set(b)
    added=sorted(new-old);removed=sorted(old-new);changed=sorted(k for k in new&old if a[k]!=b[k])
    findings=[_finding("removed_field","Field removed","warning",k) for k in removed[:10]]
    findings += [_finding("changed_type",f"Type changed: {a[k]} -> {b[k]}","error",k) for k in changed[:10]]
    return _result("schema_diff",findings,added=added[:30],removed=removed[:30],
                   changed=changed[:30],added_count=len(added),removed_count=len(removed),
                   type_change_count=len(changed))

HANDLERS={"json_guard":json_guard,"csv_doctor":csv_doctor,"invoice_audit":invoice_audit,
          "secret_shield":secret_shield,"openapi_preflight":openapi_preflight,
          "mcp_preflight":mcp_preflight,"header_audit":header_audit,
          "robots_check":robots_check,"schema_diff":schema_diff}

def run_lab(slug,payload):
    _fail(slug in HANDLERS,"Unknown experiment tool")
    return HANDLERS[slug](_check_size(payload))
