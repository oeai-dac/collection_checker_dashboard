# oai_checker_dashboard.py
import os
import hashlib
import pandas as pd
import streamlit as st
import plotly.express as px
import re
import shutil
import json
from datetime import datetime
from PIL import Image, ExifTags

st.set_page_config(page_title="ÖAI Collection Checker", layout="wide")
st.title("📂 ÖAI Collection Checker")

# ---- Einstellungen ----
path = st.text_input("Pfad zum Ordner:", "")
umlaut_map = {'ä':'ae','Ä':'Ae','ö':'oe','Ö':'Oe','ü':'ue','Ü':'Ue','ß':'ss'}

def clean_name(name):
    for k,v in umlaut_map.items():
        name = name.replace(k,v)
    cleaned = re.sub(r'[^A-Za-z0-9_-]', '_', name)
    return cleaned

def hashfile(filename):
    hasher = hashlib.sha1()
    try:
        with open(filename,'rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def find_duplicates(files_list):
    size_dict = {}
    dup_list = []
    for file in files_list:
        try:
            size = os.path.getsize(file)
            size_dict.setdefault(size, []).append(file)
        except:
            continue
    for same_size_files in size_dict.values():
        if len(same_size_files) < 2:
            continue
        hashes = {}
        for f in same_size_files:
            h = hashfile(f)
            if not h: continue
            if h in hashes:
                dup_list.append((f, hashes[h]))
            else:
                hashes[h] = f
    return dup_list

def safe_rename(old, new):
    base, ext = os.path.splitext(new)
    counter = 1
    while os.path.exists(new):
        new = f"{base}_{counter}{ext}"
        counter += 1
    os.rename(old, new)
    return new

def convert_excel_to_csv(excel_file, output_folder=None):
    if output_folder is None:
        output_folder = os.path.dirname(excel_file)
    try:
        ext = os.path.splitext(excel_file)[1].lower()
        engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
        df = pd.read_excel(excel_file, engine=engine)
        csv_path = os.path.join(output_folder, os.path.splitext(os.path.basename(excel_file))[0] + ".csv")
        df.to_csv(csv_path, index=False)
        return csv_path
    except Exception as e:
        return str(e)

# ---- Kompakter Foldertree (nur Ordner, Zeilenumbruch korrekt) ----
def render_folder_tree_only_dirs(folder_path):
    def build_tree_lines(path, prefix="", level=0):
        try:
            items = sorted(os.listdir(path))
        except PermissionError:
            return [prefix + "[Zugriff verweigert]"]
        dirs = [item for item in items if os.path.isdir(os.path.join(path, item))]
        lines = []
        for i, item in enumerate(dirs):
            connector = "├── "
            next_prefix = prefix + "│   "
            if i == len(dirs) - 1:
                connector = "└── "
                next_prefix = prefix + "    "
            display_name = f"<span style='color:blue;font-weight:bold'>{item}</span>" if level==0 else item
            lines.append(prefix + connector + display_name)
            lines.extend(build_tree_lines(os.path.join(path, item), next_prefix, level+1))
        return lines
    lines = build_tree_lines(folder_path)
    for line in lines:
        st.markdown(f"<div style='margin:0; line-height:1.1'>{line}</div>", unsafe_allow_html=True)

# ---- Leere Dateien und Ordner finden ----
def find_empty_files_and_dirs(folder_path):
    empty_files = []
    empty_dirs = []
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            file_path = os.path.join(root, f)
            if os.path.getsize(file_path) == 0:
                empty_files.append(file_path)
        for d in dirs:
            dir_path = os.path.join(root, d)
            if len(os.listdir(dir_path)) == 0:
                empty_dirs.append(dir_path)
    return empty_files, empty_dirs

# ---- Datei/Ordner löschen ----
def delete_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False

def delete_dir(dir_path):
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            return True
        except Exception as e:
            st.warning(f"Ordner {dir_path} konnte nicht gelöscht werden: {e}")
    return False

# ---- Metadaten pro Ordner erzeugen ----
def extract_image_exif(file_path):
    exif_data = {}
    try:
        img = Image.open(file_path)
        info = img._getexif()
        if info:
            for tag, value in info.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                exif_data[decoded] = str(value)
    except Exception:
        pass
    return exif_data

def create_metadata_json(folder_path):
    files_in_folder = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path,f))]
    if not files_in_folder:
        return None
    metadata = {}
    for f in files_in_folder:
        file_path = os.path.join(folder_path, f)
        stat = os.stat(file_path)
        file_info = {
            "name": f,
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
        if f.lower().endswith(('.jpg','.jpeg','.png','.tiff','.tif')):
            file_info["exif"] = extract_image_exif(file_path)
        metadata[f] = file_info
    metadata_path = os.path.join(folder_path, "metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as jf:
        json.dump(metadata, jf, indent=4, ensure_ascii=False)
    return metadata_path
    
def is_pdfa(file_path):
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)

        # PDF/A Hinweis über Metadata
        meta = reader.metadata

        if meta:
            meta_str = str(meta).lower()
            if "pdfaid" in meta_str or "pdf/a" in meta_str:
                return True

        return False
    except:
        return False
        
# ---- Ordner analysieren ----
if path and os.path.exists(path):
    files = []
    directories = []
    size = 0
    files_dic = {}
    files_special = []
    directories_special = []

    for r, d, f in os.walk(path):
        directories.extend([os.path.join(r, dic) for dic in d])
        for dic in d:
            if dic.startswith("."): continue
            cleaned_dir = clean_name(dic)
            if cleaned_dir != dic:
                directories_special.append((os.path.join(r, dic), os.path.join(r, cleaned_dir)))
        for file in f:
            filename, ext = os.path.splitext(file)
            if filename.startswith("."): continue
            file_path = os.path.join(r, file)
            files.append(file_path)
            size += os.path.getsize(file_path)
            cleaned_name_file = clean_name(filename) + ext
            if cleaned_name_file != file:
                files_special.append((file_path, os.path.join(r, cleaned_name_file)))
            files_dic[ext] = files_dic.get(ext, 0) + 1

    # ---- DataFrames ----
    df_extensions = pd.DataFrame(list(files_dic.items()), columns=['extension','count']).sort_values(by='count', ascending=False)
    df_special_files = pd.DataFrame(files_special, columns=['original','cleaned'])
    df_special_dirs = pd.DataFrame(directories_special, columns=['original','cleaned'])

    # ---- Tabs ----
    tabs = st.tabs([
        "📊 Übersicht",
        "📁 Ordnerstruktur",
        "📝 Dateiendungen",
        "⚠️ Sonderzeichen",
        "🔄 Umwandlungen",
        "⚙️ Erweitert"
    ])

    # ---- Tab 1: Übersicht ----
    with tabs[0]:
        st.subheader("Allgemeine Informationen")
        st.metric("Anzahl Dateien", len(files))
        st.metric("Anzahl Ordner", len(directories))
        size_mb = size / 1e6
        size_gb = size / 1e9
        st.metric("Gesamtgröße", f"{size_gb:.2f} GB" if size_gb>=1 else f"{size_mb:.2f} MB")

    # ---- Tab 2: Ordnerstruktur ----
    with tabs[1]:
        st.subheader("Ordnerbaum (nur Ordner, erste Ebene blau, kompakt)")
        render_folder_tree_only_dirs(path)

    # ---- Tab 3: Dateiendungen ----
    with tabs[2]:
        st.subheader("Top 20 Dateiendungen")
        st.plotly_chart(px.bar(df_extensions.head(20), x='extension', y='count', text='count', title='Top 20 Dateiendungen'), width='stretch')
        st.subheader("Alle Dateiendungen im Ordner")
        st.dataframe(df_extensions.rename(columns={'extension':'Endung','count':'Anzahl'}), hide_index=True, height=len(df_extensions)*25, width=600)

    # ---- Tab 4: Sonderzeichen ----
    with tabs[3]:
            st.subheader("Dateien mit Sonderzeichen")
            st.metric("Anzahl Dateien mit Sonderzeichen", len(files_special))  # 👈 NEU

            st.write("Original → Bereinigt")
            if files_special:
                if st.button("Alle Dateien umbenennen"):
                    for old,new in files_special:
                        safe_rename(old,new)
                    st.success("Alle Dateien wurden umbenannt!")

                for _, row in df_special_files.iterrows():
                    col1,col2,col3 = st.columns([4,4,2])
                    with col1: st.text(row['original'])
                    with col2: st.text(row['cleaned'])
                    with col3:
                        if st.button("Umbenennen", key=row['original']):
                            safe_rename(row['original'], row['cleaned'])

            else:
                st.info("Keine Dateien mit Sonderzeichen gefunden.")

            st.subheader("Ordner mit Sonderzeichen (Vorschau)")
            st.metric("Anzahl Ordner mit Sonderzeichen", len(directories_special))  # 👈 NEU

            if directories_special:
                for _, row in df_special_dirs.iterrows():
                    col1,col2,col3 = st.columns([4,4,2])
                    with col1: st.text(row['original'])
                    with col2: st.text(row['cleaned'])
                    with col3:
                        if st.button("Umbenennen", key=row['original']+"_dir"):
                            safe_rename(row['original'], row['cleaned'])
            else:
                st.info("Keine Ordner mit Sonderzeichen gefunden.")
     # ---- Tab 5: Umwandlungen ----
    with tabs[4]:

        st.subheader("📊 Dokumentübersicht")

        word_files = [f for f in files if f.lower().endswith(('.doc', '.docx'))]
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        excel_files = [f for f in files if f.lower().endswith(('.xls', '.xlsx'))]

        # ================= WORD =================
        st.subheader("📝 Word-Dateien (DOC / DOCX)")
        st.metric("Anzahl Word-Dateien", len(word_files))

        if word_files:
            for f in word_files:
                st.text(f)
        else:
            st.info("Keine Word-Dateien gefunden.")

        st.divider()

        # ================= EXCEL =================
        st.subheader("📊 Excel-Dateien (XLS / XLSX)")
        st.metric("Anzahl Excel-Dateien", len(excel_files))

        if excel_files:
            for f in excel_files:
                st.text(f)
        else:
            st.info("Keine Excel-Dateien gefunden.")

        st.divider()

        # ================= PDF =================
        st.subheader("📄 PDF-Dateien")
        st.metric("Anzahl PDF-Dateien", len(pdf_files))

        pdfa_count = 0

        if pdf_files:
            for f in pdf_files:
                is_pdfa_flag = is_pdfa(f)
                if is_pdfa_flag:
                    pdfa_count += 1

                col1, col2 = st.columns([6, 2])
                with col1:
                    st.text(f)
                with col2:
                    if is_pdfa_flag:
                        st.success("PDF/A")
                    else:
                        st.warning("kein PDF/A")

            st.metric("PDF/A Dateien", pdfa_count)
        else:
            st.info("Keine PDF-Dateien gefunden.")
    # ---- Tab 6: Erweitert ----
    with tabs[5]:
        st.subheader("Leere Dateien und Ordner")
        if st.button("Leere Dateien und Ordner anzeigen"):
            empty_files, empty_dirs = find_empty_files_and_dirs(path)
            if empty_files:
                st.write("**Leere Dateien:**")
                for f in empty_files:
                    col1,col2 = st.columns([6,1])
                    with col1: st.text(f)
                    with col2:
                        if st.button("Löschen", key=f):
                            if delete_file(f):
                                st.success(f"{f} wurde gelöscht")
            else:
                st.success("Keine leeren Dateien gefunden.")
            if empty_dirs:
                st.write("**Leere Ordner:**")
                for d in empty_dirs:
                    col1,col2 = st.columns([6,1])
                    with col1: st.text(d)
                    with col2:
                        if st.button("Löschen", key=d):
                            if delete_dir(d):
                                st.success(f"{d} wurde gelöscht")
            else:
                st.success("Keine leeren Ordner gefunden.")

        st.subheader("Metadaten erzeugen")
        if st.button("Metadaten pro Ordner erstellen"):
            for dirpath, dirnames, filenames in os.walk(path):
                metadata_file = create_metadata_json(dirpath)
                if metadata_file:
                    st.success(f"Metadaten erstellt: {metadata_file}")

        st.subheader("Duplikate prüfen")
        if st.button("Duplikate prüfen"):
            with st.spinner("Prüfe auf Duplikate..."):
                dup_list = find_duplicates(files)
            if dup_list:
                df_dup = pd.DataFrame(dup_list, columns=['Duplikat 1','Duplikat 2'])
                st.dataframe(df_dup, width='stretch')
            else:
                st.success("Keine Duplikate gefunden.")

else:
    st.warning("Bitte einen gültigen Pfad eingeben.")