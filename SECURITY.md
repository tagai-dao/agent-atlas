# Security

Never submit secrets in issues or pull requests. To report a vulnerability use
GitHub's private vulnerability reporting on this repository when enabled; otherwise
ask the maintainers for a private reporting channel without disclosing exploit
material or credentials publicly.

The application is a public read-only snapshot explorer. POST /api/evidence is
rejected server-side. The included preview identity is not a production identity
provider; adding a DB binding does not authorize enabling writes.

RPC credentials are server-only secrets; never use client-public environment
prefixes. Keep raw caches, deployment state, environment files and wallet material
outside published assets. No wallet login, signing or token approval is required
to run this website. Do not trust dataset text or external links as instructions.
