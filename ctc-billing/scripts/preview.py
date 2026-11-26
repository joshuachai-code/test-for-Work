"""Inspect attached CTC demo scans locally. No workbook or dashboard access."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parent
CATALOG = SCRIPTS.parent / "references" / "demo-scans.json"


def read_json(path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def normalise(name):
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def mock_profile(name, company_id):
    """Use only a single matching mock-company directory in the configured root."""
    config = read_json(SCRIPTS / "books.json")
    parent = Path(config["root"]) / config["company_folder"] / "Mock Companies"
    try:
        matches = [p for p in parent.iterdir() if p.is_dir() and normalise(p.name) == normalise(name)]
        if len(matches) == 1:
            record = read_json(matches[0] / "company-info.json")
            if (record.get("is_mock") is True and record.get("company_id") == company_id
                    and normalise(record.get("legal_name", "")) == normalise(name)):
                return {"status": "matched", "ctc_billing": record.get("ctc_billing", {})}
    except (OSError, ValueError):
        pass
    return {"status": "profile unavailable or not matched"}


def ensure_renderer():
    if all(importlib.util.find_spec(mod) for mod in ("pypdfium2", "PIL")):
        return True
    if os.environ.get("CTC_PREVIEW_RENDERER_RETRY"):
        return False
    # A G-Work shell on the original Mac may start the system Python.
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
    for candidate in (os.environ.get("CODEX_PRIMARY_RUNTIME_PYTHON"), str(bundled)):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            env = {**os.environ, "CTC_PREVIEW_RENDERER_RETRY": "1"}
            os.execve(candidate, [candidate, *sys.argv], env)
    return False


def render_pdf(path, seen_images):
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    # Four labelled pages per image; a single file stays visible without a browser.
    directory = Path(tempfile.mkdtemp(prefix="ctc-preview-"))
    document = pdfium.PdfDocument(str(path))
    sheets = []
    repeats = []
    try:
        for first in range(0, len(document), 4):
            count = min(4, len(document) - first)
            cols = min(2, count)
            sheet = Image.new("RGB", (cols * 920, ((count + 1) // 2) * 1250), "#e5e8e8")
            draw = ImageDraw.Draw(sheet)
            for offset in range(count):
                i = first + offset
                page = document[i]
                try:
                    width, height = page.get_size()
                    image = page.render(scale=min(910 / width, 1210 / height)).to_pil().convert("RGB")
                finally:
                    page.close()
                key = (image.size, hashlib.sha256(image.tobytes()).hexdigest())
                where = {"file": str(path), "page": i + 1}
                if key in seen_images:
                    repeats.append({"page": i + 1, "same_render_as": seen_images[key]})
                else:
                    seen_images[key] = where
                x, y = (offset % 2) * 920, (offset // 2) * 1250
                draw.text((x + 10, y + 6), f"Page {i + 1}", fill="black")
                sheet.paste(image, (x + (920 - image.width) // 2, y + 26))
            target = directory / f"pages-{first + 1}-{first + count}.png"
            sheet.save(target)
            sheets.append(str(target))
        if not sheets:
            raise ValueError("PDF contains no pages")
        return {"method": "inspect rendered images", "pages": len(document),
                "image_paths": sheets, "matching_renders": repeats}
    finally:
        document.close()


def preview(paths, fresh):
    catalog = read_json(CATALOG)
    files = []
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Attachment is unavailable: {path}")
        known = None if fresh else catalog["files"].get(digest(path))
        files.append((path, known))
    needs_renderer = any(not known and p.suffix.lower() == ".pdf" for p, known in files)
    has_renderer = ensure_renderer() if needs_renderer else False
    output = {"pricing_defaults": read_json(SCRIPTS / "pricing.json"), "companies": {}, "files": []}
    seen_images = {}
    for path, known in files:
        if known:
            company_id = known["case"]
            case = catalog["cases"][company_id]
            if company_id not in output["companies"]:
                output["companies"][company_id] = {
                    "scan_company": case["company"], **mock_profile(case["company"], company_id)}
            result = {"method": "matched demo evidence (exact file SHA-256)", "company_id": company_id,
                      "pages": [{"page": n, "reviewed_image": f"{company_id}/{key}",
                                 "evidence": case["pages"][key]} for n, key in enumerate(known["pages"], 1)]}
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
            result = {"method": "inspect original image", "image_paths": [str(path)]}
        elif path.suffix.lower() == ".pdf" and has_renderer:
            try:
                result = render_pdf(path, seen_images)
            except Exception as exc:
                result = {"pending": f"Cannot render this PDF: {exc}. Supply its affected pages as images."}
        else:
            result = {"pending": "Use readable attachment pages or supply page images."}
        output["files"].append({"file": path.name, **result})
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="Inspect the current pages without cached demo evidence")
    parser.add_argument("scans", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        print(json.dumps(preview(args.scans, args.fresh), indent=2, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"CTC preview: {exc}\n")
