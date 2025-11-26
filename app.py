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

    # Use fixed width to avoid FPDF "not enough space" bug
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
    pdf.multi_cell(
        180,
        5,
        pdf_safe(
            "Disclaimer: This report is for educational and metabolic recovery guidance only and "
            "does not replace clinical judgment or diagnostic workup. Please correlate with the "
            "full clinical context."
        ),
    )

    # Return PDF bytes compatible with Streamlit
    pdf_data = pdf.output(dest="S")
    if isinstance(pdf_data, bytes):
        return pdf_data
    else:
        return pdf_data.encode("latin-1", "ignore")
if __name__ == "__main__":
    main()
