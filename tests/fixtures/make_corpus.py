"""Generate the deterministic test corpus (run: python3 tests/fixtures/make_corpus.py; needs Pillow + ffmpeg).

corpus/      — mixed-format folder used by integration tests and the labelled retrieval evaluation.
eval.json    — labelled queries -> expected source path (predeclared metric in docs/decisions.md D40).
"""
import json
import os
import subprocess
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "corpus")

DOCS = {
    "manuals/pressure-sensor.md": "# Pressure sensor replacement\n\nIsolate the hydraulic line and release residual pressure. Remove the four M6 mounting bolts and disconnect harness connector P7. Fit the new PS-400 sensor, torque the bolts to 9 Nm, reconnect P7 and run calibration routine CAL-22.",
    "manuals/coolant-flush.md": "# Coolant system flush\n\nDrain the coolant through the lower radiator valve into an approved container. Fill with distilled water, run the pump for ten minutes, drain again, then refill with a 50/50 glycol mixture. Bleed air from the upper hose until no bubbles appear.",
    "manuals/conveyor-belt.txt": "Conveyor belt tensioning. Loosen the take-up frame bolts, turn the adjustment screws evenly on both sides until the belt deflects 15 mm under a 5 kg load at mid-span, then retighten the frame bolts and check tracking for five minutes.",
    "manuals/battery-storage.txt": "Lithium battery storage. Store packs at 40 to 60 percent charge in a cool dry room between 10 and 25 degrees Celsius. Never stack damaged packs; isolate swollen cells in the fireproof cabinet and report them to the safety officer.",
    "policies/travel-expenses.md": "# Travel expense policy\n\nEmployees book economy class for flights under six hours. Hotel costs are reimbursed up to the city cap. Submit receipts within 30 days through the finance portal; meals are covered by a daily per diem.",
    "policies/remote-work.md": "# Remote work policy\n\nStaff may work remotely up to three days per week with manager approval. Core collaboration hours are 10:00 to 15:00 local time. Company laptops must use the VPN on public networks.",
    "policies/parental-leave.txt": "Parental leave. Birth and adoptive parents receive sixteen weeks of fully paid leave, which can be taken in up to three blocks during the first year. Notify human resources at least eight weeks in advance.",
    "it/password-reset.md": "# Resetting your password\n\nOpen the self-service portal, choose Forgot password, and confirm the code sent to your registered phone. New passwords need at least 14 characters and cannot reuse your last five passwords.",
    "it/printer-jam.txt": "Clearing a paper jam on the floor printer. Open the front door, pull the green lever, and slide the toner drawer out. Remove the jammed sheet slowly in the direction of paper travel, then close all doors to resume printing.",
    "kitchen/cafeteria-hours.txt": "The cafeteria opens at 07:30 for breakfast and serves lunch from 11:30 until 14:00. Vegetarian and vegan dishes are available every day; the salad bar closes at 13:45.",
    "safety/fire-evacuation.md": "# Fire evacuation\n\nWhen the alarm sounds, leave by the nearest marked exit without using lifts. Assemble at point B in the north car park and report to your floor warden, who checks names against the visitor list.",
    "safety/forklift-licence.txt": "Forklift operation requires a valid internal licence renewed every three years. Operators complete a daily pre-use inspection of forks, chains, brakes and horn and record it in the logbook kept at the charging bay.",
}

EVAL = [
    ("How do I replace the pressure sensor?", "manuals/pressure-sensor.md"),
    ("torque for PS-400 mounting bolts", "manuals/pressure-sensor.md"),
    ("steps to flush the cooling system", "manuals/coolant-flush.md"),
    ("how much should the belt deflect when adjusting tension", "manuals/conveyor-belt.txt"),
    ("what charge level for storing lithium packs", "manuals/battery-storage.txt"),
    ("can I fly business class on a short trip", "policies/travel-expenses.md"),
    ("how many days a week can I work from home", "policies/remote-work.md"),
    ("how long is paid leave for new parents", "policies/parental-leave.txt"),
    ("I forgot my password", "it/password-reset.md"),
    ("paper stuck in the printer", "it/printer-jam.txt"),
    ("when is lunch served", "kitchen/cafeteria-hours.txt"),
    ("where do we gather when the fire alarm goes off", "safety/fire-evacuation.md"),
    ("how often must forklift licences be renewed", "safety/forklift-licence.txt"),
    ("which oil grade do I use for the air compressor", "manuals/compressor-maintenance.docx"),
    ("HK-77", "manuals/hydraulic-pump.pdf"),
    ("CAL-22", "manuals/pressure-sensor.md"),
    ("ISO VG 46", "manuals/compressor-maintenance.docx"),
    ("assembly point B north car park", "safety/fire-evacuation.md"),
    ("where is the emergency shower located", "media/scanned-notice.pdf"),
    ("unplug the charger before cleaning the battery terminals", "media/charger-briefing.mp4"),
    ("a red square image", "media/red-square.png"),
    ("spoken instructions about removing mounting bolts", "media/sensor-instructions.mp3"),
]


def text_pdf(lines: list[str]) -> bytes:
    """Minimal valid single-page PDF with real text (Helvetica)."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join(f"({esc(l)}) '" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return out


def write(rel: str, data: bytes):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def main():
    from PIL import Image, ImageDraw
    for rel, text in DOCS.items():
        write(rel, text.encode())
    write("manuals/hydraulic-pump.pdf", text_pdf(["Hydraulic pump service interval", "Replace the pump seals every 2000 operating hours.",
                                                  "Use seal kit HK-77 and check the relief valve at 180 bar."]))
    import docx
    d = docx.Document()
    d.core_properties.created = __import__("datetime").datetime(2026, 1, 1)  # deterministic bytes
    d.add_heading("Air compressor maintenance", 0)
    d.add_heading("Daily checks", level=1)
    d.add_paragraph("Drain condensate from the receiver tank and check the pressure gauge reads between 7 and 9 bar.")
    d.add_heading("Oil change", level=1)
    d.add_paragraph("Change the compressor oil every 4,000 operating hours. Use ISO VG 46 synthetic oil and replace the oil filter at the same time.")
    t = d.add_table(rows=3, cols=2)
    for r, (a, b) in enumerate([("Task", "Interval"), ("Air filter", "1,000 h"), ("Separator element", "8,000 h")]):
        t.cell(r, 0).text, t.cell(r, 1).text = a, b
    d.save(os.path.join(OUT, "manuals/compressor-maintenance.docx"))
    img = Image.new("RGB", (256, 256), (220, 0, 0))
    os.makedirs(os.path.join(OUT, "media"), exist_ok=True)
    img.save(os.path.join(OUT, "media/red-square.png"))
    scan = Image.new("RGB", (850, 1100), "white")
    d = ImageDraw.Draw(scan)
    d.rectangle([100, 100, 750, 400], outline="black", width=8)
    d.ellipse([300, 500, 550, 750], fill=(0, 90, 200))
    scan.save(os.path.join(OUT, "media/scanned-diagram.pdf"))  # image-only PDF
    from PIL import ImageFont
    notice = Image.new("RGB", (1240, 1754), "white")  # A4 at 150 dpi, scanned: text exists only as pixels
    dn = ImageDraw.Draw(notice)
    big, body = ImageFont.load_default(size=72), ImageFont.load_default(size=40)
    dn.text((100, 160), "SAFETY NOTICE", fill="black", font=big)
    for i, line in enumerate(["The emergency shower is located in bay 4,", "next to the acid store.", "Test the shower every Monday and log the result."]):
        dn.text((100, 360 + i * 70), line, fill="black", font=body)
    notice.save(os.path.join(OUT, "media/scanned-notice.pdf"))
    Image.new("RGB", (320, 200), (30, 140, 60)).save(os.path.join(OUT, "media/green-panel.jpg"), quality=90)
    speech = os.path.join(HERE, "speech.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", speech, "-codec:a", "libmp3lame", "-b:a", "64k", os.path.join(OUT, "media/sensor-instructions.mp3")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(HERE, "clip.mp4"), "-c", "copy", os.path.join(OUT, "media/test-pattern.mp4")], check=True)
    # video whose meaning is only in its soundtrack (speech): found through the transcript
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=8:size=640x360:rate=10", "-i", os.path.join(HERE, "briefing.wav"),
                    "-shortest", "-pix_fmt", "yuv420p", "-c:a", "aac", os.path.join(OUT, "media/charger-briefing.mp4")], check=True)
    with open(os.path.join(HERE, "eval.json"), "w") as f:
        json.dump({"metric": "hit@5 (expected source path among top-5 results)", "threshold": 0.9,
                   "queries": [{"query": q, "expected_path": p} for q, p in EVAL]}, f, indent=1)
    print("corpus written to", OUT)


if __name__ == "__main__":
    main()
