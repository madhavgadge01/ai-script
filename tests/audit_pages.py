import os
import glob
import sqlite3
from bs4 import BeautifulSoup

export_dir = "storage/exports/BCA_BCS-011_U1"
page_files = sorted(glob.glob(f"{export_dir}/page_*.html"))

print(f"Total HTML page files found: {len(page_files)}")

placeholder_words = ["placeholder", "lorem", "todo", "tbd", "sample content", "page content..."]

for idx, pf in enumerate(page_files, 1):
    with open(pf, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "NO_H1"
    badge_el = soup.find("span", class_="chapter-badge")
    badge = badge_el.get_text(strip=True) if badge_el else "NO_BADGE"
    sections = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]
    callouts = [c.get_text(strip=True) for c in soup.find_all("div", class_="callout")]
    tables = soup.find_all("table")
    
    # Check for formulas / equations
    formula_signals = ["CPI", "CPU Time", "AMAT", "Hit Time", "Miss Rate", "Instruction Count", "Clock Cycle Time"]
    found_formulas = [sig for sig in formula_signals if sig in html]
    
    # Check for placeholders
    detected_ph = [w for w in placeholder_words if w in html.lower()]
    
    print(f"\n--- Page {idx}: {os.path.basename(pf)} ({len(html)} bytes) ---")
    print(f"  Title: {title}")
    print(f"  Badge: {badge}")
    print(f"  H2 Sections: {sections}")
    print(f"  Callouts ({len(callouts)}): {[c[:60] + '...' for c in callouts]}")
    print(f"  Tables: {len(tables)}")
    print(f"  Formulas found: {found_formulas}")
    print(f"  Non-empty HTML: {bool(html.strip())} ({len(html)} chars)")
    print(f"  Placeholders: {detected_ph if detected_ph else 'NONE (Clean)'}")

print("\n--- Cross-check with SQLite database ---")
conn = sqlite3.connect("storage/uninotes.db")
cursor = conn.cursor()
cursor.execute("SELECT id, unit_id, page_number, page_title, length(content_html) FROM generated_pages ORDER BY page_number")
rows = cursor.fetchall()
print(f"SQLite rows in generated_pages: {len(rows)}")
for r in rows:
    print(f"  Page {r[2]}: ID={r[0]}, Unit={r[1]}, Title='{r[3]}', Length={r[4]} chars")
conn.close()
