from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DB_PATH = DATA / "actas.sqlite"
PDF_DIR = DATA / "pdfs"
PUBLIC_REPO = ROOT.parent / f"{ROOT.name}-publico"

KIND_DIR = {"jgl_minutes": "jgl", "plenary_minutes": "pleno"}
KIND_TAG = {"jgl_minutes": "JGL", "plenary_minutes": "PLENO"}
