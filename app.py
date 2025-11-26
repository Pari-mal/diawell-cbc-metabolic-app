import math
from datetime import date

import streamlit as st


# ----------------- Utility functions ----------------- #

def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def classify_index(value, cutoffs):
    """
    Generic classifier:
    cutoffs = [(upper_limit, label), ...]
    Returns label for first upper_limit where value <= upper_limit,
    else returns label of last cutoff.
    """
    if value is None:
        return "NA"
    for limit, label in cutoffs:
        if value <= limit:
            return label
    return cutoffs[-1][1]


def risk_from_total(total_score):
    if total_score is None:
        return "NA"
    if total_score < 20:
        return "Very low risk"
    elif total_score < 40:
        return "Mild risk"
    elif total_score < 70:
        return "Moderate risk"
    else:
        return "High risk"


# ----------------- Core calculations ----------------- #

def calculate_indices(inputs):
    age = safe_float(inputs.get("age"))
    sex = inputs.get("sex", "M")
    diabetes_flag = inputs.get("diabetes", False)

    wbc = safe_float(inputs.get("wbc"))             # ×10⁹/L
    neut_pct = safe_float(inputs.get("neut_pct"))   # %
    lymph_pct = safe_float(inputs.get("lymph_pct")) # %
    mono_pct = safe_float(inputs.get("mono_pct"))   # %
    platelets = safe_float(inputs.get("platelets")) # ×10⁹/L

    fasting_glu = safe_float(inputs.get("fasting_glu"))  # mg/dL
    tg = safe_float(inputs.get("tg"))                   # mg/dL
    hdl = safe_float(inputs.get("hdl"))                 # mg/dL
    ast = safe_float(inputs.get("ast"))                 # IU/L
    alt = safe_float(inputs.get("alt"))                 # IU/L
    hba1c = safe_float(inputs.get("hba1c"))             # %

    weight = safe_float(inputs.get("weight"))  # kg
    height = safe_float(inputs.get("height"))  # cm
    waist = safe_float(inputs.get("waist"))    # cm
    htn = inputs.get("htn", False)

    # ---- Anthropometry ---- #
    bmi = None
    if weight and height:
        bmi = weight / ((height / 100.0) ** 2)

    # ---- Absolute CBC counts ---- #
    anc = alc = amc = None
    if wbc is not None:
        if neut_pct is not None:
            anc = wbc * neut_pct / 100.0
        if lymph_pct is not None:
            alc = wbc * lymph_pct / 100.0
        if mono_pct is not None:
            amc = wbc * mono_pct / 100.0

    # ----- Inflammatory indices ----- #

    nlr = None
    if anc is not None and alc and alc != 0:
        nlr = anc / alc

    plr = None
    if platelets is not None and alc and alc != 0:
        plr = platelets / alc

    sii = None
    if platelets is not None and anc is not None and alc and alc != 0:
        # Standard definition: (Platelets × ANC) / ALC
        sii = (platelets * anc) / alc

    siri = None
    if anc is not None and amc is not None and alc and alc != 0:
        # Correct definition: (ANC × AMC) / ALC
        siri = (anc * amc) / alc

    # ----- Atherogenic / metabolic indices ----- #

    # AIP: log10(TG(mmol/L) / HDL(mmol/L))
    aip = None
    if tg and hdl and hdl > 0:
        tg_mmol = tg / 88.57
        hdl_mmol = hdl / 38.67
        if hdl_mmol > 0:
            aip = math.log10(tg_mmol / hdl_mmol)

    # TyG: ln [ TG (mg/dL) * FPG (mg/dL) / 2 ]
    tyg = None
    if tg and fasting_glu:
        tyg = math.log(tg * fasting_glu / 2.0)

    # METS-IR: ln(2*FPG + TG) * BMI / ln(HDL)
    mets_ir = None
    if fasting_glu and tg and bmi and hdl and hdl > 0:
        try:
            mets_ir = math.log(2 * fasting_glu + tg) * bmi / math.log(hdl)
        except ValueError:
            mets_ir = None

    # Hepatic Steatosis Index
    hsi = None
    if alt and ast and ast != 0 and bmi:
        hsi = 8 * (alt / ast) + bmi
        if sex.upper() == "F":
            hsi += 2
        if diabetes_flag:
            hsi += 2

    # FIB-4
    fib4 = None
    if age and ast and alt and platelets and alt > 0 and platelets > 0:
        fib4 = (age * ast) / (platelets * math.sqrt(alt))

    # eGDR (higher = better insulin sensitivity)
    egdr = None
    if waist and hba1c:
        egdr = 21.16 - (0.09 * waist) - (3.41 * (1 if htn else 0)) - (0.55 * hba1c)

    indices = {
        "NLR": nlr,
        "PLR": plr,
        "SII": sii,
        "SIRI": siri,
        "AIP": aip,
        "TyG": tyg,
        "METS-IR": mets_ir,
        "HSI": hsi,
        "FIB-4": fib4,
        "eGDR": egdr,
    }

    # ----- Severity labels per index (UPDATED CUTOFFS) ----- #

    idx_sev = {}

    # NLR
    idx_sev["NLR"] = classify_index(
        nlr,
        [
            (2.0, "Normal"),
            (3.0, "Mild high"),
            (5.0, "Moderate high"),
        ],
    )

    # PLR
    idx_sev["PLR"] = classify_index(
        plr,
        [
            (150, "Normal"),
            (200, "Mild high"),
            (300, "Moderate high"),
        ],
    )

    # SII
    idx_sev["SII"] = classify_index(
        sii,
        [
            (500, "Normal"),
            (800, "Mild high"),
            (1200, "Moderate high"),
        ],
    )

    # SIRI
    idx_sev["SIRI"] = classify_index(
        siri,
        [
            (1.0, "Normal"),
            (1.5, "Mild high"),
            (3.0, "Moderate high"),
        ],
    )

    # AIP (mmol/L-based)
    idx_sev["AIP"] = classify_index(
        aip,
        [
            (0.11, "Low risk"),
            (0.15, "Borderline"),
            (0.21, "Intermediate"),
        ],
    )

    # TyG
    idx_sev["TyG"] = classify_index(
        tyg,
        [
            (8.5, "Normal"),
            (9.0, "Mild high"),
            (9.5, "Moderate high"),
        ],
    )

    # METS-IR
    idx_sev["METS-IR"] = classify_index(
        mets_ir,
        [
            (40, "Normal"),
            (50, "Mild high"),
            (60, "Moderate high"),
        ],
    )

    # HSI
    idx_sev["HSI"] = classify_index(
        hsi,
        [
            (30, "Low"),
            (36, "Borderline"),
        ],
    )

    # FIB-4
    idx_sev["FIB-4"] = classify_index(
        fib4,
        [
            (1.3, "Low"),
            (2.67, "Indeterminate"),
        ],
    )

    # eGDR (higher is better)
    # >8.0: Normal; 6–8: Mild low; 4–6: Moderate low; <4: Severe low
    idx_sev["eGDR"] = classify_index(
        egdr,
        [
            (4.0, "Severe low"),
            (6.0, "Moderate low"),
            (8.0, "Mild low"),
        ],
    )

    # ---- Map severity → numeric penalty for domain scores ---- #

    def sev_to_score(label):
        if label in ("NA", None):
            return 0
        # "Good" / low-risk labels
        if label in ("Normal", "Low", "Low risk"):
            return 0
        # Mild / Borderline
        if "Mild" in label or "Borderline" in label:
            return 1
        # Moderate, Intermediate, Indeterminate
        if "Moderate" in label or "Intermediate" in label or "Indeterminate" in label:
            return 2
        # High / Severe
        if "High" in label or "Severe" in label:
            return 3
        return 0

    # Domains
    dom_map = {
        "Inflammation": ["NLR", "PLR", "SII", "SIRI"],
        "Oxidative / Hb-MCV": ["AIP"],
        "Endothelial": ["AIP", "METS-IR"],
        "Metabolic / Liver / IR": ["TyG", "METS-IR", "HSI", "FIB-4", "eGDR"],
    }

    domain_scores = {}
    domain_labels = {}

    for dom, keys in dom_map.items():
        vals = [sev_to_score(idx_sev[k]) for k in keys if k in idx_sev]
        if not vals:
            domain_scores[dom] = 0.0
            domain_labels[dom] = "NA"
            continue

        raw = sum(vals)
        max_raw = len(vals) * 3  # max 3 per index
        score_0_25 = round((raw / max_raw) * 25, 1)
        domain_scores[dom] = score_0_25

        if score_0_25 < 6:
            lab = "Normal"
        elif score_0_25 < 12:
            lab = "Mild"
        elif score_0_25 < 18:
            lab = "Moderate"
        else:
            lab = "Severe"
        domain_labels[dom] = lab

    total_score = sum(domain_scores.values())
    risk_cat = risk_from_total(total_score)

    return indices, idx_sev, domain_scores, domain_labels, total_score, risk_cat


# ----------------- PDF builder ----------------- #

def build_pdf(patient, indices, idx_sev, domain_scores, domain_labels, total_score, risk_cat):
    """
    Returns: bytes (PDF), robust to different fpdf2 return types.
    """
    from fpdf import FPDF  # ensure fpdf2 in requirements.txt

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Effective printable width
    try:
        effective_width = pdf.epw  # fpdf2 convenience
    except AttributeError:
        effective_width = pdf.w - pdf.l_margin - pdf.r_margin

    # --------- Header --------- #
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DiaWell C.O.R.E. Foundation - Metabolic Health Report", ln=True)

    pdf.ln(3)
    pdf.set_font("Helvetica", "", 11)

    line1 = f"Patient Name: {patient.get('name', '')}"
    line2 = f"Age/Sex: {patient.get('age', '')} / {patient.get('sex', '')}"
    line3 = f"Date: {patient.get('date', '')}"
    line4 = f"Diabetes: {'Yes' if patient.get('diabetes', False) else 'No'}"

    pdf.cell(0, 6, line1, ln=True)
    pdf.cell(0, 6, line2, ln=True)
    pdf.cell(0, 6, line3, ln=True)
    pdf.cell(0, 6, line4, ln=True)

    pdf.ln(5)

    # --------- Overall summary --------- #
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Overall Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)

    score_str = f"{round(total_score, 1)}" if total_score is not None else "NA"
    pdf.cell(0, 6, f"Total Score (0-100): {score_str}", ln=True)
    pdf.cell(0, 6, f"Risk Category: {risk_cat}", ln=True)

    # --------- Domain scores --------- #
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Domain Scores (0-25 each)", ln=True)
    pdf.set_font("Helvetica", "", 11)

    for dom in ["Inflammation", "Oxidative / Hb-MCV", "Endothelial", "Metabolic / Liver / IR"]:
        sc = domain_scores.get(dom, 0.0)
        lab = domain_labels.get(dom, "NA")
        pdf.cell(0, 6, f"{dom}: {round(sc, 1)} ({lab})", ln=True)

    # --------- Key indices --------- #
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Key Indices (with severity)", ln=True)
    pdf.set_font("Helvetica", "", 11)

    order = ["NLR", "PLR", "SII", "SIRI", "TyG", "METS-IR", "AIP", "HSI", "FIB-4", "eGDR"]
    for key in order:
        val = indices.get(key)
        lab = idx_sev.get(key, "NA")
        if val is None:
            val_str = "NA"
        else:
            if abs(val) >= 100:
                val_str = f"{val:.1f}"
            else:
                val_str = f"{val:.2f}"
        pdf.cell(0, 6, f"{key}: {val_str} ({lab})", ln=True)

    # --------- Legend --------- #
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Abbreviation Legend", ln=True)
    pdf.set_font("Helvetica", "", 10)

    legend_lines = [
        "NLR = Neutrophil-to-Lymphocyte Ratio",
        "PLR = Platelet-to-Lymphocyte Ratio",
        "SII = (Platelets × ANC) / ALC",
        "SIRI = (ANC × AMC) / ALC",
        "AIP = log10[TG(mmol/L)/HDL-C(mmol/L)]",
        "HSI = Hepatic Steatosis Index",
        "FIB-4 = Fibrosis-4 Index",
        "TyG = Triglyceride-Glucose Index",
        "METS-IR = Metabolic Score for Insulin Resistance",
        "eGDR = Estimated Glucose Disposal Rate",
    ]

    for ln in legend_lines:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 5, ln)

    # --------- Disclaimer --------- #
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    disclaimer = (
        "This report is for educational and metabolic recovery guidance only and does not "
        "replace clinical judgment or diagnostic workup. Please correlate with full clinical context."
    )
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(effective_width, 5, disclaimer)

    # --------- Return as bytes (robust) --------- #
    result = pdf.output(dest="S")
    if isinstance(result, str):
        pdf_bytes = result.encode("latin-1", "ignore")
    else:
        pdf_bytes = bytes(result)

    return pdf_bytes


# ----------------- Streamlit UI ----------------- #

def main():
    st.set_page_config(page_title="CBC & Metabolic Fitness Marker Report", layout="wide")

    st.title("DiaWell C.O.R.E. – Metabolic Health & CBC Fitness Marker")
    st.write(
        "Enter CBC and metabolic parameters to generate an integrated metabolic health report "
        "with inflammation, atherogenicity, insulin resistance, liver health, and a PDF summary."
    )

    with st.form("input_form"):
        st.subheader("Patient Details")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            name = st.text_input("Name", value="")
        with col2:
            age = st.number_input("Age (years)", min_value=0, max_value=120, value=40)
        with col3:
            sex = st.selectbox("Sex", ["M", "F"])
        with col4:
            diabetes_flag = st.checkbox("Diabetes present?", value=True)

        st.markdown("---")
        st.subheader("Anthropometry")
        c1, c2, c3 = st.columns(3)
        with c1:
            weight = st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.1)
        with c2:
            height = st.number_input("Height (cm)", min_value=0.0, value=170.0, step=0.1)
        with c3:
            waist = st.number_input("Waist (cm)", min_value=0.0, value=95.0, step=0.1)

        htn = st.checkbox("Hypertension present?", value=False)

        st.markdown("---")
        st.subheader("CBC (Complete Blood Count) – key parameters")
        c1, c2, c3 = st.columns(3)
        with c1:
            wbc = st.number_input("Total WBC (×10⁹/L)", min_value=0.0, value=7.5, step=0.1)
            platelets = st.number_input("Platelets (×10⁹/L)", min_value=0.0, value=250.0, step=1.0)
        with c2:
            neut_pct = st.number_input("Neutrophils (%)", min_value=0.0, max_value=100.0, value=55.0, step=0.1)
            lymph_pct = st.number_input("Lymphocytes (%)", min_value=0.0, max_value=100.0, value=30.0, step=0.1)
        with c3:
            mono_pct = st.number_input("Monocytes (%)", min_value=0.0, max_value=100.0, value=8.0, step=0.1)

        st.markdown("---")
        st.subheader("Metabolic / Liver / Lipid Parameters")
        c1, c2, c3 = st.columns(3)
        with c1:
            fasting_glu = st.number_input("Fasting Glucose (mg/dL)", min_value=0.0, value=110.0, step=1.0)
            hba1c = st.number_input("HbA1c (%)", min_value=0.0, max_value=20.0, value=7.0, step=0.1)
        with c2:
            tg = st.number_input("Triglycerides (mg/dL)", min_value=0.0, value=180.0, step=1.0)
            hdl = st.number_input("HDL-C (mg/dL)", min_value=0.0, value=40.0, step=1.0)
        with c3:
            ast = st.number_input("AST (IU/L)", min_value=0.0, value=30.0, step=1.0)
            alt = st.number_input("ALT (IU/L)", min_value=0.0, value=35.0, step=1.0)

        submitted = st.form_submit_button("Calculate & Generate Report")

    if submitted:
        inputs = {
            "age": age,
            "sex": sex,
            "diabetes": diabetes_flag,
            "wbc": wbc,
            "neut_pct": neut_pct,
            "lymph_pct": lymph_pct,
            "mono_pct": mono_pct,
            "platelets": platelets,
            "fasting_glu": fasting_glu,
            "tg": tg,
            "hdl": hdl,
            "ast": ast,
            "alt": alt,
            "hba1c": hba1c,
            "weight": weight,
            "height": height,
            "waist": waist,
            "htn": htn,
        }

        indices, idx_sev, domain_scores, domain_labels, total_score, risk_cat = calculate_indices(inputs)

        st.success("Report calculated successfully.")

        colA, colB = st.columns(2)

        with colA:
            st.subheader("Overall Summary")
            st.metric("Total Score (0-100)", f"{total_score:.1f}")
            st.write(f"**Risk Category:** {risk_cat}")

            st.subheader("Domain Scores (0-25)")
            for dom in ["Inflammation", "Oxidative / Hb-MCV", "Endothelial", "Metabolic / Liver / IR"]:
                sc = domain_scores.get(dom, 0.0)
                lab = domain_labels.get(dom, "NA")
                st.write(f"- **{dom}**: {sc:.1f} ({lab})")

        with colB:
            st.subheader("Key Indices")
            for key in ["NLR", "PLR", "SII", "SIRI", "TyG", "METS-IR", "AIP", "HSI", "FIB-4", "eGDR"]:
                val = indices.get(key)
                lab = idx_sev.get(key, "NA")
                if val is None:
                    disp = "NA"
                else:
                    disp = f"{val:.1f}" if abs(val) >= 100 else f"{val:.2f}"
                st.write(f"- **{key}**: {disp}  ({lab})")

        patient = {
            "name": name,
            "age": age,
            "sex": sex,
            "date": date.today().strftime("%d-%m-%Y"),
            "diabetes": diabetes_flag,
        }

        pdf_bytes = build_pdf(
            patient=patient,
            indices=indices,
            idx_sev=idx_sev,
            domain_scores=domain_scores,
            domain_labels=domain_labels,
            total_score=total_score,
            risk_cat=risk_cat,
        )

        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name=f"DiaWell_Metabolic_Report_{name or 'patient'}.pdf",
            mime="application/pdf",
        )

        st.caption(
            "This tool is for educational and metabolic recovery guidance only and does not replace clinical judgment."
        )


if __name__ == "__main__":
    main()
