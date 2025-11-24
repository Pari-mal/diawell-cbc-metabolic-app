
import math
import io
import datetime
import streamlit as st
from fpdf import FPDF

# ------------------ Core calculation helpers ------------------ #

def calc_nlr(neutrophils, lymphocytes):
    if lymphocytes <= 0:
        return None
    return neutrophils / lymphocytes

def calc_plr(platelets, lymphocytes):
    if lymphocytes <= 0:
        return None
    return platelets / lymphocytes

def calc_tyg(glucose_mgdl, tg_mgdl):
    # TyG = ln( (TG * Glucose) / 2 )
    if glucose_mgdl <= 0 or tg_mgdl <= 0:
        return None
    return math.log((tg_mgdl * glucose_mgdl) / 2.0)

def calc_mets_ir(glucose_mgdl, tg_mgdl, hdl_mgdl, bmi):
    # Simplified METS-IR (same as used in your Excel)
    if glucose_mgdl <= 0 or tg_mgdl <= 0 or hdl_mgdl <= 0 or bmi <= 0:
        return None
    return math.log(2 * glucose_mgdl + tg_mgdl) * bmi / math.log(hdl_mgdl)

def calc_egdr(waist_cm, hba1c, htn_flag):
    # eGDR (mg/kg/min):
    # 21.158 − 0.09 × Waist − 3.407 × HTN − 0.551 × HbA1c
    if waist_cm <= 0 or hba1c <= 0:
        return None
    return 21.158 - 0.09 * waist_cm - 3.407 * htn_flag - 0.551 * hba1c

def map_index_to_severity(value, low, mild, moderate):
    """Map continuous values into 0–3 severity band."""
    if value is None:
        return None
    if value <= low:
        return 0
    elif value <= mild:
        return 1
    elif value <= moderate:
        return 2
    else:
        return 3

def risk_label_from_score(score_0_100):
    if score_0_100 is None:
        return "No score"
    if score_0_100 < 25:
        return "Low risk"
    elif score_0_100 < 50:
        return "Mild risk"
    elif score_0_100 < 75:
        return "Moderate risk"
    else:
        return "High risk – intensive optimization needed"

# ------------------ PDF generation ------------------ #

class ReportPDF(FPDF):
    def header(self):
        # Title at top of each page
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "DiaWell C.O.R.E. Foundation – Metabolic Health Report", ln=True, align="C")
        self.ln(2)

    def footer(self):
        # Page number at bottom
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        page_text = f"Page {self.page_no()}"
        self.cell(0, 10, page_text, align="C")

def create_pdf_report(patient_info, results):
    """
    patient_info: dict with patient_name, age, sex, date, diabetes
    results: dict with calculated indices & global score
    Returns: bytes of PDF.
    """
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Patient block
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Patient Name: {patient_info['name']}", ln=True)
    pdf.cell(0, 8, f"Age / Sex: {patient_info['age']} years / {patient_info['sex']}", ln=True)
    pdf.cell(0, 8, f"Date of Examination: {patient_info['date']}", ln=True)
    diabetes_text = "Yes (diabetes present)" if patient_info["diabetes"] else "No / Not known"
    pdf.cell(0, 8, f"Diabetes: {diabetes_text}", ln=True)
    pdf.ln(4)

    # Global score
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Overall Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Total Score (0–100): {results['total_score']:.1f}", ln=True)
    pdf.cell(0, 8, f"Risk Category: {results['risk_label']}", ln=True)
    pdf.ln(4)

    # Domain overview
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Domain-wise Overview", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Inflammation (CBC-based): {results['inflammation_score']:.1f} / 25", ln=True)
    pdf.cell(0, 8, f"Oxidative / Hb–MCV / Energy: {results['oxidative_score']:.1f} / 25", ln=True)
    pdf.cell(0, 8, f"Endothelial / Vascular: {results['endothelial_score']:.1f} / 25", ln=True)
    pdf.cell(0, 8, f"Metabolic / IR / Liver / CV: {results['metabolic_score']:.1f} / 25", ln=True)
    pdf.ln(4)

    # Detailed indices
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Key Indices", ln=True)
    pdf.set_font("Helvetica", "", 11)

    # Inflammation
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Inflammation (CBC-based):", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"NLR: {results['nlr_text']}", ln=True)
    pdf.cell(0, 6, f"PLR: {results['plr_text']}", ln=True)

    # Metabolic / IR / liver
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Metabolic / Insulin Resistance / CV:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"TyG: {results['tyg_text']}", ln=True)
    pdf.cell(0, 6, f"METS-IR: {results['mets_ir_text']}", ln=True)
    pdf.cell(0, 6, f"eGDR: {results['egdr_text']}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        "Disclaimer: This report is for educational and lifestyle guidance purposes only and "
        "does not replace clinical judgment, diagnostic workup, or medical advice. "
        "Please correlate with full clinical context and investigations."
    )

    # Export as bytes
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return pdf_bytes

# ------------------ Streamlit App ------------------ #

def main():
    st.set_page_config(
        page_title="DiaWell CBC + Metabolic Health App",
        layout="centered"
    )

    st.title("DiaWell C.O.R.E. – CBC + Biochemistry Metabolic Health (Demo)")
    st.caption("Example Streamlit app ready for GitHub + Streamlit Cloud + PDF export.")

    # ---- Patient info ----
    st.header("1. Patient Information")
    col1, col2, col3 = st.columns(3)
    with col1:
        patient_name = st.text_input("Patient Name", value="Test Patient")
    with col2:
        age = st.number_input("Age (years)", min_value=0, max_value=120, value=40)
    with col3:
        sex = st.selectbox("Sex", ["M", "F"])

    diabetes_flag = st.selectbox("Diabetes", ["No / Not known (0)", "Yes (1)"])
    diabetes = 1 if "Yes" in diabetes_flag else 0

    # ---- CBC ----
    st.header("2. CBC Inputs")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        neut = st.number_input("Neutrophils (x10⁹/L)", min_value=0.0, value=5.0)
    with c2:
        lymph = st.number_input("Lymphocytes (x10⁹/L)", min_value=0.0, value=2.0)
    with c3:
        mono = st.number_input("Monocytes (x10⁹/L)", min_value=0.0, value=0.5)
    with c4:
        platelets = st.number_input("Platelets (x10⁹/L)", min_value=0.0, value=200.0)

    # ---- Biochemistry / metabolic ----
    st.header("3. Metabolic / Biochemistry Inputs")
    m1, m2, m3 = st.columns(3)
    with m1:
        glu = st.number_input("Glucose (mg/dL)", min_value=0.0, value=120.0)
        tg = st.number_input("Triglycerides (mg/dL)", min_value=0.0, value=200.0)
        hdl = st.number_input("HDL (mg/dL)", min_value=0.0, value=33.0)
    with m2:
        hba1c = st.number_input("HbA1c (%)", min_value=0.0, max_value=20.0, value=6.5)
        bmi = st.number_input("BMI (kg/m²)", min_value=10.0, max_value=60.0, value=26.0)
        waist = st.number_input("Waist circumference (cm)", min_value=40.0, max_value=200.0, value=90.0)
    with m3:
        htn_flag = st.selectbox("Hypertension", ["No (0)", "Yes (1)"])
    htn = 1 if "Yes" in htn_flag else 0

    if st.button("Calculate & Generate Report"):
        # ---- Calculate indices ----
        nlr = calc_nlr(neut, lymph)
        plr = calc_plr(platelets, lymph)
        tyg = calc_tyg(glu, tg)
        mets_ir = calc_mets_ir(glu, tg, hdl, bmi)
        egdr = calc_egdr(waist, hba1c, htn)

        # Simple domain scores (demo; you’ll plug in your full 4-domain logic if you want)
        domain_inflammation = 0
        domain_oxidative = 0
        domain_endothelial = 0
        domain_metabolic = 0
        domain_count = 0

        # Inflammation domain example (NLR based)
        if nlr is not None:
            sev_nlr = map_index_to_severity(nlr, low=2, mild=3, moderate=5)  # 0–3
            domain_inflammation = (sev_nlr / 3) * 25
            domain_count += 1

        # Oxidative domain placeholder – you can add RDW/Hb/MCV logic later
        domain_oxidative = 12.5  # neutral mid for demo
        domain_count += 1

        # Endothelial domain placeholder – you can add MHR/NHR later
        domain_endothelial = 12.5
        domain_count += 1

        # Metabolic domain from TyG, METS-IR, eGDR
        metab_severities = []
        if tyg is not None:
            tyg_sev = map_index_to_severity(tyg, low=8.5, mild=8.9, moderate=9.5)
            if tyg_sev is not None:
                metab_severities.append(tyg_sev)
        if mets_ir is not None:
            mets_sev = map_index_to_severity(mets_ir, low=35, mild=40, moderate=45)
            if mets_sev is not None:
                metab_severities.append(mets_sev)
        if egdr is not None:
            # invert (higher is better)
            if egdr > 8:
                egdr_sev = 0
            elif egdr > 6:
                egdr_sev = 1
            elif egdr > 4:
                egdr_sev = 2
            else:
                egdr_sev = 3
            metab_severities.append(egdr_sev)

        if metab_severities:
            avg_metab_sev = sum(metab_severities) / len(metab_severities)
            domain_metabolic = (avg_metab_sev / 3) * 25
            domain_count += 1

        # Total score (simple mean of four domain scores)
        if domain_count > 0:
            total_score = (domain_inflammation + domain_oxidative +
                           domain_endothelial + domain_metabolic)
        else:
            total_score = None

        risk_label = risk_label_from_score(total_score)

        # ---- Show results on screen ----
        st.subheader("4. Results (Demo)")
        cA, cB = st.columns(2)

        with cA:
            st.markdown("**Inflammation (CBC)**")
            st.write(f"NLR: {nlr:.2f}" if nlr is not None else "NLR: NA")
            st.write(f"PLR: {plr:.1f}" if plr is not None else "PLR: NA")
            st.write(f"Inflammation domain score: {domain_inflammation:.1f} / 25")

        with cB:
            st.markdown("**Metabolic / IR / Liver / CV**")
            if tyg is not None:
                st.write(f"TyG: {tyg:.2f}")
            else:
                st.write("TyG: NA")
            if mets_ir is not None:
                st.write(f"METS-IR: {mets_ir:.2f}")
            else:
                st.write("METS-IR: NA")
            if egdr is not None:
                st.write(f"eGDR: {egdr:.2f} mg/kg/min")
            else:
                st.write("eGDR: NA")
            st.write(f"Metabolic domain score: {domain_metabolic:.1f} / 25")

        st.markdown("---")
        st.subheader("5. Overall Risk (Demo)")
        if total_score is not None:
            st.write(f"Total Score (0–100): **{total_score:.1f}**")
            st.write(f"Risk Category: **{risk_label}**")
        else:
            st.write("Not enough data to compute total score.")

        # ---- Prepare data for PDF ----
        today_str = datetime.date.today().strftime("%d-%m-%Y")
        patient_info = {
            "name": patient_name,
            "age": age,
            "sex": sex,
            "date": today_str,
            "diabetes": bool(diabetes),
        }

        results = {
            "total_score": total_score if total_score is not None else 0.0,
            "risk_label": risk_label,
            "inflammation_score": domain_inflammation,
            "oxidative_score": domain_oxidative,
            "endothelial_score": domain_endothelial,
            "metabolic_score": domain_metabolic,
            "nlr_text": f"{nlr:.2f}" if nlr is not None else "NA",
            "plr_text": f"{plr:.1f}" if plr is not None else "NA",
            "tyg_text": f"{tyg:.2f}" if tyg is not None else "NA",
            "mets_ir_text": f"{mets_ir:.2f}" if mets_ir is not None else "NA",
            "egdr_text": f"{egdr:.2f} mg/kg/min" if egdr is not None else "NA",
        }

        pdf_bytes = create_pdf_report(patient_info, results)

        st.markdown("---")
        st.subheader("6. Download PDF Report")
        st.download_button(
            label="Download PDF report",
            data=pdf_bytes,
            file_name=f"DiaWell_Report_{patient_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
        )

        st.info("You can print this PDF and give it to the patient as a summary sheet.")

    st.caption(
        "Note: This is a demo app. You can replace the simple scoring logic with your full "
        "CBC + biochemistry 4-domain scoring that you developed in Excel."
    )

if __name__ == "__main__":
    main()
