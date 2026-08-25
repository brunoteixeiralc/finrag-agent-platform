"""Tests for the content-safe local document validation command."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIRECTORY = Path(__file__).parent.parent
SCRIPT = PROJECT_DIRECTORY / "scripts" / "validate_documents.py"
FIXTURES = PROJECT_DIRECTORY / "tests" / "fixtures" / "documents"


def test_validation_script_reports_only_safe_measurements() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(FIXTURES / "synthetic_credit_notes.txt"),
            str(FIXTURES / "synthetic_risk_report.pdf"),
        ],
        cwd=PROJECT_DIRECTORY,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    measurements = [json.loads(line) for line in completed.stdout.splitlines()]

    assert [measurement["filename"] for measurement in measurements] == [
        "synthetic_credit_notes.txt",
        "synthetic_risk_report.pdf",
    ]
    assert [measurement["chunks"] for measurement in measurements] == [1, 2]
    assert all(len(measurement["sha256"]) == 64 for measurement in measurements)
    assert "Synthetic Credit Portfolio Notes" not in completed.stdout
    assert "Adverse Scenario" not in completed.stdout
    assert completed.stderr == ""
