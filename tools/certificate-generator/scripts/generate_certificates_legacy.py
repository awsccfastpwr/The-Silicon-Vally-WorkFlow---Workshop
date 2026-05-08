#!/usr/bin/env python3
"""
Legacy CSV-only certificate generator retained for reference.

The script keeps the Canva PDF template as the certificate background and
overlays attendee names, the event title, the replacement logo, and the
Rayyan Shaheer signature block.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = PROJECT_ROOT / "assets" / "templates" / "aws-session-attendee-certificate-template.pdf"
DEFAULT_LOGO = PROJECT_ROOT / "assets" / "logos" / "aws-cc-fast-pwr-black-fg-no-bg.png"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "certificates-legacy"
DEFAULT_EVENT_TITLE = "AWS Silicon Valley Workflow"
DEFAULT_WORKSHOPS = "5"
DEFAULT_SIGNER_NAME = "Rayyan Shaheer"
DEFAULT_SIGNER_TITLE = "AWS Cloud Club Captain at FAST Peshawar"

BROWN = colors.HexColor("#a36532")
LIGHT_BROWN = colors.HexColor("#c78555")
BG_FILL = colors.HexColor("#fbfaf6")
INK = colors.HexColor("#1f2933")

NAME_COLUMNS = (
    "name",
    "full_name",
    "full name",
    "attendee",
    "attendee_name",
    "attendee name",
    "participant",
    "participant_name",
    "participant name",
)
EVENT_COLUMNS = ("event", "event_title", "event title", "session", "session_title", "session title")


@dataclass(frozen=True)
class Attendee:
    name: str
    event_title: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate AWS Silicon Valley Workflow certificates from a CSV."
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="CSV file with at least a name column.",
    )
    parser.add_argument(
        "--template",
        default=DEFAULT_TEMPLATE,
        type=Path,
        help="Certificate PDF template.",
    )
    parser.add_argument(
        "--logo",
        default=DEFAULT_LOGO,
        type=Path,
        help="Replacement logo image.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Folder for generated certificates.",
    )
    parser.add_argument(
        "--event",
        default=DEFAULT_EVENT_TITLE,
        help="Default event title used when CSV rows do not override it.",
    )
    parser.add_argument(
        "--workshops",
        default=DEFAULT_WORKSHOPS,
        help="Number of workshops completed.",
    )
    parser.add_argument(
        "--signer-name",
        default=DEFAULT_SIGNER_NAME,
        help="Name shown in the bottom-right signature block.",
    )
    parser.add_argument(
        "--signer-title",
        default=DEFAULT_SIGNER_TITLE,
        help="Title shown in the bottom-right signature block.",
    )
    parser.add_argument(
        "--combined-name",
        default="all_certificates.pdf",
        help="File name for the combined multi-page PDF.",
    )
    parser.add_argument(
        "--uppercase-names",
        action="store_true",
        help="Render attendee names in uppercase.",
    )
    return parser.parse_args()


def normalized_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def read_attendees(csv_path: Path) -> list[Attendee]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row with a name column.")

        field_lookup = {normalized_key(field): field for field in reader.fieldnames}
        name_field = next((field_lookup.get(field) for field in NAME_COLUMNS if field in field_lookup), None)
        if not name_field:
            name_field = reader.fieldnames[0]

        event_field = next((field_lookup.get(field) for field in EVENT_COLUMNS if field in field_lookup), None)

        attendees: list[Attendee] = []
        for line_number, row in enumerate(reader, start=2):
            name = (row.get(name_field) or "").strip()
            if not name:
                continue
            event_title = (row.get(event_field) or "").strip() if event_field else None
            attendees.append(Attendee(name=name, event_title=event_title or None))

    if not attendees:
        raise ValueError("No attendee names were found in the CSV.")

    return attendees


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned or "certificate"


def crop_transparent_border(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    return image.crop(bbox) if bbox else image


def find_signature_font() -> Path | None:
    candidates = (
        Path("/usr/share/fonts/opentype/urw-base35/Z003-MediumItalic.otf"),
        Path("/usr/share/fonts/opentype/linux-libertine/LinLibertine_RI.otf"),
        Path("/usr/share/fonts/opentype/urw-base35/NimbusRoman-Italic.otf"),
    )
    return next((path for path in candidates if path.exists()), None)


def make_signature_image(name: str) -> Image.Image:
    font_path = find_signature_font()
    width, height = 1000, 260
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    if font_path:
        font = ImageFont.truetype(str(font_path), 120)
    else:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), name, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(20, (width - text_w) // 2)
    y = max(8, (height - text_h) // 2 - 8)
    draw.text((x, y), name, font=font, fill=(24, 24, 24, 235))

    cropped = crop_transparent_border(image)
    padding = 18
    padded = Image.new(
        "RGBA",
        (cropped.width + padding * 2, cropped.height + padding * 2),
        (255, 255, 255, 0),
    )
    padded.alpha_composite(cropped, (padding, padding))
    return padded


def fit_font_size(
    text: str,
    font_name: str,
    max_width: float,
    start_size: int,
    min_size: int,
) -> int:
    for size in range(start_size, min_size - 1, -1):
        if stringWidth(text, font_name, size) <= max_width:
            return size
    return min_size


def draw_centered_fit(
    pdf: canvas.Canvas,
    text: str,
    x_center: float,
    y: float,
    max_width: float,
    font_name: str,
    start_size: int,
    min_size: int,
    color: colors.Color,
) -> None:
    size = fit_font_size(text, font_name, max_width, start_size, min_size)
    pdf.setFillColor(color)
    pdf.setFont(font_name, size)
    pdf.drawCentredString(x_center, y, text)


def draw_wrapped_centered(
    pdf: canvas.Canvas,
    text: str,
    x_center: float,
    first_y: float,
    max_width: float,
    font_name: str,
    font_size: int,
    color: colors.Color,
    line_gap: float = 12,
) -> None:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and stringWidth(candidate, font_name, font_size) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)

    pdf.setFillColor(color)
    pdf.setFont(font_name, font_size)
    for index, line_text in enumerate(lines[:3]):
        pdf.drawCentredString(x_center, first_y - index * line_gap, line_text)


def draw_logo(pdf: canvas.Canvas, logo_path: Path) -> None:
    with Image.open(logo_path) as source:
        logo = crop_transparent_border(source)

    pdf.setFillColor(BG_FILL)
    pdf.rect(72, 400, 172, 132, stroke=0, fill=1)

    max_w, max_h = 132, 116
    ratio = min(max_w / logo.width, max_h / logo.height)
    draw_w = logo.width * ratio
    draw_h = logo.height * ratio
    x = 98 + (max_w - draw_w) / 2
    y = 409 + (max_h - draw_h) / 2
    pdf.drawImage(ImageReader(logo), x, y, width=draw_w, height=draw_h, mask="auto")


def draw_main_text(
    pdf: canvas.Canvas,
    attendee_name: str,
    event_title: str,
    workshops: str,
    uppercase_names: bool,
) -> None:
    pdf.setFillColor(BG_FILL)
    pdf.rect(145, 192, 552, 152, stroke=0, fill=1)

    rendered_name = attendee_name.upper() if uppercase_names else attendee_name
    draw_centered_fit(
        pdf,
        rendered_name,
        x_center=421,
        y=292,
        max_width=540,
        font_name="Helvetica",
        start_size=38,
        min_size=22,
        color=BROWN,
    )

    pdf.setFillColor(LIGHT_BROWN)
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(
        421,
        248,
        f"for successfully attending all {workshops} workshops of the event titled",
    )

    draw_centered_fit(
        pdf,
        event_title,
        x_center=421,
        y=213,
        max_width=490,
        font_name="Helvetica-Bold",
        start_size=22,
        min_size=16,
        color=LIGHT_BROWN,
    )


def draw_signature_block(pdf: canvas.Canvas, signer_name: str, signer_title: str) -> None:
    pdf.setFillColor(BG_FILL)
    pdf.rect(555, 66, 240, 130, stroke=0, fill=1)

    signature = make_signature_image(signer_name)
    pdf.drawImage(ImageReader(signature), 590, 142, width=170, height=44, mask="auto")

    pdf.setStrokeColor(colors.HexColor("#5f5f5f"))
    pdf.setLineWidth(1.1)
    pdf.line(590, 135, 760, 135)

    pdf.setFillColor(BROWN)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(675, 115, signer_name)

    draw_wrapped_centered(
        pdf,
        signer_title,
        x_center=675,
        first_y=99,
        max_width=210,
        font_name="Helvetica-Bold",
        font_size=9.5,
        color=BROWN,
        line_gap=11,
    )


def make_overlay_pdf(
    width: float,
    height: float,
    logo_path: Path,
    attendee_name: str,
    event_title: str,
    workshops: str,
    signer_name: str,
    signer_title: str,
    uppercase_names: bool,
) -> io.BytesIO:
    packet = io.BytesIO()
    pdf = canvas.Canvas(packet, pagesize=(width, height))
    draw_logo(pdf, logo_path)
    draw_main_text(pdf, attendee_name, event_title, workshops, uppercase_names)
    draw_signature_block(pdf, signer_name, signer_title)
    pdf.save()
    packet.seek(0)
    return packet


def render_certificate(
    template_path: Path,
    logo_path: Path,
    attendee: Attendee,
    default_event_title: str,
    workshops: str,
    signer_name: str,
    signer_title: str,
    uppercase_names: bool,
) -> bytes:
    reader = PdfReader(str(template_path))
    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    event_title = attendee.event_title or default_event_title

    overlay_pdf = make_overlay_pdf(
        width=width,
        height=height,
        logo_path=logo_path,
        attendee_name=attendee.name,
        event_title=event_title,
        workshops=workshops,
        signer_name=signer_name,
        signer_title=signer_title,
        uppercase_names=uppercase_names,
    )
    overlay_reader = PdfReader(overlay_pdf)
    page.merge_page(overlay_reader.pages[0])

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(output)
    return output.getvalue()


def write_certificates(
    attendees: Iterable[Attendee],
    template_path: Path,
    logo_path: Path,
    output_dir: Path,
    default_event_title: str,
    workshops: str,
    signer_name: str,
    signer_title: str,
    combined_name: str,
    uppercase_names: bool,
) -> tuple[list[Path], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    individual_dir = output_dir / "individual"
    individual_dir.mkdir(parents=True, exist_ok=True)

    combined_writer = PdfWriter()
    written_files: list[Path] = []

    for index, attendee in enumerate(attendees, start=1):
        pdf_bytes = render_certificate(
            template_path=template_path,
            logo_path=logo_path,
            attendee=attendee,
            default_event_title=default_event_title,
            workshops=workshops,
            signer_name=signer_name,
            signer_title=signer_title,
            uppercase_names=uppercase_names,
        )

        file_name = f"{index:03d}-{safe_filename(attendee.name)}.pdf"
        output_path = individual_dir / file_name
        output_path.write_bytes(pdf_bytes)
        written_files.append(output_path)

        combined_reader = PdfReader(io.BytesIO(pdf_bytes))
        combined_writer.add_page(combined_reader.pages[0])

    combined_path = output_dir / combined_name
    with combined_path.open("wb") as handle:
        combined_writer.write(handle)

    return written_files, combined_path


def main() -> None:
    args = parse_args()

    attendees = read_attendees(args.csv)
    written_files, combined_path = write_certificates(
        attendees=attendees,
        template_path=args.template,
        logo_path=args.logo,
        output_dir=args.output,
        default_event_title=args.event,
        workshops=args.workshops,
        signer_name=args.signer_name,
        signer_title=args.signer_title,
        combined_name=args.combined_name,
        uppercase_names=args.uppercase_names,
    )

    print(f"Generated {len(written_files)} individual certificate(s).")
    print(f"Individual PDFs: {written_files[0].parent}")
    print(f"Combined PDF: {combined_path}")


if __name__ == "__main__":
    main()
