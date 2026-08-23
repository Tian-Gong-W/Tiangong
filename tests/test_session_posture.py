from __future__ import annotations

import json
from datetime import datetime, timezone

from tonmen.evidence import EvidenceRecord
from tonmen.intelligence import FactKind, Severity, parse_evidence
from tonmen.tools.adapters import CrawlerAdapter


def _crawler_evidence(*records: dict) -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        id="e-session-posture",
        tool="crawler",
        target="https://localhost",
        argv=("python", "-m", "tonmen.tools.runners.crawler"),
        exit_code=0,
        stdout="\n".join(json.dumps(item) for item in records) + "\n",
        stderr="",
        started_at=now,
        finished_at=now,
    )


def test_crawler_declares_observation_only_session_capabilities():
    capabilities = set(CrawlerAdapter.spec.capabilities)
    assert "session_cookie.observe" in capabilities
    assert "cors.observe" in capabilities
    assert "security_headers.observe" in capabilities
    assert "session.takeover" not in capabilities
    assert not any(item.endswith(".execute") for item in capabilities)


def test_entry_page_session_posture_becomes_conservative_findings_without_cookie_values():
    evidence = _crawler_evidence(
        {
            "type": "page",
            "url": "https://localhost/",
            "status": 200,
            "title": "Home",
            "content_type": "text/html",
            "depth": 0,
            "bytes": 200,
            "truncated": False,
            "redirected": False,
            "security": {
                "https": True,
                "hsts": False,
                "csp": False,
                "x_content_type_options": True,
                "referrer_policy": True,
                "frame_options": True,
                "permissions_policy": False,
                "cache_control": True,
                "cors_allow_origin": "*",
                "cors_allow_credentials": True,
                "cors_vary_origin": False,
                "cookies": [
                    {
                        "name": "sid",
                        "secure": False,
                        "httponly": False,
                        "samesite": None,
                        "partitioned": False,
                    }
                ],
                "cookie_values_recorded": False,
            },
        }
    )

    facts = parse_evidence(evidence)
    web = [fact for fact in facts if fact.kind is FactKind.WEB]
    findings = [fact for fact in facts if fact.kind is FactKind.FINDING]

    assert len(web) == 1
    assert web[0].data["security"]["cookie_values_recorded"] is False
    assert len(findings) == 4
    assert {fact.data["issue"] for fact in findings} == {
        "hsts_missing",
        "csp_missing",
        "cookie_policy",
        "cors_wildcard",
    }
    cookie = next(fact for fact in findings if fact.data["issue"] == "cookie_policy")
    assert cookie.severity is Severity.LOW
    assert cookie.data["cookie_name"] == "sid"
    assert cookie.data["missing_flags"] == ["Secure", "HttpOnly", "SameSite"]
    assert cookie.data["cookie_value_recorded"] is False
    assert "secret" not in json.dumps([fact.data for fact in facts])


def test_deeper_pages_keep_security_metadata_but_do_not_multiply_posture_findings():
    evidence = _crawler_evidence(
        {
            "type": "page",
            "url": "http://localhost/child",
            "status": 200,
            "title": "Child",
            "content_type": "text/html",
            "depth": 1,
            "bytes": 100,
            "truncated": False,
            "security": {
                "https": False,
                "hsts": False,
                "csp": False,
                "cors_allow_origin": "*",
                "cors_allow_credentials": False,
                "cookies": [{"name": "pref", "secure": False, "httponly": False, "samesite": None}],
                "cookie_values_recorded": False,
            },
        }
    )

    facts = parse_evidence(evidence)
    assert [fact.kind for fact in facts] == [FactKind.WEB]
    assert facts[0].data["security"]["cookies"][0]["name"] == "pref"
