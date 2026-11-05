from pathlib import Path
import sys


FROZEN = bool(getattr(sys, 'frozen', False))
PROJECT_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]
ASSETS_DIR = (Path(__file__).resolve().parent if FROZEN else PROJECT_ROOT) / 'assets'
HANDWRITING_FONTS_DIR = PROJECT_ROOT / 'fonts' / 'handwriting' if FROZEN else ASSETS_DIR / 'fonts' / 'handwriting'
