# FHMP Flora – Site Characteristics: Streamlit field app
# Author: M365 Copilot for Wess Von Hooton

import os
import re
from datetime import datetime, date
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from textwrap import wrap

APP_TITLE = "FHMP Flora – Site Characteristics"
DATA_DIR = "data"
SUMMARY_DIR = "summaries"
CSV_PATH = os.path.join(DATA_DIR, "site_characteristics.csv")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

# ---------- Reference data ----------
VEGETATION = ["Forest", "Woodland", "Shrubland", "Other"]
DOMINANT_SPECIES = ["Jarrah", "Marri", "Karri", "Wandoo", "Other"]
LANDFORM = ["Crest", "Upper slope", "Midslope", "Lower slope", "Simple slope", "Flat", "Open depression", "Closed depression", "Hillock", "Ridge"]
WATER_FEATURES = ["Riverine permanent", "Riverine seasonal", "Riverine floodplain", "Pool permanent", "Pool seasonal", "Marsh, swamp", "Spring", "Peatland", "Man-made"]
FIRE_PRESENCE = ["No evidence/>10 yrs", "3-10 yrs", "1-3 yrs", "<1 yr"]
FIRE_INTENSITY = ["No evidence", "Patchy (unburned patches up to 2m scorch)", "Low (no unburned patches up to 2m scorch)", "2-5 m scorch", "High (complete canopy scorch)", "Extreme"]
SOIL_COLOUR = ["Grey", "Brown", "Yellow", "Orange", "Red", "Pink", "Pale/Dark"]
SOIL_TYPE = ["Sand", "Loam", "Clay", "Peat"]
DIEBACK = ["No evidence", "Some loss of indicator species", "Extensive loss of indicator species"]
DROUGHT_STRESS = ["No stress evident", "Evident on some individuals", "Evident on some taxa", "Extensive across taxa and site"]
ANIMAL_SCALE = {0: "None", 1: "Light", 2: "Moderate", 3: "Heavy"}
ANIMAL_TYPES = ["Rabbits", "Kangaroo (grazing)", "Pigs", "Horse/Donkey/Cattle", "Other feral"]

# ---------- Session helpers ----------
def init_session():
    if "mode" not in st.session_state:
        st.session_state.mode = "splash"
    if "step" not in st.session_state:
        st.session_state.step = 0
    if "form" not in st.session_state:
        st.session_state.form = default_form()
    if "step_triggered" not in st.session_state:
        st.session_state.step_triggered = False

def default_form():
    return {
        "date": date.today().isoformat(),
        "site": "",
        "vegetation": {v: False for v in VEGETATION},
        "vegetation_other": "",
        "dominant_species": {s: False for s in DOMINANT_SPECIES},
        "dominant_other": "",
        "landform": {l: False for l in LANDFORM},
        "water_features": {w: False for w in WATER_FEATURES},
        "fire_presence": FIRE_PRESENCE[0],
        "fire_intensity": FIRE_INTENSITY[0],
        "coarse_surface": False,
        "rock_outcrop": False,
        "soil_colour": {c: False for c in SOIL_COLOUR},
        "soil_type": {t: False for t in SOIL_TYPE},
        "dieback": DIEBACK[0],
        "drought_stress": DROUGHT_STRESS[0],
        "stressed_taxa": "",
        "weeds_species": "",
        "weeds_extent_density": "",
        "weeds_percent": 0,
        "animals": {a: 0 for a in ANIMAL_TYPES},
        "animals_other_text": "",
        "other_comments": ""
    }

def reset_to_splash():
    st.session_state.mode = "splash"
    st.session_state.step = 0
    st.session_state.form = default_form()

# ---------- Data export ----------
def write_csv_row(row_dict):
    df_row = pd.DataFrame([row_dict])
    write_header = not os.path.exists(CSV_PATH)
    df_row.to_csv(CSV_PATH, mode="a", header=write_header, index=False, encoding="utf-8")

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
    water = [k for k, v in form["water_features"].items() if v]
    soil_colour = [k for k, v in form["soil_colour"].items() if v]
    soil_type = [k for k, v in form["soil_type"].items() if v]
    animals = {k: v for k, v in form["animals"].items() if v != 0}

    return {
        "submission_id": submission_id,
        "date": form["date"],
        "site": form["site"],
        "vegetation": "; ".join(veg),
        "dominant_species": "; ".join(dom),
        "landform": "; ".join(landform),
        "water_features": "; ".join(water),
        "fire_presence": form["fire_presence"],
        "fire_intensity": form["fire_intensity"],
        "coarse_surface": form["coarse_surface"],
        "rock_outcrop": form["rock_outcrop"],
        "soil_colour": "; ".join(soil_colour),
        "soil_type": "; ".join(soil_type),
        "dieback": form["dieback"],
        "drought_stress": form["drought_stress"],
        "stressed_taxa": form["stressed_taxa"],
        "weeds_species": form["weeds_species"],
        "weeds_extent_density": form["weeds_extent_density"],
        "weeds_percent": form["weeds_percent"],
        "animals_rabbits": form["animals"]["Rabbits"],
        "animals_kangaroo": form["animals"]["Kangaroo (grazing)"],
        "animals_pigs": form["animals"]["Pigs"],
        "animals_hdc": form["animals"]["Horse/Donkey/Cattle"],
        "animals_other": form["animals"]["Other feral"],
        "animals_other_text": form["animals_other_text"],
        "other_comments": form["other_comments"],
        "summary_image": "" # filled after PNG saved
    }

def draw_summary_image(record_path, form):
    # Generate a clean PNG summary
    W, H = 1200, 900
    margin = 40
    bg = (255, 255, 255)
    img = Image.new("RGB", (W, H), color=bg)
    draw = ImageDraw.Draw(img)

    # Fonts (fallback to default if these not found)
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

    # Title
    title = f"FHMP Flora – Site Characteristics Summary"
    draw.text((margin, margin), title, fill=(0, 0, 0), font=font_title)

    y = margin + 50
    sub = f"Date: {form['date']}     Site: {form['site']}"
    draw.text((margin, y), sub, fill=(0, 0, 0), font=font_b)
    y += 36

    # Helper to print wrapped lines
    def print_block(header, text, y):
        draw.text((margin, y), header, fill=(15, 60, 130), font=font_h)
        y += 30
        for line in wrap(text or "-", width=100):
            draw.text((margin+20, y), u"• " + line, fill=(0, 0, 0), font=font_b)
            y += 26
        return y + 6

    def join_selected(d, other_key=None, other_text=""):
        sel = [k for k,v in d.items() if v and (other_key is None or k != other_key)]
        if other_key and d.get(other_key) and other_text.strip():
            sel.append(f"Other: {other_text.strip()}")
        return "; ".join(sel)

    y = print_block("Vegetation", join_selected(form["vegetation"], "Other", form["vegetation_other"]), y)
    y = print_block("Dominant species", join_selected(form["dominant_species"], "Other", form["dominant_other"]), y)
    y = print_block("Landform morphology", "; ".join([k for k,v in form["landform"].items() if v]), y)
    y = print_block("Water features", "; ".join([k for k,v in form["water_features"].items() if v]), y)
    y = print_block("Fire", f"Presence: {form['fire_presence']} | Intensity: {form['fire_intensity']}", y)
    y = print_block("Surface & Soils",
                    f"Coarse surface: {'Yes' if form['coarse_surface'] else 'No'}; "
                    f"Rock outcrop: {'Yes' if form['rock_outcrop'] else 'No'}; "
                    f"Soil colour: {', '.join([k for k,v in form['soil_colour'].items() if v])}; "
                    f"Soil type: {', '.join([k for k,v in form['soil_type'].items() if v])}", y)
    y = print_block("Dieback & Drought stress",
                    f"Dieback: {form['dieback']}; Drought: {form['drought_stress']}; "
                    f"Stressed taxa: {form['stressed_taxa'] or '-'}", y)
    y = print_block("Weeds",
                    f"Species: {form['weeds_species'] or '-'}; "
                    f"Extent/Density: {form['weeds_extent_density'] or '-'}; "
                    f"% weeds: {form['weeds_percent']}%", y)

    # Animals with bars
    draw.text((margin, y), "Animal presence (0=None, 1=Light, 2=Moderate, 3=Heavy)", fill=(15, 60, 130), font=font_h)
    y += 30
    x0 = margin + 20
    bar_w = 220
    bar_h = 16
    gap = 24
    for a in ANIMAL_TYPES:
        val = form["animals"][a]
        draw.text((x0, y-2), a, fill=(0,0,0), font=font_s)
        # frame
        draw.rectangle([x0+280, y, x0+280+bar_w, y+bar_h], outline=(120,120,120), width=1)
        # fill
        fill_w = int((val/3.0)*bar_w)
        draw.rectangle([x0+280, y, x0+280+fill_w, y+bar_h], fill=(80, 150, 80))
        draw.text((x0+280+bar_w+10, y-2), str(val), fill=(0,0,0), font=font_s)
        y += gap
    if form["animals"]["Other feral"] and form["animals_other_text"]:
        draw.text((x0, y), f"Other feral notes: {form['animals_other_text']}", fill=(0,0,0), font=font_s)
        y += gap

    # Other comments
    y = y + 10
    y = print_block("Other comments", form["other_comments"], y)

    img.save(record_path)
    return record_path

def reset_to_splash():
    st.session_state.mode = "splash"
    st.session_state.step = 0
    st.session_state.form = default_form()

# ---------- UI ----------
init_session()
st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(APP_TITLE)

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
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        st.dataframe(df, use_container_width=True, height=320)
        st.download_button("Download full CSV", data=open(CSV_PATH, "rb"), file_name="site_characteristics.csv")
    else:
        st.info("No records yet. Create a new entry first.")
    st.markdown("---")
    st.subheader("Saved summary images")
    images = [f for f in os.listdir(SUMMARY_DIR) if f.lower().endswith(".png")]
    if not images:
        st.info("No summary images yet.")
    else:
        for name in sorted(images, reverse=True):
            path = os.path.join(SUMMARY_DIR, name)
            with st.expander(name):
                st.image(path)
                with open(path, "rb") as f:
                    st.download_button("Download image", data=f, file_name=name)
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
        form["site"] = st.text_input("Site", value=form["site"])

    elif step == 1:
        st.subheader("Vegetation")
        for v in VEGETATION:
            form["vegetation"][v] = st.checkbox(v, value=form["vegetation"][v])
        if form["vegetation"]["Other"]:
            form["vegetation_other"] = st.text_input("Other (Vegetation)", value=form["vegetation_other"])

    elif step == 2:
        st.subheader("Dominant species")
        for s in DOMINANT_SPECIES:
            form["dominant_species"][s] = st.checkbox(s, value=form["dominant_species"][s])
        if form["dominant_species"]["Other"]:
            form["dominant_other"] = st.text_input("Other (Dominant species)", value=form["dominant_other"])

    elif step == 3:
        st.subheader("Landform morphology")
        for l in LANDFORM:
            form["landform"][l] = st.checkbox(l, value=form["landform"][l])

    elif step == 4:
        st.subheader("Water features")
        for w in WATER_FEATURES:
            form["water_features"][w] = st.checkbox(w, value=form["water_features"][w])

    elif step == 5:
        st.subheader("Fire")
        form["fire_presence"] = st.radio("Presence", FIRE_PRESENCE, index=FIRE_PRESENCE.index(form["fire_presence"]))
        form["fire_intensity"] = st.radio("Intensity", FIRE_INTENSITY, index=FIRE_INTENSITY.index(form["fire_intensity"]))

    elif step == 6:
        st.subheader("Soils & Surface")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Soil colour**")
            for c in SOIL_COLOUR:
                form["soil_colour"][c] = st.checkbox(c, value=form["soil_colour"][c], key=f"soilc_{c}")
        with c2:
            st.markdown("**Soil type**")
            for t in SOIL_TYPE:
                form["soil_type"][t] = st.checkbox(t, value=form["soil_type"][t], key=f"soilt_{t}")
        st.markdown("---")
        form["coarse_surface"] = st.checkbox("Coarse surface present", value=form["coarse_surface"])
        form["rock_outcrop"] = st.checkbox("Rock outcrop present", value=form["rock_outcrop"])

    elif step == 7:
        st.subheader("Dieback & Drought stress")
        form["dieback"] = st.radio("Dieback", DIEBACK, index=DIEBACK.index(form["dieback"]))
        form["drought_stress"] = st.radio("Drought stress", DROUGHT_STRESS, index=DROUGHT_STRESS.index(form["drought_stress"]))
        form["stressed_taxa"] = st.text_input("Stressed taxa (if any)", value=form["stressed_taxa"])

    elif step == 8:
        st.subheader("Weeds")
        form["weeds_species"] = st.text_area("Weeds: Species", value=form["weeds_species"])
        form["weeds_extent_density"] = st.text_input("Extent and Density", value=form["weeds_extent_density"])
        form["weeds_percent"] = st.number_input("% of vegetation that is weeds", min_value=0, max_value=100, value=int(form["weeds_percent"]))

    elif step == 9:
        st.subheader("Animal presence (0=None, 1=Light, 2=Moderate, 3=Heavy)")
        for a in ANIMAL_TYPES:
            form["animals"][a] = st.select_slider(a, options=[0, 1, 2, 3], value=form["animals"][a])
        if form["animals"]["Other feral"] > 0:
            form["animals_other_text"] = st.text_input("Other feral (notes)", value=form["animals_other_text"])

    elif step == 10:
        st.subheader("Other comments")
        form["other_comments"] = st.text_area("Comments", value=form["other_comments"], height=150)

    elif step == 11:
        st.subheader("✅ Export Complete")
        st.success("Saved! CSV row appended and summary image generated.")
        st.image(st.session_state.export_image_path, caption="Summary")

        df_single = pd.DataFrame([st.session_state.export_record])
        st.download_button("Download this record as CSV",
                           data=df_single.to_csv(index=False).encode("utf-8"),
                           file_name=st.session_state.export_csv_name)

        with open(st.session_state.export_image_path, "rb") as f:
            st.download_button("Download summary image (PNG)", data=f, file_name=st.session_state.export_image_name)

        if st.button("Done (Back to home)"):
            reset_to_splash()
            st.rerun()

    # ---- navigation ----
    if step < 11:
        st.markdown("---")
        cols = st.columns(3)

        if cols[0].button("⬅ Back", disabled=(step == 0)):
            st.session_state.step = max(0, step - 1)
            st.rerun()

        if step < 10:
            if cols[2].button("Next ➡"):
                st.session_state.step = min(10, step + 1)
                st.rerun()
        else:
            if cols[2].button("✅ Finish & Export"):
                record = collect_export_record(form)
                image_name = f"{record['submission_id']}.png"
                image_path = os.path.join(SUMMARY_DIR, image_name)
                draw_summary_image(image_path, form)
                record["summary_image"] = image_name
                write_csv_row(record)

                # Store export data in session state
                st.session_state.export_record = record
                st.session_state.export_image_path = image_path
                st.session_state.export_csv_name = f"{record['submission_id']}_site_characteristics.csv"
                st.session_state.export_image_name = image_name
                st.session_state.step = 11
                st.rerun()
