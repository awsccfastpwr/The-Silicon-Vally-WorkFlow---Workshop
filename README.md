# AWS Silicon Valley Workflow Workshop

Official workshop repository for the AWS Silicon Valley Workflow series hosted by AWS Cloud Club FAST Peshawar.

This repository contains the workshop session material, FastAPI examples, AWS deployment exercises, and the certificate generation tooling used for signed QR-verified attendance certificates.

## Repository Structure

```text
.
├── sessions/
│   ├── 01-the-hacker-setup/
│   ├── 02-python-fastapi/
│   ├── 03-cloud-access/
│   └── 04-final-production-launch/
├── tools/
│   └── certificate-generator/
├── docs/
└── README.md
```

## Sessions

| Folder | Focus |
| --- | --- |
| `sessions/01-the-hacker-setup` | Linux terminal, WSL, Git, and GitHub CLI setup |
| `sessions/02-python-fastapi` | Python backend foundations and FastAPI APIs |
| `sessions/03-cloud-access` | AWS access, IAM, billing safety, and cloud setup |
| `sessions/04-final-production-launch` | Docker, Lambda container deployment, API Gateway, and production launch |

## Certificate Generator

The certificate workflow lives in:

```text
tools/certificate-generator/
```

It generates signed attendance certificates from CSV or XLSX input and exports PDFs, PNGs, manifests, and a public verifier key. Private signing keys and generated outputs are ignored by Git.

## Public Repository Safety

This repository is safe to keep public as long as these files are never committed:

- `.certificate_keys/`
- `outputs/`
- generated manifests
- real attendee spreadsheets
- private API keys or cloud credentials
- local virtual environments and caches

GitHub secret scanning, push protection, Dependabot alerts, and Dependabot security updates are enabled for the repository.

## Technical Team

- Technical Lead: Raqeeb
- Technical Co-Leads: Abdul Kalam, Muhammad Taha, Hisam Mehboob
- Club Lead: Rayyan Shaheer

## Repository

```text
awsccfastpwr/aws-silicon-valley-workflow-workshop
```
