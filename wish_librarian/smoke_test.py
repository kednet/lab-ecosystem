"""
Быстрый sanity-check: проверить, что все модули импортируются.
Запуск: python smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

print("🔍 Smoke test WishLibrarian...")

# 1) config
from agent.config import get_settings
s = get_settings()
s.ensure_directories()
print(f"  ✅ config: OUTPUT_DIR={s.output_dir}")

# 2) logger
from agent.utils.logger import setup_logging, get_logger
setup_logging()
log = get_logger()
log.info("  ✅ logger работает")

# 3) models
from agent.models import BookInfo, ReviewBundle
b = BookInfo(title="Test", author="A", source_url="https://x/")
print(f"  ✅ models: folder_name={b.folder_name()}")

# 4) parsers
from agent.parsers.koob_parser import KoobParser
from agent.parsers.reviews_parser import ReviewsParser
from agent.parsers.scientific_parser import ScientificParser
from agent.parsers.affiliate_links import AffiliateLinksGenerator
print("  ✅ parsers импортируются")

# 5) storage
from agent.storage.file_manager import FileManager
from agent.storage.templates import render_metadata_json
print(f"  ✅ templates: {len(render_metadata_json(b))} симв.")

# 6) ai
from agent.ai.prompts import build_summary_prompt
print(f"  ✅ prompts: {len(build_summary_prompt(b))} симв.")

# 7) librarian
from agent.librarian import WishLibrarian
print("  ✅ librarian импортируется")

print("\n🎉 Все модули загружены успешно!")
print("Для реальной работы укажите ANTHROPIC_API_KEY в .env и запустите:")
print('  python -m agent.cli --url "https://oko.koob.ru/transerfing_realnosti/"')
