import math
import datetime
import streamlit as st
from fpdf import FPDF

# ----------------------------------------------------
#   UNICODE PDF SETUP (DejaVu fonts)
# ----------------------------------------------------

class ReportPDF(FPDF):
    def header(self):
        # Title at top of each page
        self.set_font("DejaVu", "B", 14)
        self.cell(
            0,
            10,
            "DiaWell C.O.R.E. Foundation - CBC + Biochemistry Metabolic Health Report",
            ln=True,
            align="C",
        )
        self.ln(2)

    def footer(self):
        # Page number at bottom
        self.set_y(-15)
        self.set_font("DejaVu", "", 9)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def init_pdf():
    """
    Create a PDF instance with Unicode-ready fonts.
    """
    pdf = ReportPDF()
    # These paths work on Streamlit Cloud's default Linux image.
    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


# ----------------------------------------------------
#   HELPER FUNCTIONS
# ----------------------------------------------------

def safe_div(a, b):
    if b is None or b == 0:
        return None
    return a / b


def severity_to_text(sev, direction="up"):
    """
    Map severity 0-3 to textual label with arrows.
    direction 'up' = worse with higher value,
    direction 'down' = worse with lower value (e.g., eGDR).
    """
    if sev is None:
        return "NA"
    if direction == "down":
        mapping = {
            0: "Normal",
            1: "Mild ↓",
            2: "Moderate ↓",
            3: "Severe ↓",
        }
    else:
        mapping = {
            0: "Normal",
            1: "Mild ↑",
            2: "Moderate ↑",
            3: "Severe ↑",
        }
    return mapping.get(sev, "NA")


def domain_label(score):
    """
    Convert 0-25 domain score to a qualitative label.
    """
    if score < 6:
        return "Near optimal"
    if score < 13:
        return "Mild"
    if score < 19:
        return "Moderate"
    return "Severe"


def overall_risk_label(total_score):
    """
    0-100 total score -> overall risk category.
    """
    if total_score < 25:
        return "Low risk"
    if total_score < 40:
        return "Mild risk"
    if total_score < 60:
        return "Moderate risk"
    return "High risk - intensive optimization needed"


def pdf_safe(text):
    """
    Sanitize text before sending to FPDF:
    - Replace problematic Unicode characters (arrows, dashes, smart quotes, NBSP)
    - Ensure everything is renderable within latin-1.
    """
    if text is None:
        return ""
    s = str(text)
    replacements = {
        "–": "-",
        "—": "-",
        "-": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "↑": " up",
        "↓": " down",
        "→": "->",
        "←": "<-",
        "\u00a0": " ",  # non-breaking space
    }
    return "".join(replacements.get(ch, ch) for ch in s)


# ----------------------------------------------------
#   CORE INDEX CALCULATIONS
# ----------------------------------------------------

def calc_inflammation_block(neut, lymph, mono, plate):
    """
    Inflammation & immune activation:
    NLR, PLR, SII, SIRI, AISI + severities + domain score.
    """

    nlr = safe_div(neut, lymph)
    plr = safe_div(plate, lymph)
    sii = safe_div(plate * neut, lymph) if lymph else None
    siri = safe_div(neut * mono, lymph) if lymph else None
    aisi = neut * lymph * mono if all(x is not None for x in [neut, lymph, mono]) else None

    # ---- Severity cutoffs (0-3) ----
    def sev_nlr(x):
        if x is None:
            return None
        if x <= 2.0:
            return 0
        if x <= 3.0:
            return 1
        if x <= 5.0:
            return 2
        return 3

    def sev_plr(x):
        if x is None:
            return None
        if x < 120:
            return 0
        if x < 150:
            return 1
        if x < 200:
            return 2
        return 3

    def sev_sii(x):
        if x is None:
            return None
        if x < 300:
            return 0
        if x < 600:
            return 1
        if x < 900:
            return 2
        return 3

    def sev_siri(x):
        if x is None:
            return None
        if x < 0.8:
            return 0
        if x < 1.5:
            return 1
        if x < 2.5:
            return 2
        return 3

    def sev_aisi(x):
        if x is None:
            return None
        if x < 150:
            return 0
        if x < 300:
            return 1
        if x < 600:
            return 2
        return 3

    s_nlr = sev_nlr(nlr)
    s_plr = sev_plr(plr)
    s_sii = sev_sii(sii)
    s_siri = sev_siri(siri)
    s_aisi = sev_aisi(aisi)

    severities = [s for s in [s_nlr, s_plr, s_sii, s_siri, s_aisi] if s is not None]
    inflam_sev = sum(severities) / len(severities) if severities else 0
    inflam_score = round(25 * (inflam_sev / 3), 0)

    return {
        "nlr": nlr,
        "plr": plr,
        "sii": sii,
        "siri": siri,
        "aisi": aisi,
        "s_nlr": s_nlr,
        "s_plr": s_plr,
        "s_sii": s_sii,
        "s_siri": s_siri,
        "s_aisi": s_aisi,
        "inflam_sev": inflam_sev,
        "inflam_score": inflam_score,
    }


def calc_oxidative_block(rdw, plate, albumin, hb, mcv):
    """
    Oxidative stress / Hb-MCV / energy:
    RDW, RPR, RAR, Hb/RDW, MCV/Hb, HPR + severities + domain score.
    """
    rpr = safe_div(rdw, plate)
    rar = safe_div(rdw, albumin)
    hbrdw = safe_div(hb, rdw)
    mcvhb = safe_div(mcv, hb)
    hpr = safe_div(hb, plate)

    # RDW (%)
    def sev_rdw(x):
        if x is None:
            return None
        if x < 13.0:
            return 0
        if x < 14.0:
            return 1
        if x < 15.0:
            return 2
        return 3

    # RDW/Platelet
    def sev_rpr(x):
        if x is None:
            return None
        if x < 0.07:
            return 0
        if x < 0.10:
            return 1
        if x < 0.15:
            return 2
        return 3

    # RDW/Albumin
    def sev_rar(x):
        if x is None:
            return None
        if x < 3.0:
            return 0
        if x < 4.0:
            return 1
        if x < 5.0:
            return 2
        return 3

    # Hb/RDW – fatigue / energy stress
    def sev_hbrdw(x):
        if x is None:
            return None
        if x >= 1.35:
            return 0
        if x >= 1.20:
            return 1
        if x >= 1.00:
            return 2
        return 3

    # MCV/Hb – macrocytic tendency
    def sev_mcvhb(x):
        if x is None:
            return None
        if x < 7.0:
            return 0
        if x < 8.0:
            return 1
        if x < 9.0:
            return 2
        return 3

    # Hb/Platelet
    def sev_hpr(x):
        if x is None:
            return None
        if x < 0.07:
            return 0
        if x < 0.09:
            return 1
        if x < 0.12:
            return 2
        return 3

    s_rdw = sev_rdw(rdw)
    s_rpr = sev_rpr(rpr)
    s_rar = sev_rar(rar)
    s_hbrdw = sev_hbrdw(hbrdw)
    s_mcvhb = sev_mcvhb(mcvhb)
    s_hpr = sev_hpr(hpr)

    severities = [s for s in [s_rdw, s_rpr, s_rar, s_hbrdw, s_mcvhb, s_hpr] if s is not None]
    oxid_sev = sum(severities) / len(severities) if severities else 0
    oxid_score = round(25 * (oxid_sev / 3), 0)

    return {
        "rdw": rdw,
        "rpr": rpr,
        "rar": rar,
        "hbrdw": hbrdw,
        "mcvhb": mcvhb,
        "hpr": hpr,
        "s_rdw": s_rdw,
        "s_rpr": s_rpr,
        "s_rar": s_rar,
        "s_hbrdw": s_hbrdw,
        "s_mcvhb": s_mcvhb,
        "s_hpr": s_hpr,
        "oxid_sev": oxid_sev,
        "oxid_score": oxid_score,
    }


def calc_endothelial_block(mono, neut, hdl):
    """
    Endothelial dysfunction & vascular inflammation:
    MHR, NHR + severities + domain score.
    """
    mhr = safe_div(mono, hdl)
    nhr = safe_div(neut, hdl)

    def sev_mhr(x):
        if x is None:
            return None
        if x < 0.010:
            return 0
        if x < 0.020:
            return 1
        if x < 0.030:
            return 2
        return 3

    def sev_nhr(x):
        if x is None:
            return None
        if x < 0.10:
            return 0
        if x < 0.20:
            return 1
        if x < 0.30:
            return 2
        return 3

    s_mhr = sev_mhr(mhr)
    s_nhr = sev_nhr(nhr)

    severities = [s for s in [s_mhr, s_nhr] if s is not None]
    endo_sev = sum(severities) / len(severities) if severities else 0
    endo_score = round(25 * (endo_sev / 3), 0)

    return {
        "mhr": mhr,
        "nhr": nhr,
        "s_mhr": s_mhr,
        "s_nhr": s_nhr,
        "endo_sev": endo_sev,
        "endo_score": endo_score,
    }


def calc_metabolic_block(
    age, sex, diabetes, glu, tg, hdl, ast, alt, hba1c, waist, bmi, htn, plate
):
    """
    Metabolic / IR / Liver / CV risk:
    TyG, METS-IR, AIP (mmol/L-based), HSI, FIB-4, eGDR + severities + domain score.
    """

    # TyG (mg/dL-based standard)
    tyg = None
    if glu > 0 and tg > 0:
        tyg = math.log((glu * tg) / 2)

    # METS-IR
    mets_ir = None
    if glu > 0 and tg > 0 and hdl > 0 and bmi > 0:
        mets_ir = math.log(2 * glu + tg) * bmi / math.log(hdl)

    # AIP - mmol/L version: convert from mg/dL to mmol/L
    aip = None
    if tg > 0 and hdl > 0:
        tg_mmol = tg / 88.5
        hdl_mmol = hdl / 38.7
        if hdl_mmol > 0:
            aip = math.log10(tg_mmol / hdl_mmol)

    # HSI = 8 * (ALT/AST) + BMI + (2 if female) + (2 if diabetes)
    hsi = None
    if ast > 0:
        hsi = 8 * (alt / ast) + bmi
        if sex in ["F", "f"]:
            hsi += 2
        if diabetes == 1:
            hsi += 2

    # FIB-4 = (Age * AST) / (Platelets * sqrt(ALT))
    fib4 = None
    if plate > 0 and alt > 0:
        fib4 = (age * ast) / (plate * math.sqrt(alt))

    # eGDR = 21.158 - 0.09*Waist - 3.407*HTN - 0.551*HbA1c
    egdr = 21.158 - 0.09 * waist - 3.407 * (1 if htn else 0) - 0.551 * hba1c

    # ---- Severities ----

    def sev_tyg(x):
        if x is None:
            return None
        if x < 8.5:
            return 0
        if x < 8.9:
            return 1
        if x < 9.5:
            return 2
        return 3

    def sev_mets(x):
        if x is None:
            return None
        if x < 35:
            return 0
        if x < 40:
            return 1
        if x < 45:
            return 2
        return 3

    # AIP mmol/L thresholds:
    # <0.11 low, 0.11-0.21 intermediate, >0.21 high
    def sev_aip(x):
        if x is None:
            return None
        if x < 0.11:  # low risk
            return 0
        if x <= 0.21:  # intermediate
            return 1
        return 3  # high - counted as severe

    def sev_hsi(x):
        if x is None:
            return None
        if x < 30:
            return 0
        if x < 35:
            return 1
        if x < 40:
            return 2
        return 3

    def sev_fib4(x):
        if x is None:
            return None
        if x < 1.3:
            return 0
        if x < 2.0:
            return 1
        if x < 2.67:
            return 2
        return 3

    # Higher eGDR is better; lower is worse
    def sev_egdr(x):
        if x is None:
            return None
        if x > 8.0:
            return 0
        if x > 6.0:
            return 1
        if x > 4.0:
            return 2
        return 3

    s_tyg = sev_tyg(tyg)
    s_mets = sev_mets(mets_ir)
    s_aip = sev_aip(aip)
    s_hsi = sev_hsi(hsi)
    s_fib4 = sev_fib4(fib4)
    s_egdr = sev_egdr(egdr)

    severities = [s for s in [s_tyg, s_mets, s_aip, s_hsi, s_fib4, s_egdr] if s is not None]
    metab_sev = sum(severities) / len(severities) if severities else 0
    metab_score = round(25 * (metab_sev / 3), 0)

    return {
        "tyg": tyg,
        "mets_ir": mets_ir,
        "aip": aip,
        "hsi": hsi,
        "fib4": fib4,
        "egdr": egdr,
        "s_tyg": s_tyg,
        "s_mets": s_mets,
        "s_aip": s_aip,
        "s_hsi": s_hsi,
        "s_fib4": s_fib4,
        "s_egdr": s_egdr,
        "metab_sev": metab_sev,
        "metab_score": metab_score,
    }


# ----------------------------------------------------
#   PDF REPORT BUILDER
# ----------------------------------------------------

def build_pdf(patient, blocks):
    """
    patient: dict with name, age, sex, diabetes, date
    blocks: dict with domain scores, labels, key index texts, etc.
    """
    pdf = init_pdf()
    pdf.add_page()
    pdf.set_font("DejaVu", "", 11)

    # Patient info
    pdf.cell(0, 8, pdf_safe(f"Patient Name: {patient['name']}"), ln=True)
    pdf.cell(0, 8, pdf_safe(f"Age/Sex: {patient['age']} / {patient['sex']}"), ln=True)
    pdf.cell(0, 8, pdf_safe(f"Date: {patient['date']}"), ln=True)
    pdf.cell(0, 8, pdf_safe(f"Diabetes: {'Yes' if patient['diabetes'] else 'No'}"), ln=True)
    pdf.ln(4)

    # Overall summary
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, pdf_safe("Overall Summary"), ln=True)
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 8, pdf_safe(f"Total Score (0-100): {blocks['total_score']:.1f}"), ln=True)
    pdf.cell(0, 8, pdf_safe(f"Risk Category: {blocks['risk_label']}"), ln=True)
    pdf.ln(4)

    # Domain scores
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, pdf_safe("Domain Scores (0-25 each)"), ln=True)
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(
        0,
        8,
        pdf_safe(f"Inflammation: {blocks['inflam_score']:.1f} / 25 ({blocks['inflam_label']})"),
        ln=True,
    )
    pdf.cell(
        0,
        8,
        pdf_safe(f"Oxidative / Hb-MCV: {blocks['oxid_score']:.1f} / 25 ({blocks['oxid_label']})"),
        ln=True,
    )
    pdf.cell(
        0,
        8,
        pdf_safe(f"Endothelial: {blocks['endo_score']:.1f} / 25 ({blocks['endo_label']})"),
        ln=True,
    )
    pdf.cell(
        0,
        8,
        pdf_safe(f"Metabolic / IR / Liver: {blocks['metab_score']:.1f} / 25 ({blocks['metab_label']})"),
        ln=True,
    )
    pdf.ln(4)

    # Domain-wise comments
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, pdf_safe("Domain-wise Interpretation"), ln=True)
    pdf.set_font("DejaVu", "", 11)

    # NOTE: use fixed width (180) instead of 0 to avoid FPDFException
    pdf.multi_cell(180, 6, pdf_safe(f"Inflammation: {blocks['inflam_comment']}"))
    pdf.multi_cell(180, 6, pdf_safe(f"Oxidative / Hb-MCV: {blocks['oxid_comment']}"))
    pdf.multi_cell(180, 6, pdf_safe(f"Endothelial: {blocks['endo_comment']}"))
    pdf.multi_cell(180, 6, pdf_safe(f"Metabolic / IR / Liver: {blocks['metab_comment']}"))
    pdf.ln(4)

    # Key indices
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, pdf_safe("Key Indices (with severity)"), ln=True)
    pdf.set_font("DejaVu", "", 11)

    for line in blocks["key_indices"]:
        pdf.cell(0, 7, pdf_safe(line), ln=True)

    pdf.ln(4)

    # Full forms
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, pdf_safe("Full Forms of Indices"), ln=True)
    pdf.set_font("DejaVu", "", 10)

    full_forms = [
        "NLR  - Neutrophil-to-Lymphocyte Ratio",
        "PLR  - Platelet-to-Lymphocyte Ratio",
        "SII  - Systemic Immune-Inflammation Index",
        "SIRI - Systemic Inflammation Response Index",
        "AISI - Aggregate Index of Systemic Inflammation",
        "RDW  - Red Cell Distribution Width",
        "RPR  - RDW-to-Platelet Ratio",
        "RAR  - RDW-to-Albumin Ratio",
        "Hb/RDW - Hemoglobin-to-RDW Ratio",
        "MCV/Hb - Mean Corpuscular Volume-to-Hemoglobin Ratio",
        "HPR - Hemoglobin-to-Platelet Ratio",
        "MHR - Monocyte-to-HDL Ratio",
        "NHR - Neutrophil-to-HDL Ratio",
        "TyG - Triglyceride-Glucose Index",
        "METS-IR - Metabolic Score for Insulin Resistance",
        "AIP - Atherogenic Index of Plasma",
        "HSI - Hepatic Steatosis Index",
        "FIB-4 - Fibrosis-4 Index",
        "eGDR - Estimated Glucose Disposal Rate",
    ]

    for ff in full_forms:
        pdf.cell(0, 6, pdf_safe(ff), ln=True)

    pdf.ln(4)
    pdf.set_font("DejaVu", "", 9)
    # Also use fixed width 180 for disclaimer
    pdf.multi_cell(
        180,
        5,
        pdf_safe(
            "Disclaimer: This report is for educational and metabolic recovery guidance only and "
            "does not replace clinical judgment or diagnostic workup. Please correlate with the "
            "full clinical context."
        ),
    )

    # Return PDF as bytes for Streamlit download_button
    return pdf.output(dest="S").encode("latin-1", "ignore")


# ----------------------------------------------------
#   STREAMLIT APP
# ----------------------------------------------------

def main():
    st.set_page_config(
        page_title="DiaWell CBC + Biochemistry Metabolic Health",
        layout="centered",
    )

    st.title("DiaWell C.O.R.E. - CBC + Biochemistry Metabolic Health Dashboard")

    # ----------------- Patient Info -----------------
    st.header("1. Patient Information")
    col1, col2, col3 = st.columns(3)
    with col1:
        patient_name = st.text_input("Patient Name", "Test Patient")
    with col2:
        age = st.number_input("Age (years)", 0, 120, 40)
    with col3:
        sex = st.selectbox("Sex", ["M", "F"])

    diabetes_flag = st.selectbox("Diabetes", ["No / Not known (0)", "Yes (1)"])
    diabetes = 1 if "Yes" in diabetes_flag else 0

    # ----------------- CBC Inputs -----------------
    st.header("2. CBC Inputs")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        neut = st.number_input("Neutrophils (x10^9/L)", 0.0, 30.0, 5.0)
    with c2:
        lymph = st.number_input("Lymphocytes (x10^9/L)", 0.0, 30.0, 2.0)
    with c3:
        mono = st.number_input("Monocytes (x10^9/L)", 0.0, 5.0, 0.5)
    with c4:
        plate = st.number_input("Platelets (x10^9/L)", 0.0, 1000.0, 200.0)

    st.subheader("Hb / RDW / MCV")
    c5, c6, c7 = st.columns(3)
    with c5:
        hb = st.number_input("Hemoglobin (g/dL)", 0.0, 25.0, 13.0)
    with c6:
        rdw = st.number_input("RDW (%)", 0.0, 30.0, 13.0)
    with c7:
        mcv = st.number_input("MCV (fL)", 0.0, 140.0, 96.0)

    # ----------------- Metabolic Inputs -----------------
    st.header("3. Metabolic / Biochemistry Inputs")
    m1, m2, m3 = st.columns(3)
    with m1:
        glu = st.number_input("Glucose (mg/dL)", 0.0, 600.0, 120.0)
        tg = st.number_input("Triglycerides (mg/dL)", 0.0, 2000.0, 200.0)
        hdl = st.number_input("HDL (mg/dL)", 0.0, 200.0, 33.0)
    with m2:
        tc = st.number_input("Total Cholesterol (mg/dL)", 0.0, 400.0, 200.0)
        albumin = st.number_input("Albumin (g/dL)", 0.0, 6.0, 3.4)
        ast = st.number_input("AST (U/L)", 0.0, 500.0, 33.0)
    with m3:
        alt = st.number_input("ALT (U/L)", 0.0, 500.0, 40.0)
        hba1c = st.number_input("HbA1c (%)", 0.0, 20.0, 6.0)
        bmi = st.number_input("BMI (kg/m^2)", 10.0, 60.0, 26.0)

    w1, w2 = st.columns(2)
    with w1:
        waist = st.number_input("Waist circumference (cm)", 40.0, 200.0, 88.0)
    with w2:
        htn_flag = st.selectbox("Hypertension", ["No (0)", "Yes (1)"])
    htn = True if "Yes" in htn_flag else False

    # ----------------- Calculate -----------------
    if st.button("Calculate & Generate Report"):
        infl = calc_inflammation_block(neut, lymph, mono, plate)
        oxid = calc_oxidative_block(rdw, plate, albumin, hb, mcv)
        endo = calc_endothelial_block(mono, neut, hdl)
        metab = calc_metabolic_block(
            age, sex, diabetes, glu, tg, hdl, ast, alt, hba1c, waist, bmi, htn, plate
        )

        total_score = infl["inflam_score"] + oxid["oxid_score"] + endo["endo_score"] + metab["metab_score"]
        label = overall_risk_label(total_score)

        # Domain labels
        inflam_label = domain_label(infl["inflam_score"])
        oxid_label = domain_label(oxid["oxid_score"])
        endo_label = domain_label(endo["endo_score"])
        metab_label = domain_label(metab["metab_score"])

        # Domain comments
        inflam_comment_map = {
            "Near optimal": "No significant systemic inflammation on CBC-derived indices.",
            "Mild": "Mild elevation in inflammatory markers; consider lifestyle optimization and monitoring.",
            "Moderate": "Moderate systemic inflammation; evaluate for chronic inflammatory or metabolic drivers.",
            "Severe": "Marked systemic inflammation; consider detailed workup and aggressive risk modification.",
        }
        oxid_comment_map = {
            "Near optimal": "No major signal of oxidative or hematologic stress.",
            "Mild": "Mild signal of oxidative or hematologic stress; correlate with fatigue, B12/folate, and nutrition.",
            "Moderate": "Moderate oxidative or energy stress; consider micronutrient and mitochondrial support.",
            "Severe": "Severe hematologic or oxidative stress pattern; rule out deficiency, chronic disease, or marrow stress.",
        }
        endo_comment_map = {
            "Near optimal": "Endothelial markers appear within healthy range.",
            "Mild": "Mild endothelial stress; consider vascular health strategies (blood pressure, lipids, activity, diet).",
            "Moderate": "Moderate endothelial dysfunction; intensify vascular risk management.",
            "Severe": "Severe endothelial stress; evaluate for advanced atherosclerotic risk and organ damage.",
        }
        metab_comment_map = {
            "Near optimal": "Metabolic, liver, and insulin-resistance markers are largely reassuring.",
            "Mild": "Mild metabolic risk; reinforce diet, activity, weight management, and sleep.",
            "Moderate": "Moderate metabolic and insulin-resistance burden; structured lifestyle and pharmacologic review advised.",
            "Severe": "Severe metabolic risk; high priority for comprehensive diabetes, NAFLD, and cardiovascular risk management.",
        }

        inflam_comment = inflam_comment_map[inflam_label]
        oxid_comment = oxid_comment_map[oxid_label]
        endo_comment = endo_comment_map[endo_label]
        metab_comment = metab_comment_map[metab_label]

        # ----------------- Display on screen -----------------
        st.subheader("4. Domain Scores")
        d1, d2 = st.columns(2)
        with d1:
            st.write(f"Inflammation score: **{infl['inflam_score']:.1f} / 25** ({inflam_label})")
            st.write(f"Oxidative / Hb-MCV score: **{oxid['oxid_score']:.1f} / 25** ({oxid_label})")
        with d2:
            st.write(f"Endothelial score: **{endo['endo_score']:.1f} / 25** ({endo_label})")
            st.write(f"Metabolic / IR / Liver score: **{metab['metab_score']:.1f} / 25** ({metab_label})")

        st.subheader("5. Overall Score")
        st.write(f"Total CBC + Biochem Metabolic Health Score: **{total_score:.1f} / 100**")
        st.write(f"Overall interpretation: **{label}**")

        st.markdown("---")
        st.subheader("6. Key Indices (summary)")

        cA, cB = st.columns(2)
        with cA:
            st.markdown("**Inflammation (CBC)**")
            if infl["nlr"] is not None:
                st.write(f"NLR: {infl['nlr']:.2f} ({severity_to_text(infl['s_nlr'])})")
            else:
                st.write("NLR: NA")
            if infl["plr"] is not None:
                st.write(f"PLR: {infl['plr']:.1f} ({severity_to_text(infl['s_plr'])})")
            else:
                st.write("PLR: NA")
            if infl["sii"] is not None:
                st.write(f"SII: {infl['sii']:.1f} ({severity_to_text(infl['s_sii'])})")
            else:
                st.write("SII: NA")
            if infl["siri"] is not None:
                st.write(f"SIRI: {infl['siri']:.2f} ({severity_to_text(infl['s_siri'])})")
            else:
                st.write("SIRI: NA")

        with cB:
            st.markdown("**Metabolic / IR / Liver**")
            if metab["tyg"] is not None:
                st.write(f"TyG: {metab['tyg']:.2f} ({severity_to_text(metab['s_tyg'])})")
            else:
                st.write("TyG: NA")
            if metab["mets_ir"] is not None:
                st.write(f"METS-IR: {metab['mets_ir']:.2f} ({severity_to_text(metab['s_mets'])})")
            else:
                st.write("METS-IR: NA")
            if metab["aip"] is not None:
                st.write(f"AIP (mmol/L): {metab['aip']:.3f} ({severity_to_text(metab['s_aip'])})")
            else:
                st.write("AIP: NA")
            if metab["hsi"] is not None:
                st.write(f"HSI: {metab['hsi']:.1f} ({severity_to_text(metab['s_hsi'])})")
            else:
                st.write("HSI: NA")
            if metab["fib4"] is not None:
                st.write(f"FIB-4: {metab['fib4']:.2f} ({severity_to_text(metab['s_fib4'])})")
            else:
                st.write("FIB-4: NA")
            if metab["egdr"] is not None:
                st.write(
                    f"eGDR: {metab['egdr']:.2f} mg/kg/min "
                    f"({severity_to_text(metab['s_egdr'], direction='down')})"
                )
            else:
                st.write("eGDR: NA")

        # ----------------- Build key index lines for PDF -----------------
        key_indices = []

        # Inflammation
        if infl["nlr"] is not None:
            key_indices.append(f"NLR: {infl['nlr']:.2f} ({severity_to_text(infl['s_nlr'])})")
        if infl["plr"] is not None:
            key_indices.append(f"PLR: {infl['plr']:.1f} ({severity_to_text(infl['s_plr'])})")
        if infl["sii"] is not None:
            key_indices.append(f"SII: {infl['sii']:.1f} ({severity_to_text(infl['s_sii'])})")
        if infl["siri"] is not None:
            key_indices.append(f"SIRI: {infl['siri']:.2f} ({severity_to_text(infl['s_siri'])})")

        # Oxidative
        if oxid["rdw"] is not None:
            key_indices.append(f"RDW: {oxid['rdw']:.1f}% ({severity_to_text(oxid['s_rdw'])})")
        if oxid["rpr"] is not None:
            key_indices.append(
                f"RPR (RDW/Platelets): {oxid['rpr']:.3f} ({severity_to_text(oxid['s_rpr'])})"
            )
        if oxid["rar"] is not None:
            key_indices.append(
                f"RAR (RDW/Albumin): {oxid['rar']:.2f} ({severity_to_text(oxid['s_rar'])})"
            )
        if oxid["hbrdw"] is not None:
            key_indices.append(
                f"Hb/RDW: {oxid['hbrdw']:.2f} ({severity_to_text(oxid['s_hbrdw'])})"
            )

        # Endothelial
        if endo["mhr"] is not None:
            key_indices.append(f"MHR: {endo['mhr']:.4f} ({severity_to_text(endo['s_mhr'])})")
        if endo["nhr"] is not None:
            key_indices.append(f"NHR: {endo['nhr']:.4f} ({severity_to_text(endo['s_nhr'])})")

        # Metabolic
        if metab["tyg"] is not None:
            key_indices.append(f"TyG: {metab['tyg']:.2f} ({severity_to_text(metab['s_tyg'])})")
        if metab["mets_ir"] is not None:
            key_indices.append(
                f"METS-IR: {metab['mets_ir']:.2f} ({severity_to_text(metab['s_mets'])})"
            )
        if metab["aip"] is not None:
            key_indices.append(
                f"AIP (mmol/L): {metab['aip']:.3f} ({severity_to_text(metab['s_aip'])})"
            )
        if metab["hsi"] is not None:
            key_indices.append(f"HSI: {metab['hsi']:.1f} ({severity_to_text(metab['s_hsi'])})")
        if metab["fib4"] is not None:
            key_indices.append(
                f"FIB-4: {metab['fib4']:.2f} ({severity_to_text(metab['s_fib4'])})"
            )
        if metab["egdr"] is not None:
            key_indices.append(
                f"eGDR: {metab['egdr']:.2f} mg/kg/min "
                f"({severity_to_text(metab['s_egdr'], direction='down')})"
            )

        # ----------------- Prepare structures for PDF -----------------
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        patient = {
            "name": patient_name,
            "age": age,
            "sex": sex,
            "diabetes": bool(diabetes),
            "date": today_str,
        }

        blocks = {
            "inflam_score": infl["inflam_score"],
            "oxid_score": oxid["oxid_score"],
            "endo_score": endo["endo_score"],
            "metab_score": metab["metab_score"],
            "inflam_label": inflam_label,
            "oxid_label": oxid_label,
            "endo_label": endo_label,
            "metab_label": metab_label,
            "inflam_comment": inflam_comment,
            "oxid_comment": oxid_comment,
            "endo_comment": endo_comment,
            "metab_comment": metab_comment,
            "total_score": total_score,
            "risk_label": label,
            "key_indices": key_indices,
        }

        pdf_bytes = build_pdf(patient, blocks)

        st.markdown("---")
        st.subheader("7. Download Printable PDF")
        st.download_button(
            "Download DiaWell PDF Report",
            data=pdf_bytes,
            file_name=f"DiaWell_Report_{patient_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()
