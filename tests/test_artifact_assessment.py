from __future__ import annotations

from tonmen.artifacts.assessment import assess_artifact


def test_static_assessment_flags_posture_without_claiming_exploitability():
    report = {
        "format": "elf",
        "mitigations": {
            "pie_candidate": False,
            "nx_stack": False,
            "gnu_relro": False,
        },
        "structure": {
            "sections": [
                {"name": ".text", "permissions": "RX"},
                {"name": ".jit", "permissions": "RWX"},
            ],
            "segments": [],
        },
        "linkage": {
            "dependencies": ["libc.so.6"],
            "imports": ["gets", "memcpy", "safe_api"],
            "exports": [],
        },
    }

    assessment = assess_artifact(report)

    assert assessment["mode"] == "static-report-only"
    assert assessment["execution_authority"] is False
    assert assessment["payload_generated"] is False
    assert assessment["artifact_executed"] is False
    assert assessment["vulnerability_confirmed"] is False

    signals = assessment["signals"]
    codes = {item["code"] for item in signals}
    assert "mitigation.nx_stack.absent" in codes
    assert "mitigation.pie_candidate.absent" in codes
    assert "mitigation.gnu_relro.absent" in codes
    assert "memory.section.writable_executable" in codes
    assert "api.unsafe_input_api.gets" in codes
    assert "api.raw_memory_copy_api.memcpy" in codes
    assert all(item["vulnerability_confirmed"] is False for item in signals)
    assert all(item["execution_authority"] is False for item in signals)
    assert all(item["basis"] for item in signals)
    assert all(item["review"] for item in signals)


def test_pe_import_shape_is_supported_without_turning_imports_into_findings():
    report = {
        "format": "pe",
        "mitigations": {
            "aslr": True,
            "nx_compat": True,
            "control_flow_guard": True,
        },
        "structure": {"sections": [{"name": ".text", "permissions": "RX"}]},
        "linkage": {
            "dependencies": ["KERNEL32.dll", "msvcrt.dll"],
            "imports": [
                {"library": "KERNEL32.dll", "symbols": ["ExitProcess"]},
                {"library": "msvcrt.dll", "symbols": ["strcpy", "sprintf"]},
            ],
            "exports": [],
        },
    }

    assessment = assess_artifact(report)

    assert {item["code"] for item in assessment["signals"]} == {
        "api.unsafe_copy_api.strcpy",
        "api.unsafe_format_api.sprintf",
    }
    assert all(item["severity"] == "info" for item in assessment["signals"])
    assert assessment["summary"]["by_severity"]["info"] == 2
    assert assessment["summary"]["by_severity"]["medium"] == 0
    assert "Locate callers" in assessment["review_plan"][0]


def test_unknown_or_positive_mitigation_state_does_not_invent_risk():
    report = {
        "format": "macho",
        "mitigations": {"pie": True},
        "structure": {"sections": [], "segments": []},
        "linkage": {"dependencies": [], "imports": [], "exports": []},
    }

    assessment = assess_artifact(report)

    assert assessment["signals"] == []
    assert assessment["summary"]["signals"] == 0
    assert assessment["review_plan"] == [
        "Continue format-aware static review only if additional evidence justifies deeper analysis."
    ]
