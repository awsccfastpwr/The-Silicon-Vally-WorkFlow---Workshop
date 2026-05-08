# AWS Silicon Valley Workflow Certificate Generator

Certificate generation workflow for AWS Silicon Valley Workflow at FAST Peshawar, including reusable certificate assets, sample attendee input, and verification-ready output structure.

![Certificate template preview](docs/images/certificate-template-preview.png)

## What This Project Does

The main generator creates spoof-resistant certificates from a CSV or XLSX attendee list. Each certificate includes:

- one PDF certificate per attendee
- one PNG certificate per attendee
- one combined PDF
- CSV and JSON manifests
- a signed verification QR code
- a public key export for the future verifier website

The signed token includes an `email_sha256` hash, not the raw email. Raw email appears only in the local manifests.

## Project Structure

```text
.
├── assets/
│   ├── logos/
│   └── templates/
├── docs/
│   └── images/
├── examples/
├── scripts/
├── outputs/
├── requirements.txt
└── README.md
```

Key paths:

- `scripts/generate_certificates.py` - current signed certificate generator
- `scripts/generate_certificates_legacy.py` - older CSV-only generator kept for reference
- `assets/templates/aws-session-attendee-certificate-template.pdf` - certificate background template
- `assets/logos/aws-cc-fast-pwr-black-fg-no-bg.png` - AWS Cloud Club FAST Peshawar logo
- `examples/attendees-example.csv` - sample input file
- `outputs/` - generated files and workbook exports
- `.certificate_keys/` - local signing keys, ignored by Git

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`pdf2image` also needs Poppler installed on the machine. On Ubuntu/Debian:

```bash
sudo apt-get install poppler-utils
```

## Input Format

Use a `.csv` or `.xlsx` file with these required columns:

```csv
name,rollno,email
Ayesha Khan,22P-1234,ayesha@example.com
Muhammad Ali,22P-5678,muhammad@example.com
```

Accepted aliases:

- `name`: `full_name`, `attendee_name`, `attendee`, `participant_name`, `participant`
- `rollno`: `roll_no`, `roll no`, `roll_number`, `roll number`, `student_id`, `student id`
- `email`: `email_address`, `email address`

Legacy `.xls` files are not supported. Save them as `.xlsx` or `.csv`.

## Generate Certificates

Run the generator from this folder:

```bash
.venv/bin/python scripts/generate_certificates.py \
  --input examples/attendees-example.csv \
  --verify-base-url https://rayyanshaheer.com/verify
```

By default, generated files are written to:

- `outputs/certificates/individual/pdf/`
- `outputs/certificates/individual/png/`
- `outputs/certificates/all_certificates.pdf`
- `outputs/certificates/manifest.csv`
- `outputs/certificates/manifest.json`

Individual files are named as:

```text
RollNo_Name.pdf
RollNo_Name.png
```

## Defaults

The script uses:

- Event: `AWS Silicon Valley Workflow`
- Sessions: `5`
- Signer: `Rayyan Shaheer`
- Signer title: `AWS Cloud Club Captain at FAST Peshawar`
- Verification URL: provided through `--verify-base-url`

You can override these values with CLI flags:

```bash
.venv/bin/python scripts/generate_certificates.py \
  --input attendees.csv \
  --verify-base-url https://rayyanshaheer.com/verify \
  --event "AWS Silicon Valley Workflow" \
  --sessions-total 5 \
  --signer-name "Rayyan Shaheer" \
  --signer-title "AWS Cloud Club Captain at FAST Peshawar"
```

## Verification Keys

On first run, the generator creates:

- `.certificate_keys/private_key.pem`
- `.certificate_keys/public_key.pem`
- `.certificate_keys/public_key.json`

Never share or upload `private_key.pem`. It is ignored by `.gitignore`.

The public key is safe to copy into the verification website. If you rotate keys later, keep old public keys in the verifier until all old certificates no longer need verification.

## Verification URL Changes

If the verification site moves:

- update `--verify-base-url` for newly generated certificates
- keep the old URL redirected, because old QR codes point to it
- copy the new public key into the website if you rotate the private key
- never upload the private key to GitHub or any website

The current planned verifier URL is:

```text
https://rayyanshaheer.com/verify
```
