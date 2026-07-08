# Security Policy

## Supported scope

Security fixes are prioritized for the default branch and the latest published repository state.

## Reporting a vulnerability

Please do not open public GitHub issues for suspected security vulnerabilities.

Use one of these paths instead:

1. GitHub private vulnerability reporting, if it is enabled for this repository.
2. Email `husnainbinmunawar@gmail.com` with the subject line `VoxRelay AI security report`.

Include:

- a clear description of the issue;
- affected endpoints, files, or workflows;
- reproduction steps or a proof of concept;
- impact assessment and any suggested remediation.

## Disclosure expectations

- Do not include real secrets, customer data, or credentials in reports.
- Allow reasonable time for investigation and remediation before public disclosure.
- Be explicit if the issue affects demo-mode assumptions versus production deployment patterns.

## Security posture notes

This repository includes security-oriented controls such as tenant isolation, role checks, API key hashing, request IDs, audit records, and redaction helpers. It does not claim compliance certification, formal penetration-test coverage, or suitability for regulated production use without further hardening.
