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
    """Simple classifier using (upper_limit, label) pairs."""
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

    wbc = safe_float(inputs.get("wbc"))
    neut_pct = safe_float(inputs.get("neut_pct"))
    lymph_pct = safe_float(inputs.get("lymph_pct"))
    mono_pct = safe_float(inputs.get("mono_pct"))
    platelets = safe_float(inputs.get("platelets"))

    fasting_glu = safe_float(inputs.get("fasting_glu"))
    tg = safe_float(inputs.get("tg"))
    hdl = safe_float(inputs.get("hdl"))
    ast = safe_float(inputs.get("ast"))
    alt = safe_float(inputs.get("alt"))
    hba1c = safe_float(inputs.get("hba1c"))

    weight = safe_float(inputs.get("weight"))
    height = safe_float(inputs.get("height"))
    waist = safe_float(inputs.get("waist"))
    hip = safe_float(inputs.get("hip"))
    htn = inputs.get("htn", False)

    # BMI & WHR (for future use if needed)
    bmi = None
    if weight and height:
        bmi = weight / ((height / 100.0) ** 2)

    whr = None
    if waist and hip:
        whr = waist / hip

    # ----- Inflammatory indices ----- #

    nlr = None
    if neut_pct and lymph_pct and lymph_pct != 0:
        nlr = neut_pct / lymph_pct

    plr = None
    if wbc and lymph_pct and lymph_pct != 0:
        lymph_abs = wbc * lymph_pct / 100.0
        if lymph_abs > 0 and platelets:
            plr = platelets / lymph_abs
    elif platelets and lymph_pct and lymph_pct != 0:
        # rough fallback
        plr = platelets / lymph_pct

    sii = None
    if platelets and neut_pct and lymph_pct and lymph_pct != 0:
        sii = platelets * (neut_pct / lymph_pct)

    siri = None
    if neut_pct and mono_pct and lymph_pct and lymph_pct != 0:
        siri = (neut_pct * mono_pct) / lymph_pct

    # ----- Atherogenic / metabolic indices ----- #

    aip = None
    if tg and hdl and hdl > 0:
        aip = math.log10(tg / hdl)

    tyg = None
    if tg and fasting_glu:
        tyg = math.log(tg * fasting_glu / 2.0)

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

    # eGDR
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

    # ----- Severity labels per index ----- #

    idx_sev = {}

    idx_sev["NLR"] = classify_index(
        nlr,
        [
            (2.0, "Normal"),
            (3.0, "Mild high"),
            (5.0, "Moderate high"),
        ],
    )

    idx_sev["PLR"] = classify_index(
        plr,
        [
            (150, "Normal"),
            (200, "Mild high"),
            (300, "Moderate high"),
        ],
    )

    idx_sev["SII"] = classify_index(
        sii,
        [
            (500, "Normal"),
            (800, "Mild high"),
            (1200, "Moderate high"),
        ],
    )

    idx_sev["SIRI"] = classify_index(
        siri,
        [
            (1.0, "Normal"),
            (1.5, "Mild high"),
            (3.0, "Moderate high"),
        ],
    )

    idx_sev["AIP"] = classify_index(
        aip,
        [
            (0.11, "Low"),
            (0.21, "Borderline"),
            (0.30, "High"),
        ],
    )

    idx_sev["TyG"] = classify_index(
        tyg,
        [
            (8.5, "Mild high"),
            (9.0, "Moderate high"),
        ],
    )

    idx_sev["METS-IR"] = classify_index(
        mets_ir,
        [
            (40, "Normal"),
            (50, "Mild high"),
            (60, "Moderate high"),
        ],
    )

    idx_sev["HSI"] = classify_index(
        hsi,
        [
            (30, "Low"),
            (36, "Borderline"),
        ],
    )

    idx_sev["FIB-4"] = classify_index(
        fib4,
        [
            (1.3, "Low"),
            (2.67, "Indeterminate"),
        ],
    )

    idx_sev["eGDR"] = classify_index(
        egdr,
        [
            (8.0, "Mild low"),
            (6.0, "Moderate low"),
        ],
    )

    # map severity → numeric penalty
    def sev_to_score(label):
        if label in ("NA", None):
            return 0
        if "Normal" in label or label == "Low":
            return 0
        if "Borderline" in label or "Mild" in label:
            return 1
        if "Moderate" in label or "Indeterminate" in label:
            return 2
        if "High" in label or "Severe" in label or "low" in label:
            return 3
        return 0

    dom_map = {
        "Inflammation": ["NLR", "PLR", "SII", "SIRI"],
        "Oxidative": ["AIP"],
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
        max_raw = len(vals) * 3  # per index max 3
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


# ----------------- PDF builder (safe) ----------------- #

def build_pdf(patient, indices, idx_sev, domain_scores, domain_labels, total_score, risk_cat):
    """
    Returns:
      (pdf_bytes, error_message)
      If error_message is not None, pdf_bytes will be None.
    """
    try:
        from fpdf import FPDF
    except Exception as e:
        return None, f"FPDF import error: {e}"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
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

    # Overall summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Overall Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)

    score_str = f"{round(total_score, 1)}" if total_score is not None else "NA"
    pdf.cell(0, 6, f"Total Score (0-100): {score_str}", ln=True)
    pdf.cell(0, 6, f"Risk Category: {risk_cat}", ln=True)

    # Domain scores
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Domain Scores (0-25 each)", ln=True)
    pdf.set_font("Helvetica", "", 11)

    for dom in ["Inflammation", "Oxidative", "Endothelial", "Metabolic / Liver / IR"]:
        sc = domain_scores.get(dom, 0.0)
        lab = domain_labels.get(dom, "NA")
        pdf.cell(0, 6, f"{dom}: {round(sc, 1)} ({lab})", ln=True)

    # Key indices
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

    # Legend
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Abbreviation Legend", ln=True)
    pdf.set_font("Helvetica", "", 10)

    legend_lines = [
        "NLR = Neutrophil-to-Lymphocyte Ratio",
        "PLR = Platelet-to-Lymphocyte Ratio",
        "SII = Systemic Immune-Inflammation Index",
        "SIRI = Systemic Inflammation Response Index",
        "AIP = Atherogenic Index of Plasma",
        "HSI = Hepatic Steatosis Index",
        "FIB-4 = Fibrosis-4 Index",
        "TyG = Triglyceride-Glucose Index",
        "METS-IR = Metabolic Score for Insulin Resistance",
        "eGDR = Estimated Glucose Disposal Rate",
    ]
    for ln in legend_lines:
        pdf.multi_cell(0, 5, ln)

    # Disclaimer
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    disclaimer = (
        "This report is for educational and metabolic recovery guidance only and does not "
        "replace clinical judgment or diagnostic workup. Please correlate with full clinical context."
    )
    pdf.multi_cell(0, 5, disclaimer)

    # Export PDF safely
    try:
        pdf_bytes = pdf.output(dest="S").encode("latin-1", "ignore")
    except Exception as e:
        return None, f"PDF generation error: {e}"

    return pdf_bytes, None


# ----------------- Streamlit UI ----------------- #

def main():
    st.set_page_config(page_title="CBC & Metabolic Fitness Marker Report", layout="wide")

    st.title("DiaWell C.O.R.E. – Metabolic Health & CBC Fitness Marker")
    st.write(
        "Enter CBC and basic metabolic parameters to generate an integrated metabolic health report "
        "with inflammation and insulin resistance markers, plus a downloadable PDF."
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
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            weight = st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.1)
        with c2:
            height = st.number_input("Height (cm)", min_value=0.0, value=170.0, step=0.1)
        with c3:
            waist = st.number_input("Waist (cm)", min_value=0.0, value=95.0, step=0.1)
        with c4:
            hip = st.number_input("Hip (cm)", min_value=0.0, value=100.0, step=0.1)

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
            "hip": hip,
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
            for dom in ["Inflammation", "Oxidative", "Endothelial", "Metabolic / Liver / IR"]:
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

        pdf_bytes, pdf_err = build_pdf(
            patient=patient,
            indices=indices,
            idx_sev=idx_sev,
            domain_scores=domain_scores,
            domain_labels=domain_labels,
            total_score=total_score,
            risk_cat=risk_cat,
        )

        if pdf_err:
            st.error(f"PDF could not be generated: {pdf_err}")
        else:
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
