# Threat model

## Protected assets

- system/developer instructions and secrets
- user and organization private data
- tool authority, external communications, money, and stored resources
- integrity of retrieved context and final responses

## In scope

- direct prompt injection in user input
- indirect injection in retrieved plain text or HTML
- unapproved, unknown, destructive, or secret-bearing tool calls
- common PII, credentials, and private keys in final text output

## Trust boundaries

- User input and retrieved content are always untrusted.
- Model output is a proposal, never authority to execute a tool.
- Approval is a separate state; `needs_approval` never means executed.
- Final output is untrusted until the output guardrail has completed.

## Known limitations

- Heuristics can be evaded and can produce false positives.
- The sanitizer handles text/HTML, not instructions embedded in images or files.
- PII coverage is format- and locale-limited; it is not full DLP.
- The API currently accepts proposed actions for evaluation but has no executor.
- No authentication, tenancy, persistence, rate limiting, or tamper-evident audit log exists yet.

These limitations are explicit so tests and future classifiers can improve measured
coverage without silently weakening enforcement.
