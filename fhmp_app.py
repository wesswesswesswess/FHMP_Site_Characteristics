# FHMP Flora – Site Characteristics: Streamlit field app
# Author: M365 Copilot for Wess Von Hooton

import os
import re
import json
from datetime import datetime, date

import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from textwrap import wrap

APP_TITLE = "FHMP Flora – Site Characteristics"
DATA_DIR = "data"
SUMMARY_DIR = "summaries"
JSONL_PATH = os.path.join(DATA_DIR, "site_characteristics.jsonl")  # authoritative log
CSV_EXPORT_NAME = "site_characteristics.csv"  # used for downloads only

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

# ---------- Reference data ----------
VEGETATION = ["Forest", "Woodland", "Shrubland", "Other"]

# Added "Tingle"
DOMINANT_SPECIES = ["Jarrah", "Marri", "Karri", "Wandoo", "Tingle", "Other"]

# Simplified landforms
LANDFORM = ["Upper slope", "Midslope", "Lower slope", "Flat"]

FIRE_PRESENCE = ["No evidence/>10 yrs", "3-10 yrs", "1-3 yrs", "<1 yr"]
FIRE_INTENSITY = [
    "No evidence",
    "Patchy (unburned patches up to 2m scorch)",
    "Low (no unburned patches up to 2m scorch)",
    "2-5 m scorch",
    "High (complete canopy scorch)",
    "Extreme",
]
DIEBACK = ["No evidence", "Some loss of indicator species", "Extensive loss of indicator species"]
DROUGHT_STRESS = [
    "No stress evident",
    "Evident on some individuals",
    "Evident on some taxa",
    "Extensive across taxa and site",
]
ANIMAL_TYPES = ["Rabbits", "Kangaroo (grazing)", "Pigs", "Horse/Donkey/Cattle", "Other feral"]

# ---------- Canonical CSV export schema (order) ----------
COLUMNS = [
    "submission_id",
    "date",
    "site",
    "vegetation",
    "dominant_species",
    "landform",
    "fire_presence",
    "fire_intensity",
    "dieback",
    "drought_stress",
    "stressed_taxa",
    "weeds_species",
    "weeds_percent",
    "animals_rabbits",
    "animals_kangaroo",
    "animals_pigs",
    "animals_hdc",
    "animals_other",
    "animals_other_text",
    "other_comments",
    "summary_image",
]

# ---------- Session helpers ----------
def init_session():
    if "mode" not in st.session_state:
        st.session_state.mode = "splash"
    if "step" not in st.session_state:
        st.session_state.step = 0
    if "form" not in st.session_state:
        st.session_state.form = default_form()
    
# --- new: delete confirmations ---
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False          # single record delete pending?
    if "confirm_rec" not in st.session_state:
        st.session_state.confirm_rec = None              # holds the selected record dict (with _idx)
    if "confirm_delete_all" not in st.session_state:
        st.session_state.confirm_delete_all = False      # bulk delete pending?
  


def default_form():
    return {
        "date": date.today().isoformat(),
        "site": "",
        "vegetation": {v: False for v in VEGETATION},
        "vegetation_other": "",
        "dominant_species": {s: False for s in DOMINANT_SPECIES},
        "dominant_other": "",
        "landform": {l: False for l in LANDFORM},
        # removed: water_features, soils & surface (coarse_surface, rock_outcrop, soil_colour, soil_type)
        "fire_presence": FIRE_PRESENCE[0],
        "fire_intensity": FIRE_INTENSITY[0],
        "dieback": DIEBACK[0],
        "drought_stress": DROUGHT_STRESS[0],
        "stressed_taxa": "",
        "weeds_species": "",
        # removed: weeds_extent_density
        "weeds_percent": 0,
        "animals": {a: 0 for a in ANIMAL_TYPES},
        "animals_other_text": "",
        "other_comments": "",
    }

def reset_to_splash():
    st.session_state.mode = "splash"
    st.session_state.step = 0
    st.session_state.form = default_form()

# ---------- JSONL storage + export ----------
def write_jsonl_record(record: dict, path=JSONL_PATH):
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def read_jsonl_records(path=JSONL_PATH):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                # Ignore a bad line; we could log or show a warning if desired
                pass
    return records

def df_from_jsonl(columns=COLUMNS):
    recs = read_jsonl_records()
    if not recs:
        return pd.DataFrame(columns=columns)
    # Normalize to canonical order; extra keys are dropped silently
    df = pd.DataFrame(recs)
    return df.reindex(columns=columns)


    
# ---------- Single-record delete helpers ----------

def load_jsonl_with_index(path=JSONL_PATH):
    """
    Read JSONL and return a list of dicts where each dict includes a special
    '_idx' key with the original line number in the log. This lets us delete
    precisely one record by index (line number).
    """
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec["_idx"] = i  # keep original line index
                out.append(rec)
            except Exception:
                # Skip malformed line silently
                pass
    return out


# ---------- Single-record + image delete helpers ----------

def load_jsonl_with_index(path=JSONL_PATH):
    """
    Read JSONL and return a list of dicts where each dict includes '_idx'
    with the original zero-based line index in the log.
    """
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec["_idx"] = i
                out.append(rec)
            except Exception:
                # Skip malformed line silently
                pass
    return out


def delete_record_and_image_by_index(target_idx: int,
                                     jsonl_path=JSONL_PATH,
                                     img_dir=SUMMARY_DIR):
    """
    Atomically remove a single JSONL line by its index, and delete its
    referenced summary image (if any). Returns (success: bool, image_name: str|None).
    """
    if not os.path.exists(jsonl_path):
        return False, None

    # Read all lines first so we can parse the one we’ll delete
    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as src:
        lines = src.readlines()

    if target_idx < 0 or target_idx >= len(lines):
        return False, None

    img_to_delete = None
    try:
        target_obj = json.loads(lines[target_idx])
        img_to_delete = target_obj.get("summary_image") or None
    except Exception:
        # Even if the line is malformed JSON, we still remove it
        pass

    # Rewrite file without the target line
    tmp_path = jsonl_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as dst:
        for i, line in enumerate(lines):
            if i != target_idx:
                dst.write(line)
    os.replace(tmp_path, jsonl_path)

    # Delete the associated image (best-effort)
    if img_to_delete:
        img_path = os.path.join(img_dir, img_to_delete)
        try:
            os.remove(img_path)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    return True, img_to_delete


def delete_all_records_and_images(jsonl_path=JSONL_PATH, img_dir=SUMMARY_DIR):
    """
    Hard-delete ALL records and ALL .png summary images.
    Returns count of images deleted.
    """
    # Clear JSONL
    if os.path.exists(jsonl_path):
        open(jsonl_path, "w").close()

    # Remove all PNGs
    deleted = 0
    if os.path.isdir(img_dir):
        for name in os.listdir(img_dir):
            if name.lower().endswith(".png"):
                try:
                    os.remove(os.path.join(img_dir, name))
                    deleted += 1
                except Exception:
                    pass
    return deleted
    
def collect_export_record(form):
    safe_site = re.sub(r'\W+', '_', form["site"]).strip("_")
    submission_id = f"{form['date'].replace('-', '')}_{safe_site}"

    veg = [k for k, v in form["vegetation"].items() if v and k != "Other"]
    if form["vegetation"].get("Other") and form["vegetation_other"].strip():
        veg.append(f"Other:{form['vegetation_other'].strip()}")

    dom = [k for k, v in form["dominant_species"].items() if v and k != "Other"]
    if form["dominant_species"].get("Other") and form["dominant_other"].strip():
        dom.append(f"Other:{form['dominant_other'].strip()}")

    landform = [k for k, v in form["landform"].items() if v]

    return {
        "submission_id": submission_id,
        "date": form["date"],
        "site": form["site"],
        "vegetation": "; ".join(veg),
        "dominant_species": "; ".join(dom),
        "landform": "; ".join(landform),
        "fire_presence": form["fire_presence"],
        "fire_intensity": form["fire_intensity"],
        "dieback": form["dieback"],
        "drought_stress": form["drought_stress"],
        "stressed_taxa": form["stressed_taxa"],
        "weeds_species": form["weeds_species"],
        "weeds_percent": form["weeds_percent"],
        "animals_rabbits": form["animals"]["Rabbits"],
        "animals_kangaroo": form["animals"]["Kangaroo (grazing)"],
        "animals_pigs": form["animals"]["Pigs"],
        "animals_hdc": form["animals"]["Horse/Donkey/Cattle"],
        "animals_other": form["animals"]["Other feral"],
        "animals_other_text": form["animals_other_text"],
        "other_comments": form["other_comments"],
        "summary_image": "",  # set after image save
    }

# ---------- Summary image ----------
def draw_summary_image(record_path, form):
    W, H = 1200, 900
    margin = 40
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 34)
        font_h = ImageFont.truetype("arial.ttf", 26)
        font_b = ImageFont.truetype("arial.ttf", 22)
        font_s = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = ImageFont.load_default()
        font_h = ImageFont.load_default()
        font_b = ImageFont.load_default()
        font_s = ImageFont.load_default()

    draw.text((margin, margin), "FHMP Flora – Site Characteristics Summary", fill=(0, 0, 0), font=font_title)
    y = margin + 50
    draw.text((margin, y), f"Date: {form['date']}   Site: {form['site']}", fill=(0, 0, 0), font=font_b)
    y += 36

    def print_block(header, text, y):
        draw.text((margin, y), header, fill=(15, 60, 130), font=font_h)
        y += 30
        for line in wrap(text or "-", width=100):
            draw.text((margin + 20, y), u"• " + line, fill=(0, 0, 0), font=font_b)
            y += 26
        return y + 6

    def join_selected(d, other_key=None, other_text=""):
        sel = [k for k, v in d.items() if v and (other_key is None or k != other_key)]
        if other_key and d.get(other_key) and other_text.strip():
            sel.append(f"Other: {other_text.strip()}")
        return "; ".join(sel)

    y = print_block("Vegetation", join_selected(form["vegetation"], "Other", form["vegetation_other"]), y)
    y = print_block("Dominant species", join_selected(form["dominant_species"], "Other", form["dominant_other"]), y)
    y = print_block("Landform", "; ".join([k for k, v in form["landform"].items() if v]), y)
    y = print_block("Fire", f"Presence: {form['fire_presence']}\nIntensity: {form['fire_intensity']}", y)
    y = print_block(
        "Dieback & Drought stress",
        f"Dieback: {form['dieback']}; Drought: {form['drought_stress']}; "
        f"Stressed taxa: {form['stressed_taxa'] or '-'}",
        y,
    )
    y = print_block(
        "Weeds",
        f"Species: {form['weeds_species'] or '-'}; % weeds: {form['weeds_percent']}%",
        y,
    )

    # Animals visual
    draw.text((margin, y), "Animal presence (0=None, 1=Light, 2=Moderate, 3=Heavy)",
              fill=(15, 60, 130), font=font_h)
    y += 30
    x0 = margin + 20
    bar_w = 220
    bar_h = 16
    gap = 24
    for a in ANIMAL_TYPES:
        val = form["animals"][a]
        draw.text((x0, y - 2), a, fill=(0, 0, 0), font=font_s)
        draw.rectangle([x0 + 280, y, x0 + 280 + bar_w, y + bar_h], outline=(120, 120, 120), width=1)
        fill_w = int((val / 3.0) * bar_w)
        draw.rectangle([x0 + 280, y, x0 + 280 + fill_w, y + bar_h], fill=(80, 150, 80))
        draw.text((x0 + 280 + bar_w + 10, y - 2), str(val), fill=(0, 0, 0), font=font_s)
        y += gap

    if form["animals"]["Other feral"] and form["animals_other_text"]:
        draw.text((x0, y), f"Other feral notes: {form['animals_other_text']}", fill=(0, 0, 0), font=font_s)
        y += gap

    y += 10
    y = print_block("Other comments", form["other_comments"], y)

    img.save(record_path)
    return record_path
 
# ---------- Step validation (controls Next/Finish availability) ----------

def validate_step(form, step) -> tuple[bool, list[str]]:
    """
    Returns (is_ok, messages) for the current step only.
    We only validate what's on the screen, to keep UX simple.
    """
    errors = []

    # Step 0: Details
    if step == 0:
        if not form["site"].strip():
            errors.append("Enter a Site name/code to continue.")

    # Step 1: Vegetation → Other requires text
    if step == 1:
        if form["vegetation"].get("Other") and not form.get("vegetation_other", "").strip():
            errors.append("Provide text for Vegetation → Other.")

    # Step 2: Dominant species → Other requires text
    if step == 2:
        if form["dominant_species"].get("Other") and not form.get("dominant_other", "").strip():
            errors.append("Provide text for Dominant species → Other.")

    # Step 7: Animals → if 'Other feral' > 0 requires notes
    if step == 7:
        if form["animals"].get("Other feral", 0) > 0 and not form.get("animals_other_text", "").strip():
            errors.append("Provide notes for Animals → Other feral.")

    return (len(errors) == 0, errors)

# ---------- UI ----------
init_session()
st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(APP_TITLE)

# Step control (reduced steps after removing sections)
LAST_FORM_STEP = 8   # 0..8 are form pages
EXPORT_STEP = 9      # 9 = confirmation

if st.session_state.mode == "splash":
    st.write("Choose an action:")
    c1, c2 = st.columns(2)
    if c1.button("➕ Create new", use_container_width=True):
        st.session_state.mode = "new"
        st.session_state.step = 0
        st.rerun()
    if c2.button("📂 View previous", use_container_width=True):
        st.session_state.mode = "view"
        st.rerun()

elif st.session_state.mode == "view":
    st.subheader("Previous records")

    # --- Inline confirmation UIs (shown at the top so they are hard to miss) ---
    if st.session_state.confirm_delete and st.session_state.confirm_rec is not None:
        rec = st.session_state.confirm_rec
        with st.container(border=True):
            st.warning(
                f"Are you sure you want to delete this record **and its image**?\n\n"
                f"- **submission_id**: {rec.get('submission_id','')}\n"
                f"- **site**: {rec.get('site','')}\n"
                f"- **date**: {rec.get('date','')}\n"
                f"- **image**: {rec.get('summary_image','(none)')}"
            )
            c1, c2 = st.columns([1, 1])
            if c1.button("✅ Yes, delete", type="primary", key="confirm_del_yes"):
                ok, img_name = delete_record_and_image_by_index(rec["_idx"])
                st.session_state.confirm_delete = False
                st.session_state.confirm_rec = None
                if ok:
                    msg = "Record deleted."
                    if img_name:
                        msg += f" Image removed: {img_name}"
                    st.success(msg)
                else:
                    st.error("Could not delete the selected record.")
                st.rerun()
            if c2.button("Cancel", key="confirm_del_no"):
                st.session_state.confirm_delete = False
                st.session_state.confirm_rec = None
                st.rerun()

    # Clean up any leftover input key when the confirm dialog is not active
    if not st.session_state.confirm_delete_all and "confirm_delete_all_input" in st.session_state:
        st.session_state.pop("confirm_delete_all_input", None)

    if st.session_state.confirm_delete_all:
        with st.container(border=True):
            st.warning(
                "This will **delete ALL records and ALL summary images**. This cannot be undone."
            )
            st.text_input("Type **DELETE** to confirm:", key="confirm_delete_all_input")

            ok_to_delete = (
                st.session_state.get("confirm_delete_all_input", "").strip().upper() == "DELETE"
            )

            c1, c2 = st.columns([1, 1])
            if c1.button(
                "🗑️ Yes, delete EVERYTHING",
                type="primary",
                key="confirm_all_yes",
                disabled=not ok_to_delete,
            ):
                img_count = delete_all_records_and_images()
                # IMPORTANT: don't write to the widget key here; just clear the flag and pop the input
                st.session_state.confirm_delete_all = False
                st.session_state.pop("confirm_delete_all_input", None)
                st.success(f"All records deleted. Removed {img_count} image(s).")
                st.rerun()

            if c2.button("Cancel", key="confirm_all_no"):
                st.session_state.confirm_delete_all = False
                st.session_state.pop("confirm_delete_all_input", None)
                st.rerun()

    # --- Table + downloads ---
    recs_with_idx = load_jsonl_with_index()
    if recs_with_idx:
        df_display = pd.DataFrame(recs_with_idx).drop(columns=["_idx"]).reindex(columns=COLUMNS)
        st.dataframe(df_display, use_container_width=True, height=320)
        csv_bytes = df_display.to_csv(index=False).encode("utf-8")
        st.download_button("Download full CSV", data=csv_bytes, file_name=CSV_EXPORT_NAME)
    else:
        st.info("No records yet. Create a new entry first.")

    # --- Manage a single record (now with confirmation) ---
    st.markdown("### Manage individual records")
    if recs_with_idx:
        labels = [
            f"[{r['_idx']}] {r.get('submission_id','')} — {r.get('site','')} ({r.get('date','')})"
            for r in recs_with_idx
        ]
        label_to_rec = {lab: r for lab, r in zip(labels, recs_with_idx)}
        sel_label = st.selectbox("Select a record", labels)
        sel_rec = label_to_rec[sel_label]

        with st.expander("Preview selected record"):
            st.json({k: v for k, v in sel_rec.items() if k != "_idx"})

        # Instead of immediate delete, open confirmation
        if st.button("🗑️ Delete record & image", key="open_confirm_single"):
            st.session_state.confirm_delete = True
            st.session_state.confirm_rec = sel_rec
            st.rerun()
    else:
        st.caption("No records to manage.")

    st.markdown("---")
    cols_bottom = st.columns(3)

    # Instead of immediate bulk delete, open confirmation
    if cols_bottom[0].button("🗑️ Delete ALL records & images", key="open_confirm_all"):
        st.session_state.confirm_delete_all = True
        st.session_state.confirm_delete_all_text = ""
        st.rerun()

    if st.button("⬅ Back to home"):
        reset_to_splash()
        st.rerun()

elif st.session_state.mode == "new":
    form = st.session_state.form
    step = st.session_state.step

    # ---- step content ----
    if step == 0:
        st.subheader("Details")
        form["date"] = st.date_input("Date", value=datetime.fromisoformat(form["date"]).date()).isoformat()
        form["site"] = st.text_input("Site", value=form["site"], placeholder="Enter a site name/code")
        if not form["site"].strip():
            st.info("Enter a Site name/code to continue.")

    elif step == 1:
        st.subheader("Vegetation")
        for v in VEGETATION:
            form["vegetation"][v] = st.checkbox(v, value=form["vegetation"][v])
        if form["vegetation"]["Other"]:
            form["vegetation_other"] = st.text_input(
                "Other (Vegetation) — required when 'Other' is selected",
                value=form["vegetation_other"]
        )

    elif step == 2:
        st.subheader("Dominant species")
        for s in DOMINANT_SPECIES:
            form["dominant_species"][s] = st.checkbox(s, value=form["dominant_species"][s])
        
        if form["dominant_species"]["Other"]:
            form["dominant_other"] = st.text_input(
                "Other (Dominant species) — required when 'Other' is selected",
                value=form["dominant_other"]
            )


    elif step == 3:
        st.subheader("Landform")
        for l in LANDFORM:
            form["landform"][l] = st.checkbox(l, value=form["landform"][l])

    elif step == 4:
        st.subheader("Fire")
        form["fire_presence"] = st.radio("Presence", FIRE_PRESENCE, index=FIRE_PRESENCE.index(form["fire_presence"]))
        form["fire_intensity"] = st.radio("Intensity", FIRE_INTENSITY, index=FIRE_INTENSITY.index(form["fire_intensity"]))

    elif step == 5:
        st.subheader("Dieback & Drought stress")
        form["dieback"] = st.radio("Dieback", DIEBACK, index=DIEBACK.index(form["dieback"]))
        form["drought_stress"] = st.radio("Drought stress", DROUGHT_STRESS, index=DROUGHT_STRESS.index(form["drought_stress"]))
        form["stressed_taxa"] = st.text_input("Stressed taxa (if any)", value=form["stressed_taxa"])

    elif step == 6:
        st.subheader("Weeds")
        form["weeds_species"] = st.text_area("Weeds: Species", value=form["weeds_species"])
        form["weeds_percent"] = st.number_input("% of vegetation that is weeds", min_value=0, max_value=100,
                                               value=int(form["weeds_percent"]))

    elif step == 7:
        st.subheader("Animal presence (0=None, 1=Light, 2=Moderate, 3=Heavy)")
        for a in ANIMAL_TYPES:
            form["animals"][a] = st.select_slider(a, options=[0, 1, 2, 3], value=form["animals"][a])
        if form["animals"]["Other feral"] > 0:
            form["animals_other_text"] = st.text_input(
                "Other feral (notes) — required when 'Other feral' > 0",
                value=form["animals_other_text"]
        )

    elif step == 8:
        st.subheader("Other comments")
        form["other_comments"] = st.text_area("Comments", value=form["other_comments"], height=150)

    elif step == EXPORT_STEP:
        st.subheader("✅ Export Complete")
        st.success("Saved! Record appended to JSONL and summary image generated.")
        st.image(st.session_state.export_image_path, caption="Summary")

        # Single-record CSV download (built from the record)
        df_single = pd.DataFrame([st.session_state.export_record]).reindex(columns=COLUMNS)
        st.download_button(
            "Download this record as CSV",
            data=df_single.to_csv(index=False).encode("utf-8"),
            file_name=st.session_state.export_csv_name,
        )
        with open(st.session_state.export_image_path, "rb") as f:
            st.download_button("Download summary image (PNG)", data=f,
                               file_name=st.session_state.export_image_name)
        if st.button("Done (Back to home)"):
            reset_to_splash()
            st.rerun()

        # ---- navigation ----
    if step <= LAST_FORM_STEP:
        st.markdown("---")
        cols = st.columns(3)

        # Validate current step
        is_ok, messages = validate_step(form, step)
        if not is_ok:
            for m in messages:
                st.warning(m)

        # Back: on step 0 return to splash; otherwise step-1
        if cols[0].button("⬅ Back"):
            if step == 0:
                reset_to_splash()
            else:
                st.session_state.step = max(0, step - 1)
            st.rerun()

        # Next / Finish
        if step < LAST_FORM_STEP:
            if cols[2].button("Next ➡", disabled=not is_ok):
                st.session_state.step = step + 1
                st.rerun()
        else:
            # Finish at LAST_FORM_STEP
            if cols[2].button("✅ Finish & Export", disabled=not is_ok):
                record = collect_export_record(form)

                # Safety guard (unchanged)
                if not isinstance(record, dict) or "submission_id" not in record:
                    st.error("Internal error: export record not formed as expected.")
                    st.caption(f"type(record)={type(record)}; keys={list(record.keys()) if isinstance(record, dict) else 'n/a'}")
                    st.stop()

                image_name = f"{record['submission_id']}.png"
                image_path = os.path.join(SUMMARY_DIR, image_name)
                draw_summary_image(image_path, form)
                record["summary_image"] = image_name

                write_jsonl_record(record)

                # Store export data for confirmation screen
                st.session_state.export_record = record
                st.session_state.export_image_path = image_path
                st.session_state.export_csv_name = f"{record['submission_id']}_site_characteristics.csv"
                st.session_state.export_image_name = image_name

                st.session_state.step = EXPORT_STEP
                st.rerun()