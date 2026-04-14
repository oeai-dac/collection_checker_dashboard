# 📂 ÖAI Collection Checker

Ein interaktives Streamlit-Dashboard zum Analysieren, Bereinigen und Verwalten von Ordnern und Dateien.

---

## Funktionen

- **Ordneranalyse**: Gesamtanzahl Dateien, Ordner und Größe
- **Ordnerbaum**: Kompakter Baum der Ordnerstruktur
- **Dateiendungen**: Übersicht über Dateiendungen
- **Sonderzeichen**: Dateien und Ordner umbenennen, um Sonderzeichen zu entfernen
- **Excel → CSV**: Automatische Umwandlung von XLS/XLSX-Dateien
- **Erweitert**:
  - Leere Dateien und Ordner anzeigen und löschen
  - Metadaten pro Ordner erstellen (inkl. EXIF-Daten für Bilder)
  - Duplikate prüfen

---

## Voraussetzungen

- Python 3.10+
- Bibliotheken:
  - `streamlit`
  - `pandas`
  - `plotly`
  - `pillow`
  - `openpyxl`
  - `xlrd`


```bash
pip install -r requirements.txt

streamlit run oeai_checker_dashboard.py
