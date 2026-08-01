# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Instead, report them privately by opening a [GitHub Security Advisory](https://github.com/sahilleth/incident-commander/security/advisories/new) or emailing the maintainers through GitHub (use the private contact option on the repository if available).

Include:

- Description of the issue and potential impact
- Steps to reproduce
- Affected versions
- Any suggested fix (optional)

We aim to acknowledge reports within **72 hours** and will work on a fix before public disclosure when possible.

## Security considerations

Incident Commander runs `kubectl` against clusters you configure and can execute rollbacks after human approval. Treat:

- **Kubeconfig / cluster credentials** as highly sensitive
- **API keys** (`GROQ_API_KEY`, etc.) as secrets — use `.env`, never commit them
- **The API server** (`incident-commander serve`) as trusted-network only until auth is implemented

Do not expose the API or kube credentials to untrusted networks without additional hardening.
