"""DentalFlow — gestión odontológica y agenda operativa (hora de Colombia)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from sqlalchemy import select
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_calendar import calendar

from dentalflow.db import AppointmentEvent, Patient, Professional, Service, initialize, session_factory
from dentalflow.security import config, database_url, is_demo, verify_credentials
from dentalflow.services import (
    BusinessError, STATUSES, add_block, change_status, create_appointment, create_patient,
    create_professional, create_service, delete_block, free_slots, get_workdays,
    list_appointments, list_blocks, list_patients, list_professionals, list_services,
    local_now, reschedule_appointment, set_workday, update_patient,
)
from dentalflow.ui import PALETTE, appointment_tile, css, header, money

st.set_page_config(page_title="DentalFlow | Agenda clínica", page_icon="🦷", layout="wide", initial_sidebar_state="expanded")
css()

CLINIC = config("CLINIC_NAME", "DentalFlow Clínica")
NOW = local_now()
TODAY = NOW.date()
DEMO = is_demo()
DB_URL = database_url()


def friendly_error(exc: Exception):
    if isinstance(exc, BusinessError):
        st.error(str(exc))
    else:
        st.error("No fue posible completar la operación. Revisa la conexión y vuelve a intentarlo.")


def done(text: str):
    st.toast(text, icon="✅")
    st.rerun()


def login():
    left, mid, right = st.columns([1, 1.1, 1])
    with mid:
        st.markdown('<div style="height:48px"></div>', unsafe_allow_html=True)
        st.markdown('<div style="text-align:center;font-size:48px">🦷</div>', unsafe_allow_html=True)
        st.markdown('<h1 style="text-align:center;margin-bottom:0">DentalFlow</h1>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center;color:#758497">La agenda inteligente de tu clínica dental</p>', unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("Bienvenido de nuevo")
            st.caption("Ingresa con tu cuenta administrativa para consultar y gestionar pacientes.")
            if not config("ADMIN_EMAIL") or not config("ADMIN_PASSWORD_HASH"):
                st.warning("Configura ADMIN_EMAIL, ADMIN_PASSWORD_HASH y DATABASE_URL en los secretos de la aplicación.")
                st.code("python scripts/hash_password.py", language="bash")
                st.stop()
            with st.form("login_form"):
                email = st.text_input("Correo electrónico", placeholder="admin@clinica.com")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Ingresar a mi clínica", type="primary", use_container_width=True)
            if submitted:
                tries = st.session_state.get("login_tries", 0)
                if tries >= 8:
                    st.error("Límite de intentos de esta sesión. Cierra la sesión del navegador y contacta al administrador.")
                elif verify_credentials(email, password):
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = email.strip().lower()
                    st.session_state["login_tries"] = 0
                    st.rerun()
                else:
                    st.session_state["login_tries"] = tries + 1
                    st.error("Correo o contraseña incorrectos.")
        st.caption("🔒 Acceso privado · Datos almacenados fuera de GitHub")


if not DB_URL:
    st.error("**Falta configurar la base de datos.** Define DATABASE_URL en los secretos de Streamlit. Para explorar sin datos reales configura DEMO_MODE = 'true'.")
    st.stop()
if not DEMO and DB_URL.startswith("sqlite") and config("APP_ENV", "production").lower() == "production":
    st.error("**Producción requiere PostgreSQL.** SQLite no garantiza persistencia en hospedajes efímeros; configura DATABASE_URL con PostgreSQL.")
    st.stop()

if not DEMO and not st.session_state.get("logged_in", False):
    login()
    st.stop()

try:
    initialize(DB_URL)
except Exception:
    st.error("No se pudo conectar con la base de datos. Verifica DATABASE_URL y su acceso desde el servidor.")
    st.stop()


with session_factory(DB_URL)() as db:
    patients = list_patients(db)
    professionals = list_professionals(db)
    active_professionals = [p for p in professionals if p.active]
    services = list_services(db)
    active_services = [s for s in services if s.active]
    patient_dict = {p.id: p for p in patients if p.active}
    prof_dict = {p.id: p for p in active_professionals}
    service_dict = {s.id: s for s in active_services}

    @st.dialog("Nuevo paciente", width="large")
    def patient_dialog():
        st.caption("Registro administrativo de pacientes · Los campos con * son obligatorios.")
        with st.form("patient_form"):
            a, b = st.columns(2)
            first_name = a.text_input("Nombres *", max_chars=100)
            last_name = b.text_input("Apellidos *", max_chars=100)
            c, d = st.columns([1, 2])
            doc_type = c.selectbox("Tipo de documento", ["CC", "TI", "CE", "PA", "PEP", "Otro"])
            doc = d.text_input("Número de documento *", max_chars=35)
            phone, email = st.columns(2)
            phone_value = phone.text_input("Celular / Teléfono *", max_chars=30)
            email_value = email.text_input("Correo electrónico", max_chars=200)
            has_birth = st.checkbox("Registrar fecha de nacimiento")
            birth = st.date_input("Fecha de nacimiento", value=date(1990, 1, 1), max_value=TODAY) if has_birth else None
            notes = st.text_area("Observaciones administrativas", placeholder="Preferencias de contacto, información logística…", max_chars=3000)
            submit = st.form_submit_button("Guardar paciente", type="primary", use_container_width=True)
        if submit:
            try:
                create_patient(db, first_name=first_name, last_name=last_name, document_type=doc_type,
                               document_number=doc, phone=phone_value, email=email_value, birth_date=birth, notes=notes)
                done("Paciente registrado correctamente")
            except Exception as exc:
                friendly_error(exc)

    @st.dialog("Editar paciente", width="large")
    def patient_edit_dialog(patient_id: str):
        p = db.get(Patient, patient_id)
        if not p:
            st.error("Paciente no encontrado")
            return
        st.caption(f"{p.document_type} · {p.document_number} | El documento no se modifica desde esta pantalla")
        with st.form(f"edit_patient_{patient_id}"):
            a, b = st.columns(2)
            first = a.text_input("Nombres", p.first_name)
            last = b.text_input("Apellidos", p.last_name)
            a, b = st.columns(2)
            phone = a.text_input("Teléfono", p.phone)
            email = b.text_input("Correo electrónico", p.email or "")
            notes = st.text_area("Observaciones administrativas", p.notes or "")
            submit = st.form_submit_button("Guardar cambios", type="primary")
        if submit:
            try:
                update_patient(db, patient_id, first_name=first, last_name=last, phone=phone, email=email, notes=notes)
                done("Información del paciente actualizada")
            except Exception as exc:
                friendly_error(exc)

    @st.dialog("Agendar nueva cita", width="large")
    def booking_dialog(prefilled_date: date | None = None, prefilled_time: time | None = None):
        if not patient_dict:
            st.warning("Primero registra un paciente desde la sección Pacientes.")
            if st.button("Cerrar"):
                st.rerun()
            return
        if not active_professionals:
            st.warning("Primero registra un odontólogo desde Profesionales.")
            return
        if not active_services:
            st.warning("Necesitas al menos un procedimiento activo.")
            return
        st.caption("Selección guiada · Solo se mostrarán los horarios realmente disponibles.")
        a, b = st.columns(2)
        pat_id = a.selectbox("Paciente *", list(patient_dict), format_func=lambda x: patient_dict[x].full_name)
        prof_id = b.selectbox("Odontólogo *", list(prof_dict), format_func=lambda x: prof_dict[x].name)
        service_id = st.selectbox("Procedimiento *", list(service_dict),
                                  format_func=lambda x: f"{service_dict[x].name} · {service_dict[x].duration_min} min · {money(service_dict[x].price_cop)}")
        a, b = st.columns(2)
        target_day = a.date_input("Fecha *", value=max(TODAY, prefilled_date or TODAY), min_value=TODAY,
                                  max_value=TODAY + timedelta(days=365), key="new_appointment_date")
        available = free_slots(db, prof_id, service_id, target_day)
        selected = None
        if available:
            labels = {t: t.strftime("%I:%M %p") for t in available}
            index = next((i for i, t in enumerate(available) if prefilled_time and t.time() == prefilled_time), 0)
            selected = b.selectbox("Hora disponible *", available, index=index, format_func=lambda t: labels[t])
        else:
            b.info("Sin espacios disponibles para esta combinación.")
        reason = st.text_input("Motivo de la cita", placeholder="Ej. Consulta inicial", max_chars=250)
        notes = st.text_area("Nota interna opcional", max_chars=3000)
        if selected:
            ends = selected + timedelta(minutes=service_dict[service_id].duration_min)
            st.markdown(f'<div class="df-note"><strong>Resumen de la reserva</strong><br>{target_day:%d/%m/%Y} · {selected:%I:%M %p} a {ends:%I:%M %p} · {escape(prof_dict[prof_id].name)}</div>', unsafe_allow_html=True)
        if st.button("Confirmar agendamiento", type="primary", use_container_width=True, disabled=selected is None):
            try:
                create_appointment(db, patient_id=pat_id, professional_id=prof_id, service_id=service_id,
                                   starts=selected, reason=reason, notes=notes,
                                   created_by=st.session_state.get("user_email", "Modo demostración"))
                done("¡Cita agendada! El horario ya está reservado")
            except Exception as exc:
                friendly_error(exc)

    @st.dialog("Gestionar cita", width="large")
    def appointment_dialog(appointment_id: str):
        a = db.get(Appointment, appointment_id)
        if not a:
            st.warning("No se encontró la cita seleccionada")
            return
        st.subheader(a.patient.full_name)
        st.caption(f"{a.service.name} · {a.professional.name}")
        st.markdown(f"**{a.start_at:%d/%m/%Y}** · {a.start_at:%I:%M %p} – {a.end_at:%I:%M %p}")
        if a.reason:
            st.write(f"**Motivo:** {a.reason}")
        st.divider()
        new_state = st.selectbox("Estado de la cita", STATUSES, index=STATUSES.index(a.status))
        if st.button("Actualizar estado", type="primary", disabled=new_state == a.status):
            try:
                change_status(db, a.id, new_state, actor=st.session_state.get("user_email", "Demo"))
                done("Estado de la cita actualizado")
            except Exception as exc:
                friendly_error(exc)
        if a.status not in ("Cancelada", "Atendida", "No asistió"):
            with st.expander("Reprogramar esta cita", expanded=False):
                if not prof_dict or not service_dict:
                    st.warning("Activa al menos un profesional y un servicio antes de reprogramar.")
                    return
                new_day = st.date_input("Nueva fecha", value=max(TODAY, a.start_at.date()), min_value=TODAY,
                                        max_value=TODAY + timedelta(days=365), key=f"reschedule_day_{a.id}")
                new_prof = st.selectbox("Odontólogo", list(prof_dict),
                                        index=list(prof_dict).index(a.professional_id) if a.professional_id in prof_dict else 0,
                                        format_func=lambda x: prof_dict[x].name, key=f"reschedule_prof_{a.id}")
                new_svc = st.selectbox("Procedimiento", list(service_dict),
                                       index=list(service_dict).index(a.service_id) if a.service_id in service_dict else 0,
                                       format_func=lambda x: service_dict[x].name, key=f"reschedule_service_{a.id}")
                slots = free_slots(db, new_prof, new_svc, new_day)
                original = a.start_at
                if new_prof == a.professional_id and new_day == original.date() and a.status in ("Programada", "Confirmada", "En atención"):
                    if original >= NOW and original not in slots:
                        slots.insert(0, original)
                    slots.sort()
                if slots:
                    slot = st.selectbox("Nueva hora", slots, format_func=lambda t: t.strftime("%I:%M %p"))
                    if st.button("Guardar reprogramación", type="primary"):
                        try:
                            reschedule_appointment(db, a.id, slot, professional_id=new_prof,
                                                   service_id=new_svc, actor=st.session_state.get("user_email", "Demo"))
                            done("Cita reprogramada correctamente")
                        except Exception as exc:
                            friendly_error(exc)
                else:
                    st.warning("No hay espacios disponibles en esta fecha.")
        st.caption("La cancelación libera el horario inmediatamente.")
        with st.expander("Trazabilidad de esta cita"):
            history = db.scalars(select(AppointmentEvent).where(
                AppointmentEvent.appointment_id == a.id).order_by(AppointmentEvent.occurred_at.desc())).all()
            for e in history:
                st.markdown(f"**{e.action}** · {e.detail}  \n {e.occurred_at:%d/%m/%Y %H:%M} · {e.actor}")

    def appointment_frame(items: list[Appointment]) -> pd.DataFrame:
        return pd.DataFrame([{
            "ID": a.id, "Fecha": a.start_at.strftime("%d/%m/%Y"), "Inicio": a.start_at.strftime("%I:%M %p"),
            "Fin": a.end_at.strftime("%I:%M %p"), "Paciente": a.patient.full_name,
            "Odontólogo": a.professional.name, "Servicio": a.service.name,
            "Estado": a.status, "Teléfono": a.patient.phone,
        } for a in items])

    def section_bar(title: str, description: str = ""):
        st.markdown(f"### {title}")
        if description:
            st.caption(description)

    def display_cards(items: list[Appointment], max_count: int = 8):
        if not items:
            st.info("No hay citas para los filtros seleccionados.")
        else:
            for a in items[:max_count]:
                st.markdown(appointment_tile(a), unsafe_allow_html=True)

    def overview():
        header("Tu clínica, bajo control", f"{NOW:%d/%m/%Y} · Visión general de pacientes, citas y actividad de {CLINIC}.")
        items_today = list_appointments(db, TODAY, TODAY)
        month_start = TODAY.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        items_month = list_appointments(db, month_start, next_month - timedelta(days=1))
        active_today = [a for a in items_today if a.status != "Cancelada"]
        confirmed = sum(a.status == "Confirmada" for a in items_today)
        completed = sum(a.status == "Atendida" for a in items_today)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Citas de hoy", len(active_today), border=False)
        col2.metric("Confirmadas", confirmed, border=False)
        col3.metric("Atendidas hoy", completed, border=False)
        col4.metric("Pacientes registrados", len(patients), border=False)
        st.write("")
        c1, c2 = st.columns([1.45, 1], gap="large")
        with c1:
            with st.container(border=True):
                section_bar("Próximas citas", "Los siguientes turnos programados para hoy.")
                upcoming = [a for a in items_today if a.end_at >= NOW and a.status not in ("Cancelada", "Atendida", "No asistió")]
                display_cards(upcoming, max_count=6)
                if st.button("Ver agenda completa", use_container_width=True):
                    st.session_state["nav"] = "Agenda"
                    st.session_state["sidebar_nav"] = "Agenda"
                    st.rerun()
        with c2:
            with st.container(border=True):
                section_bar("Distribución del mes", "Reservas por estado · incluye citas del periodo.")
                totals = {s: sum(a.status == s for a in items_month) for s in STATUSES}
                if sum(totals.values()):
                    fig = go.Figure(go.Pie(labels=list(totals), values=list(totals.values()), hole=.72,
                                           marker=dict(colors=[PALETTE[k] for k in totals]),
                                           textinfo="none", hovertemplate="%{label}: %{value}<extra></extra>"))
                    fig.update_layout(height=275, margin=dict(t=10,b=10,l=0,r=0),
                                      showlegend=True, legend=dict(orientation="h", y=-.08),
                                      paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Arial"),
                                      annotations=[dict(text=str(sum(totals.values())), x=.5,y=.52,
                                                        font=dict(size=34,color="#15263A"), showarrow=False),
                                                   dict(text="CITAS",x=.5,y=.40,font=dict(size=11,color="#83929F"),showarrow=False)])
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                else:
                    st.info("Agenda una primera cita para ver la distribución.")
        with st.container(border=True):
            section_bar("Actividad de los próximos 7 días", "Citas programadas por fecha, sin cancelaciones.")
            next_week = list_appointments(db, TODAY, TODAY + timedelta(days=6))
            counts = {TODAY + timedelta(days=i): 0 for i in range(7)}
            for a in next_week:
                if a.status != "Cancelada":
                    counts[a.start_at.date()] += 1
            df = pd.DataFrame({"Día": [d.strftime("%d/%m") for d in counts], "Citas": list(counts.values())})
            st.bar_chart(df.set_index("Día"), color="#0F9D91", height=205)

    def agenda():
        header("Agenda odontológica", "Visualiza disponibilidad, organiza turnos y acompaña el recorrido de cada paciente.", "GESTIÓN DE CITAS")
        left, right = st.columns([4, 1])
        with left:
            st.caption("Zona horaria: America/Bogota · Intervalos de 15 minutos · Los horarios ocupados no pueden duplicarse.")
        with right:
            if st.button("＋  Nueva cita", type="primary", use_container_width=True):
                booking_dialog()
        a, b = st.columns([1, 1])
        view = a.segmented_control("Vista", ["Calendario", "Listado"], default="Calendario")
        prof_filter = b.selectbox("Filtrar por profesional", ["Todos"] + list(prof_dict),
                                  format_func=lambda p: "Todos los profesionales" if p == "Todos" else prof_dict[p].name)
        filter_id = prof_filter if prof_filter != "Todos" else None
        if view == "Calendario":
            start_day = TODAY - timedelta(days=45)
            end_day = TODAY + timedelta(days=120)
            appointments = list_appointments(db, start_day, end_day, filter_id)
            blocks = [x for x in list_blocks(db, start_day, end_day) if not filter_id or x.professional_id == filter_id]
            events = []
            for a in appointments:
                color = PALETTE.get(a.status, "#0F9D91")
                if a.status == "Cancelada":
                    continue
                events.append({"id": a.id, "title": f"{a.patient.full_name} · {a.service.name}",
                               "start": a.start_at.isoformat(), "end": a.end_at.isoformat(),
                               "backgroundColor": color, "borderColor": color,
                               "extendedProps": {"professional": a.professional.name, "status": a.status}})
            for block in blocks:
                events.append({"id": f"block-{block.id}", "title": f"⛔ {block.reason}",
                               "start": block.start_at.isoformat(), "end": block.end_at.isoformat(),
                               "backgroundColor": "#96A6B2", "borderColor": "#96A6B2"})
            settings = {
                "initialView": "timeGridWeek", "locale": "es", "timeZone": "America/Bogota",
                "initialDate": TODAY.isoformat(), "nowIndicator": True, "height": "auto",
                "editable": False, "selectable": True, "allDaySlot": False,
                "slotMinTime": "07:00:00", "slotMaxTime": "20:00:00",
                "slotDuration": "00:15:00", "slotLabelInterval": "01:00:00",
                "weekends": True, "expandRows": True, "dayMaxEvents": True,
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": "timeGridDay,timeGridWeek,dayGridMonth"},
                "buttonText": {"today":"Hoy", "month":"Mes", "week":"Semana", "day":"Día"},
            }
            response = calendar(events=events, options=settings, key=f"agenda-calendar-{filter_id}",
                                custom_css="""
                                  .fc {font-family:'DM Sans', sans-serif;color:#253E50}
                                  .fc .fc-toolbar-title {font-weight:800;font-size:1.22rem}
                                  .fc .fc-button-primary {background:#143D49;border-color:#143D49;border-radius:8px}
                                  .fc .fc-button-primary:not(:disabled).fc-button-active {background:#0F9D91;border-color:#0F9D91}
                                  .fc .fc-event {border-radius:5px;padding:2px 5px;font-weight:600;font-size:11px}
                                  .fc .fc-timegrid-now-indicator-line {border-color:#EA746F}
                                  .fc-theme-standard td,.fc-theme-standard th {border-color:#E9EDF3}
                                  """)
            if response and response.get("eventClick"):
                event = response["eventClick"].get("event", {})
                target_id = event.get("id", "")
                if target_id and not target_id.startswith("block-"):
                    appointment_dialog(target_id)
            elif response and response.get("select"):
                selection = response["select"]
                try:
                    chosen = datetime.fromisoformat(selection["start"].replace("Z", "+00:00"))
                    if chosen.tzinfo:
                        from zoneinfo import ZoneInfo
                        chosen = chosen.astimezone(ZoneInfo("America/Bogota")).replace(tzinfo=None)
                    booking_dialog(chosen.date(), chosen.time())
                except (ValueError, KeyError):
                    pass
            st.caption("Haz clic en una cita para gestionarla. Selecciona un espacio libre para abrir el agendamiento.")
        else:
            a, b, c = st.columns(3)
            date_from = a.date_input("Desde", value=TODAY, key="filter_from")
            date_to = b.date_input("Hasta", value=TODAY + timedelta(days=14), key="filter_to")
            status = c.selectbox("Estado", ["Todos"] + list(STATUSES))
            if date_to < date_from:
                st.warning("La fecha final no puede ser anterior a la inicial.")
                return
            items = list_appointments(db, date_from, date_to, filter_id)
            if status != "Todos":
                items = [a for a in items if a.status == status]
            if items:
                df = appointment_frame(items)
                st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True,
                             column_config={"Paciente": st.column_config.TextColumn("Paciente", width="medium")})
                selected = st.selectbox("Selecciona una cita para gestionar", [a.id for a in items],
                                        format_func=lambda i: next(f"{a.start_at:%d/%m %I:%M %p} · {a.patient.full_name} · {a.status}" for a in items if a.id == i))
                if st.button("Abrir cita seleccionada", type="primary"):
                    appointment_dialog(selected)
                st.download_button("Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"agenda_{date_from:%Y%m%d}_{date_to:%Y%m%d}.csv", mime="text/csv")
            else:
                st.info("Sin citas para estos filtros.")

    def patients_page():
        header("Directorio de pacientes", "Consulta, registra y mantén organizada tu base de pacientes.", "GESTIÓN DE PACIENTES")
        a, b = st.columns([4, 1])
        search = a.text_input("Buscar pacientes", placeholder="Nombre, apellido, documento o teléfono", label_visibility="collapsed")
        if b.button("＋  Nuevo paciente", type="primary", use_container_width=True):
            patient_dialog()
        lower = search.lower().strip()
        found = [p for p in patients if not lower or lower in " ".join([p.full_name, p.document_number, p.phone, p.email or ""]).lower()]
        a, b, c = st.columns(3)
        a.metric("Pacientes registrados", len(patients))
        b.metric("Activos", sum(p.active for p in patients))
        c.metric("Resultados de búsqueda", len(found))
        st.write("")
        if found:
            df = pd.DataFrame([{"Nombre completo":p.full_name, "Documento":f"{p.document_type} {p.document_number}",
                                "Teléfono":p.phone, "Correo":p.email or "—", "Estado":"Activo" if p.active else "Inactivo"}
                                for p in found])
            st.dataframe(df, use_container_width=True, hide_index=True)
            selected_patient = st.selectbox("Editar perfil de paciente", [p.id for p in found],
                                            format_func=lambda i: next(p.full_name for p in found if p.id == i))
            if st.button("Ver / editar perfil"):
                patient_edit_dialog(selected_patient)
        else:
            st.info("No hay pacientes que coincidan con la búsqueda.")
        st.caption("Solo se almacenan datos administrativos para agendamiento. La historia clínica requiere un módulo y controles específicos.")

    def professionals_page():
        header("Equipo odontológico", "Organiza especialistas y bloquea espacios en su agenda.", "GESTIÓN DE PROFESIONALES")
        with st.container(border=True):
            section_bar("Odontólogos y especialistas")
            if professionals:
                st.dataframe(pd.DataFrame([{"Profesional": p.name, "Especialidad":p.specialty,
                                            "Estado":"Activo" if p.active else "Inactivo"} for p in professionals]),
                             use_container_width=True, hide_index=True)
            else:
                st.info("Registra tu primer profesional para habilitar la agenda.")
            with st.expander("＋ Registrar nuevo profesional"):
                with st.form("new_professional"):
                    a, b, c = st.columns([2, 2, 1])
                    name = a.text_input("Nombre completo")
                    specialty = b.text_input("Especialidad", value="Odontología general")
                    color = c.color_picker("Color en la agenda", value="#14B8A6")
                    if st.form_submit_button("Guardar profesional", type="primary"):
                        try:
                            create_professional(db, name, specialty, color)
                            done("Profesional añadido")
                        except Exception as exc:
                            friendly_error(exc)
            if professionals:
                with st.expander("Modificar estado del profesional"):
                    person_id = st.selectbox("Seleccionar profesional", [p.id for p in professionals],
                                             format_func=lambda i: next(p.name for p in professionals if p.id == i))
                    p = db.get(Professional, person_id)
                    enabled = st.checkbox("Habilitado para nuevas citas", value=p.active, key=f"professional_enabled_{person_id}")
                    if st.button("Aplicar cambio", disabled=enabled == p.active):
                        p.active = enabled
                        db.commit()
                        done("Estado del profesional actualizado")
        st.write("")
        with st.container(border=True):
            section_bar("Bloqueos de agenda", "Vacaciones, permisos, reuniones o indisponibilidad.")
            if active_professionals:
                with st.form("block_schedule"):
                    a, b = st.columns(2)
                    prof_id = a.selectbox("Odontólogo", [p.id for p in active_professionals],
                                         format_func=lambda i: next(p.name for p in active_professionals if p.id == i))
                    day = b.date_input("Fecha del bloqueo", value=TODAY, min_value=TODAY)
                    a, b, c = st.columns(3)
                    start = a.time_input("Inicio", value=time(9, 0), step=900)
                    end = b.time_input("Fin", value=time(10, 0), step=900)
                    reason = c.text_input("Motivo", value="No disponible")
                    if st.form_submit_button("Crear bloqueo", type="primary"):
                        try:
                            add_block(db, prof_id, datetime.combine(day, start), datetime.combine(day, end), reason)
                            done("Bloqueo creado")
                        except Exception as exc:
                            friendly_error(exc)
            recent_blocks = list_blocks(db, TODAY, TODAY + timedelta(days=120))
            if recent_blocks:
                st.dataframe(pd.DataFrame([{"Fecha":b.start_at.strftime("%d/%m/%Y"),"Profesional":b.professional.name,
                                            "Desde":b.start_at.strftime("%H:%M"),"Hasta":b.end_at.strftime("%H:%M"),
                                            "Motivo":b.reason} for b in recent_blocks]), hide_index=True, use_container_width=True)
                selected = st.selectbox("Retirar bloqueo", [b.id for b in recent_blocks],
                                        format_func=lambda i: next(f"{b.start_at:%d/%m %H:%M} · {b.professional.name} · {b.reason}" for b in recent_blocks if b.id == i))
                if st.button("Eliminar bloqueo seleccionado"):
                    try:
                        delete_block(db, selected)
                        done("Bloqueo retirado")
                    except Exception as exc:
                        friendly_error(exc)

    def services_page():
        header("Catálogo de tratamientos", "Configura procedimientos, duración de agenda y tarifas referenciales.", "CATÁLOGO CLÍNICO")
        if services:
            st.dataframe(pd.DataFrame([{"Procedimiento":s.name,"Duración (min)":s.duration_min,
                                        "Valor (COP)":money(s.price_cop),"Estado":"Activo" if s.active else "Inactivo"}
                                        for s in services]), use_container_width=True, hide_index=True)
        with st.container(border=True):
            section_bar("Crear procedimiento")
            with st.form("new_service"):
                a, b, c = st.columns([2.5, 1, 1.5])
                name = a.text_input("Nombre del procedimiento")
                duration = b.selectbox("Duración", list(range(15, 241, 15)), index=1, format_func=lambda t:f"{t} min")
                price = c.number_input("Valor (COP)", min_value=0, value=0, step=10000)
                if st.form_submit_button("Guardar procedimiento", type="primary"):
                    try:
                        create_service(db, name, duration, int(price))
                        done("Procedimiento agregado")
                    except Exception as exc:
                        friendly_error(exc)
        if services:
            with st.container(border=True):
                section_bar("Actualizar procedimiento")
                sid = st.selectbox("Selecciona un procedimiento", [s.id for s in services],
                                    format_func=lambda i: next(s.name for s in services if s.id == i))
                s = db.get(Service, sid)
                with st.form(f"edit_service_{sid}"):
                    a, b, c = st.columns(3)
                    duration = a.selectbox("Duración (min)", list(range(15,241,15)), index=(s.duration_min // 15)-1)
                    price = b.number_input("Precio (COP)", min_value=0, value=s.price_cop, step=10000)
                    active = c.checkbox("Disponible para agendar", s.active)
                    if st.form_submit_button("Guardar cambios", type="primary"):
                        s.duration_min, s.price_cop, s.active = int(duration), int(price), active
                        db.commit()
                        done("Procedimiento actualizado")
                st.caption("Los cambios de duración aplican a las nuevas citas. Las citas existentes conservan su horario original.")

    def settings_page():
        header("Configuración de la clínica", "Ajusta el horario de atención y los parámetros operativos.", "ADMINISTRACIÓN")
        st.markdown(f"**Nombre de la clínica:** {CLINIC}")
        st.markdown("**Zona horaria:** Bogotá, Colombia (UTC−05:00)")
        st.markdown("**Motor de persistencia:** PostgreSQL externo" if DB_URL.startswith("postgres") else "**Motor de persistencia:** SQLite local de demostración")
        st.divider()
        section_bar("Horario general de atención", "Estas jornadas controlan qué turnos podrán reservarse.")
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        workdays = get_workdays(db)
        with st.form("clinic_schedule"):
            changes = []
            for day in workdays:
                a,b,c,d = st.columns([1.5,1,1,1])
                a.markdown(f"**{days[day.weekday]}**")
                enabled = b.checkbox("Abierto", value=day.enabled, key=f"open_{day.weekday}")
                opening = c.time_input("Inicio", value=day.opening, key=f"opening_{day.weekday}", label_visibility="collapsed", step=900)
                closing = d.time_input("Cierre", value=day.closing, key=f"closing_{day.weekday}", label_visibility="collapsed", step=900)
                changes.append((day.weekday, enabled, opening, closing))
            if st.form_submit_button("Guardar horario semanal", type="primary"):
                try:
                    if any(start >= end for _,_,start,end in changes):
                        raise BusinessError("La hora de inicio debe ser anterior al cierre en todos los días.")
                    for weekday, active, start, end in changes:
                        set_workday(db, weekday, active, start, end)
                    done("Horario actualizado")
                except Exception as exc:
                    friendly_error(exc)
        st.info("El cambio de horario no modifica ni cancela reservas ya registradas. Revisa las citas existentes si reduces la jornada.")
        st.caption("Seguridad: utiliza una contraseña única, PostgreSQL con TLS, copias de seguridad y accesos restringidos. No almacenes historias clínicas en esta versión.")

    with st.sidebar:
        st.markdown('<div class="df-brand">🦷 Dental<span>Flow</span></div><div class="df-side-caption">CLINIC MANAGEMENT SYSTEM</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:#AACAD2;font-size:12px;font-weight:700;padding-bottom:8px">{escape(CLINIC)}</div>', unsafe_allow_html=True)
        st.divider()
        menu = ["Resumen", "Agenda", "Pacientes", "Profesionales", "Tratamientos", "Configuración"]
        labels = {"Resumen":"▦   Resumen", "Agenda":"▦   Agenda", "Pacientes":"♙   Pacientes",
                  "Profesionales":"♧   Profesionales", "Tratamientos":"✧   Tratamientos", "Configuración":"⚙   Configuración"}
        if "nav" not in st.session_state:
            st.session_state["nav"] = "Resumen"
        if "sidebar_nav" not in st.session_state:
            st.session_state["sidebar_nav"] = st.session_state["nav"]
        selection = st.radio("NAVEGACIÓN", menu, format_func=lambda x:labels[x],
                             label_visibility="collapsed", key="sidebar_nav")
        if selection != st.session_state["nav"]:
            st.session_state["nav"] = selection
            st.rerun()
        st.divider()
        st.markdown(f'<div style="font-size:12px;color:#9BC4C8">● Sistema disponible<br>{NOW:%A, %d/%m/%Y}</div>', unsafe_allow_html=True)
        if DEMO:
            st.warning("MODO DEMO · No ingreses datos reales")
        else:
            st.caption(f"Usuario: {st.session_state.get('user_email','admin')}")
            if st.button("Cerrar sesión", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        st.markdown('<div class="df-foot">DentalFlow · Versión 1.0.0<br>Privacidad por diseño</div>', unsafe_allow_html=True)

    if DEMO:
        st.warning("🧪 **Modo demostración:** información temporal, no apta para pacientes reales. Para producción configura PostgreSQL y autenticación.")
    current = st.session_state["nav"]
    if current == "Resumen":
        overview()
    elif current == "Agenda":
        agenda()
    elif current == "Pacientes":
        patients_page()
    elif current == "Profesionales":
        professionals_page()
    elif current == "Tratamientos":
        services_page()
    else:
        settings_page()
