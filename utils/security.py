"""
Security audit utilities for the S3 mount and data files.

Scans for:
  - Unencrypted sensitive files (private keys, .pem, .pfx, etc.)
  - CSV headers that may contain leaked keys/tokens/secrets
  - .env files or credential stores in the data mount
  - Files with suspicious naming patterns
"""

import os
import re
import csv
from pathlib import Path
from dataclasses import dataclass, field

S3_MOUNT = Path(__file__).parent.parent.parent / "data" / "agency-s3"
HACKATHON_ROOT = Path(__file__).parent.parent.parent / "hackathon"

# Patterns that indicate sensitive file types
SENSITIVE_EXTENSIONS = {
    ".pem", ".key", ".pfx", ".p12", ".jks", ".keystore",
    ".cer", ".crt", ".der", ".pkcs12",
}

SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.staging",
    "credentials", "credentials.json", "credentials.yaml",
    "secrets.json", "secrets.yaml", "secrets.yml",
    "id_rsa", "id_ed25519", "id_ecdsa",
    "service-account.json", "gcloud-key.json",
    "aws_credentials", "config.ini",
}

# Header patterns that suggest leaked keys/tokens in CSV data
LEAKED_KEY_PATTERNS = [
    re.compile(r"(?i)(api[_\-]?key|apikey)"),
    re.compile(r"(?i)(secret[_\-]?key|secretkey)"),
    re.compile(r"(?i)(access[_\-]?key|accesskey)"),
    re.compile(r"(?i)(auth[_\-]?token|authtoken)"),
    re.compile(r"(?i)(password|passwd|pwd)"),
    re.compile(r"(?i)(private[_\-]?key|privatekey)"),
    re.compile(r"(?i)(bearer[_\-]?token)"),
    re.compile(r"(?i)(client[_\-]?secret)"),
    re.compile(r"(?i)(encryption[_\-]?key)"),
    re.compile(r"(?i)(ssh[_\-]?key)"),
    re.compile(r"(?i)(aws[_\-]?secret)"),
    re.compile(r"(?i)(database[_\-]?password|db[_\-]?password)"),
    re.compile(r"(?i)(connection[_\-]?string)"),
    re.compile(r"(?i)(credit[_\-]?card|card[_\-]?number|cvv)"),
    re.compile(r"(?i)(social[_\-]?security|ssn|sin\b)"),
]

# Content patterns that look like actual secrets
SECRET_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),  # OpenAI / Stripe secret key
    re.compile(r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)ghp_[a-zA-Z0-9]{36}"),  # GitHub PAT
    re.compile(r"(?i)glpat-[a-zA-Z0-9\-]{20,}"),  # GitLab PAT
]


@dataclass
class SecurityFinding:
    severity: str  # "HIGH", "MEDIUM", "LOW"
    category: str
    file_path: str
    detail: str


@dataclass
class SecurityReport:
    scan_path: str
    files_scanned: int = 0
    findings: list = field(default_factory=list)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HIGH")

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "MEDIUM")

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "LOW")

    @property
    def is_clean(self) -> bool:
        return len(self.findings) == 0


def _check_csv_headers(filepath: Path) -> list[SecurityFinding]:
    """Check CSV file headers for leaked key column names."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            for header in headers:
                for pattern in LEAKED_KEY_PATTERNS:
                    if pattern.search(header):
                        findings.append(SecurityFinding(
                            severity="HIGH",
                            category="Leaked Key in Header",
                            file_path=str(filepath),
                            detail=f"CSV header '{header}' matches sensitive pattern: {pattern.pattern}",
                        ))
                        break

            # Check first 5 data rows for secret-like values
            for row_num, row in enumerate(reader):
                if row_num >= 5:
                    break
                for col_idx, value in enumerate(row):
                    for sp in SECRET_VALUE_PATTERNS:
                        if sp.search(str(value)):
                            col_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                            findings.append(SecurityFinding(
                                severity="HIGH",
                                category="Secret Value Detected",
                                file_path=str(filepath),
                                detail=f"Row {row_num+1}, column '{col_name}' contains a value matching secret pattern",
                            ))
                            break
    except Exception:
        pass
    return findings


def _check_file_sensitivity(filepath: Path) -> list[SecurityFinding]:
    """Check if a file is a known sensitive file type."""
    findings = []
    name_lower = filepath.name.lower()
    ext = filepath.suffix.lower()

    if ext in SENSITIVE_EXTENSIONS:
        findings.append(SecurityFinding(
            severity="HIGH",
            category="Sensitive File Type",
            file_path=str(filepath),
            detail=f"Unencrypted sensitive file detected: {filepath.name} ({ext})",
        ))

    if name_lower in SENSITIVE_FILENAMES:
        findings.append(SecurityFinding(
            severity="HIGH",
            category="Credential File",
            file_path=str(filepath),
            detail=f"Credential/secret file detected: {filepath.name}",
        ))

    # Check for .env files with various suffixes
    if name_lower.startswith(".env"):
        findings.append(SecurityFinding(
            severity="MEDIUM",
            category="Environment File",
            file_path=str(filepath),
            detail=f"Environment configuration file: {filepath.name}",
        ))

    return findings


def run_security_audit(scan_s3: bool = True, scan_hackathon: bool = False) -> SecurityReport:
    """
    Run a security audit on the data directories.

    Args:
        scan_s3: Scan the S3 mount directory
        scan_hackathon: Also scan the hackathon repo data directories

    Returns:
        SecurityReport with all findings
    """
    paths_to_scan = []
    if scan_s3 and S3_MOUNT.exists():
        paths_to_scan.append(S3_MOUNT)
    if scan_hackathon and HACKATHON_ROOT.exists():
        paths_to_scan.append(HACKATHON_ROOT)

    report = SecurityReport(
        scan_path=", ".join(str(p) for p in paths_to_scan) or "No paths available"
    )

    for base_path in paths_to_scan:
        try:
            for filepath in base_path.rglob("*"):
                if not filepath.is_file():
                    continue
                # Skip node_modules and .git
                parts = filepath.parts
                if "node_modules" in parts or ".git" in parts:
                    continue

                report.files_scanned += 1

                # Check file type sensitivity
                report.findings.extend(_check_file_sensitivity(filepath))

                # Check CSV headers
                if filepath.suffix.lower() == ".csv":
                    report.findings.extend(_check_csv_headers(filepath))

                # Check JSONL files for secret patterns (first few lines)
                if filepath.suffix.lower() in (".jsonl", ".json"):
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                            for line_num, line in enumerate(f):
                                if line_num >= 3:
                                    break
                                for sp in SECRET_VALUE_PATTERNS:
                                    if sp.search(line):
                                        report.findings.append(SecurityFinding(
                                            severity="HIGH",
                                            category="Secret in Data File",
                                            file_path=str(filepath),
                                            detail=f"Line {line_num+1} contains a value matching secret pattern",
                                        ))
                                        break
                    except Exception:
                        pass

        except PermissionError:
            report.findings.append(SecurityFinding(
                severity="LOW",
                category="Access Denied",
                file_path=str(base_path),
                detail="Permission denied scanning directory",
            ))

    # If no paths were scannable, note it
    if not paths_to_scan:
        report.findings.append(SecurityFinding(
            severity="LOW",
            category="No Data Paths",
            file_path="N/A",
            detail="Neither S3 mount nor hackathon data directory is accessible",
        ))

    return report
