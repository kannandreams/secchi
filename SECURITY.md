# Security Policy

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues, pull requests, or discussions.

Public disclosure can expose users before a fix is available and may make it easier for others to exploit the issue.

Instead, use GitHub's private vulnerability reporting feature:

1. Open the [Secchi Security](https://github.com/kannandreams/secchi/security) page.
2. Select **Report a vulnerability** under **Security advisories**.
3. Provide the details requested in the private report.

Private vulnerability reporting allows the maintainers to investigate the issue confidentially, coordinate a fix, and publish an advisory when appropriate.

If the **Report a vulnerability** option is unavailable, please contact the project maintainer privately through GitHub before sharing any vulnerability details. Do not include sensitive information in a public issue.

## What to Include

Please include as much of the following information as possible:

* A clear description of the vulnerability
* The affected Secchi version, commit, or component
* Steps to reproduce the issue
* A minimal proof of concept, where safe to provide
* The potential impact
* Any suggested mitigation or fix
* Whether the vulnerability affects the CLI, TUI, MCP server, reports, registry adapters, or another integration

Please avoid including secrets, personal data, or production credentials in a report.

## Response Process

The maintainers will acknowledge a private report when possible, investigate its validity and impact, and coordinate remediation with the reporter.

Depending on the issue, the response may include:

* A patch release
* A mitigation or configuration recommendation
* A GitHub security advisory
* A request for additional reproduction details

Please allow time for investigation and responsible coordination before making the issue public.

## Public Issues

Public issues are appropriate for general bugs, feature requests, documentation problems, and questions that do not expose a security weakness.

When in doubt, report the issue privately first.
