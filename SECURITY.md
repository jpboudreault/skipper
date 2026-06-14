# Security Policy

## Supported versions

Only the latest release on the `main` branch is supported.

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Email the maintainers privately with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and aim to provide a fix or mitigation plan within 7 days.

## Security best practices for deployments

- Set `DEV_MODE=false` in production
- Generate a strong `JWT_SECRET` (`openssl rand -hex 32`)
- Restrict `admin_emails` in `tenants.json` to trusted addresses
- Keep Fly.io secrets out of version control
- Use HTTPS only (enforced by Fly.io)
