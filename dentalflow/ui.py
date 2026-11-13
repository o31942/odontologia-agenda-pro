"""Identidad visual y formatos de DentalFlow."""
from __future__ import annotations

from html import escape

import streamlit as st

from .services import local_now

PALETTE = {"Programada": "#6B7B91", "Confirmada": "#0E9B87", "En atención": "#DF9B28", "Atendida": "#5F72D7", "Cancelada": "#DF6773", "No asistió": "#AD658D"}


def money(n: int) -> str:
    return f"$ {n:,.0f}".replace(",", ".")


def css() -> None:
    st.markdown('''<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {font-family: 'DM Sans', sans-serif;}
    [data-testid="stAppViewContainer"] {background: #F5F8FB; color: #15263A;}
    .block-container {padding-top:1.65rem; padding-bottom:3rem; max-width: 1470px;}
    [data-testid="stSidebar"] {background: #0E2033;}
    [data-testid="stSidebar"] * {color: #E5F4FA;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {padding-top:.25rem; padding-bottom:.25rem;}
    [data-testid="stSidebar"] div[role="radiogroup"] label {border-radius:10px; padding:10px 12px; transition:.15s;}
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {background: #183D4B;}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {background:#183244;}
    h1,h2,h3,h4 {font-family:'Manrope',sans-serif; letter-spacing:-.04em; color:#15263A;}
    h1 {font-size:2rem!important; font-weight:800!important;}
    h2 {font-size:1.4rem!important; font-weight:800!important;}
    h3 {font-size:1.08rem!important; font-weight:700!important;}
    [data-testid="stMetric"] {background:#FFFFFF;border:1px solid #E5ECF2;box-shadow:0 3px 16px #17354E08;border-radius:16px;padding:1.15rem 1.25rem;}
    [data-testid="stMetricValue"] {font-family:'Manrope',sans-serif;font-weight:800;font-size:2rem;}
    [data-testid="stMetricLabel"] {font-weight:650;color:#69788A;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;border-color:#E6EDF3!important;box-shadow:0 3px 15px #17354E06;background:#fff;}
    .stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"] {background:#0F9D91;border-color:#0F9D91;color:#fff;border-radius:10px;font-weight:700;padding-left:1.2rem;padding-right:1.2rem;}
    .stButton button {border-radius:10px;}
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {border-radius:10px;}
    .df-header {background:linear-gradient(110deg,#102D42 0%,#163F4F 62%,#137C78 140%);color:white;border-radius:20px;padding:28px 32px;margin-bottom:22px;position:relative;overflow:hidden;box-shadow:0 14px 25px #0B30441F;}
    .df-header:after {content:'✦';position:absolute;right:55px;top:-55px;font-size:220px;color:#FFFFFF09;}
    .df-header h1 {font-size:2rem!important;color:#FFF!important;margin:0 0 8px 0;}
    .df-header p {color:#C5DFE3;font-size:1rem;margin:0;}
    .df-eyebrow {font-size:.72rem;letter-spacing:.17em;text-transform:uppercase;color:#84E4D7;font-weight:800;margin-bottom:10px;}
    .df-brand {margin-top:12px;font-family:Manrope;font-weight:800;font-size:26px;color:white;letter-spacing:-1.2px;}
    .df-brand span {color:#39DDC5;}
    .df-side-caption {color:#8BB0BB;font-size:12px;margin-bottom:25px;}
    .df-foot {font-size:.78rem;color:#8DAEBB;margin-top:15px;}
    .df-pill {display:inline-block;font-weight:700;font-size:12px;padding:4px 9px;border-radius:7px;background:#E7F7F5;color:#168578;}
    .df-note {border-left:3px solid #0FA799;background:#EEF9F7;padding:12px 16px;border-radius:6px;color:#35636C;margin:12px 0;}
    .df-day-card {background:#fff;border:1px solid #EBF0F4;border-radius:13px;padding:10px 14px;margin:8px 0;}
    .df-day-card strong {color:#15263A;}
    .df-day-card small {color:#8493A0;}
    .df-muted {color:#758497;font-size:.86rem;}
    .stDataFrame {border:1px solid #E4ECF1; border-radius:12px;}
    </style>''', unsafe_allow_html=True)


def header(title: str, subtitle: str, eyebrow: str = "PLATAFORMA DE GESTIÓN ODONTOLÓGICA") -> None:
    st.markdown(f'<div class="df-header"><div class="df-eyebrow">{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>', unsafe_allow_html=True)


def pill(status: str) -> str:
    color = PALETTE.get(status, "#5B7A86")
    return f'<span style="color:{color};font-weight:800;font-size:12px">● {escape(status)}</span>'


def appointment_tile(a) -> str:
    return (f'<div class="df-day-card"><small>{a.start_at:%I:%M %p} — {a.end_at:%I:%M %p}</small>'
            f'<div><strong>{escape(a.patient.full_name)}</strong> · {escape(a.service.name)}</div>'
            f'<div class="df-muted">{escape(a.professional.name)} &nbsp; {pill(a.status)}</div></div>')
