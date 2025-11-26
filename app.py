import math
from datetime import date

import streamlit as st
from fpdf import FPDF


# ------------- Utility functions ------------- #

def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def classify_index(value, cutoffs):
    """
    Generic classifier.
    cutoffs: list of (upper_limit, label)
    The last label is used if value > last upper_limit.
    """
    if value is None:
        return "NA"
    for limit, label in cutoffs:
        if value <= limit:
            return label
    return cutoffs[-1][1]


def risk_from_total(total_score: float) -> str:
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


# ------------- Core calculations ------------- #

def calculate_indices(inputs):
    """
    inputs: dict with numeric + categorical values.
    Returns:
        indices: dict of index_name -> value
        index_severity: dict of index_name -> label ("Normal", "Mild ↑", etc.)
        domain_scores: dict of domain -> (score_0_25, label)
        total_score: float [0–100]
    """

    # Unpack inputs
    age = safe_float(inputs.get("age"))
    sex = inputs.get("sex", "M")
    diabetes_flag = inputs.get("diabetes", False)

    wbc = safe_float(inputs.get("wbc"))          # x10^9/L
    neut_pct = safe_float(inputs.get("neut_pct"))
    lymph_pct = safe_float(inputs.get("lymph_pct"))
    mono_pct = safe_float(inputs.get("mono_pct"))
    platelets = safe_float(inputs.get("platelets"))  # x10^9/L

    fasting_glu = safe_float(inputs.get("fasting_glu"))  # mg/dL
    tg = safe_float(inputs.get("tg"))                    # mg/dL
    hdl = safe_float(inputs.get("hdl"))                  # mg/dL
    ast = safe_float(inputs.get("ast"))                  # IU/L
    alt = safe_float(inputs.get("alt"))                  # IU/L
    hba1c = safe_float(inputs.get("hba1c"))              # %

    weight = safe_float(inputs.get("weight"))  # kg
    height = safe_float(inputs.get("height"))  # cm
    waist = safe_float(inputs.get("waist"))    # cm
    hip = safe_float(inputs.get("hip"))        # cm
    htn = inputs.get("htn", False)

    bmi = None
    if weight and height:
        bmi = weight / ((height / 100) ** 2)

    whr = None
    if waist and hip:
        whr = waist / hip

    # ---- Inflammatory indices --
