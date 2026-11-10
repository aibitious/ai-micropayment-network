import pytest
from agent404.lab import TOOLS, run_lab, LabInputError, describe_tools

def test_tool_count_and_descriptors():
    assert len(TOOLS) == 9
    assert len(describe_tools()) == 9
    assert len({r["slug"] for r in describe_tools()}) == 9
    assert all(item["price"]["amount"] == 0 for item in describe_tools())

def test_json_guard_success():
    result=run_lab("json_guard",{"document":{"id":4},"schema":{"type":"object","required":["id"],"properties":{"id":{"type":"integer"}}}})
    assert result["status"] == "ok"

def test_json_guard_missing_required():
    result=run_lab("json_guard",{"document":{},"schema":{"type":"object","required":["id"]}})
    assert result["status"] == "issues" and result["findings"][0]["code"]=="schema_violation"

def test_json_guard_rejects_remote_refs():
    with pytest.raises(LabInputError):
        run_lab("json_guard",{"document":{},"schema":{"$ref":"https://example.org/malicious.json"}})

def test_csv_doctor_missing_and_duplicates():
    x=run_lab("csv_doctor",{"csv_text":"id,name\n1,Ann\n1,\n2,Bob\n","key_columns":["id"]})
    assert x["details"]["duplicates"]==1
    assert x["details"]["columns_with_missing"]==1

def test_csv_doctor_detects_ragged_rows():
    x=run_lab("csv_doctor",{"csv_text":"a,b\n1\n2,3,4\n"})
    assert any(y["code"]=="ragged_row" for y in x["findings"])

def test_csv_doctor_rejects_many_rows():
    with pytest.raises(LabInputError):
        run_lab("csv_doctor",{"csv_text":"a\n"+"x\n"*501})

def test_invoice_audit_decimal_rounding():
    r=run_lab("invoice_audit",{"currency":"PLN","lines":[{"quantity":"2","unit_price":"10.00","tax_rate":"23"}],"declared_net":"20.00","declared_tax":"4.60","declared_gross":"24.60"})
    assert r["status"]=="ok" and r["details"]["computed_gross"]=="24.60"

def test_invoice_audit_wrong_total():
    r=run_lab("invoice_audit",{"lines":[{"quantity":1,"unit_price":"11","tax_rate":0}],"declared_gross":"12"})
    assert any(y["code"]=="total_mismatch" for y in r["findings"])

def test_invoice_audit_rejects_nan():
    with pytest.raises(LabInputError):
        run_lab("invoice_audit",{"lines":[{"quantity":1,"unit_price":"NaN"}]})

def test_secret_shield_no_leak():
    token="ghp_"+"z"*36
    r=run_lab("secret_shield",{"text":"please hide "+token})
    assert r["status"]=="issues" and r["details"]["possible_secret_categories"]==1
    assert token not in str(r)

def test_openapi_preflight_lints():
    r=run_lab("openapi_preflight",{"spec":{"openapi":"3.1.0","info":{"title":"Demo","version":"1.0"},"paths":{"/x":{"get":{"responses":{"200":{"description":"ok"}}}}}}})
    assert any(x["code"]=="missing_operation_id" for x in r["findings"])

def test_openapi_preflight_empty():
    r=run_lab("openapi_preflight",{"spec":{"paths":{}}})
    assert r["status"]=="issues"

def test_mcp_preflight_valid():
    r=run_lab("mcp_preflight",{"server":{"name":"io.github.example/server","version":"0.1.0","description":"Example","remotes":[{"type":"streamable-http","url":"https://example.org/mcp"}]}})
    assert r["status"]=="ok"

def test_mcp_preflight_http_flag():
    r=run_lab("mcp_preflight",{"server":{"name":"io.github.example/server","version":"0.1.0","remotes":[{"type":"streamable-http","url":"http://example.org/mcp"}]}})
    assert any(x["code"]=="https_required" for x in r["findings"])

def test_header_audit():
    r=run_lab("header_audit",{"headers":{"content-type":"application/json"}})
    assert len(r["findings"])>=3

def test_header_audit_complete():
    r=run_lab("header_audit",{"headers":{"strict-transport-security":"max-age=31536000","content-security-policy":"default-src 'none'; frame-ancestors 'none'","x-content-type-options":"nosniff","referrer-policy":"no-referrer"}})
    assert r["status"]=="ok"

def test_robots_check_rejects_path_traversal_payload_as_url():
    with pytest.raises(LabInputError):
        run_lab("robots_check",{"robots_txt":"User-agent: *\nDisallow: /admin","path":"https://other.org"})

def test_robots_check():
    r=run_lab("robots_check",{"robots_txt":"User-agent: *\nDisallow: /private\n","path":"/private/data"})
    assert r["details"]["can_fetch_by_parser"] is False

def test_schema_diff_detects_drift():
    r=run_lab("schema_diff",{"before":{"id":2,"nested":{"name":"a"}},"after":{"id":"2","nested":{"age":3}}})
    assert r["details"]["type_change_count"]==1
    assert r["details"]["added_count"]==1
    assert r["details"]["removed_count"]==1

def test_schema_diff_unchanged():
    assert run_lab("schema_diff",{"before":{"a":[{"x":1}]},"after":{"a":[{"x":2}]}})["status"]=="ok"

def test_payload_limit():
    with pytest.raises(LabInputError):
        run_lab("secret_shield",{"text":"x"*21000})

def test_no_url_fetch():
    with pytest.raises(LabInputError):
        run_lab("probe_url",{"url":"http://169.254.169.254/"})

def test_no_document_echo_for_invoice():
    r=run_lab("invoice_audit",{"lines":[{"quantity":"1","unit_price":"13.20","description":"private"}]})
    assert "private" not in str(r)
