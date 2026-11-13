"""Reglas de negocio; independientes de la interfaz para poder probarlas."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Appointment, AppointmentEvent, Block, Patient, Professional, Service, Workday

def local_now() -> datetime:
    """Hora de la clínica: Colombia (independiente de la zona horaria del servidor)."""
    return datetime.now(ZoneInfo("America/Bogota")).replace(tzinfo=None)


STATUSES = ("Programada", "Confirmada", "En atención", "Atendida", "Cancelada", "No asistió")
BUSY_STATUSES = ("Programada", "Confirmada", "En atención", "Atendida", "No asistió")

class BusinessError(ValueError):
    """Error amigable para mostrar al usuario."""


def _trim(value: str | None, limit: int) -> str:
    return (value or "").strip()[:limit]


def create_patient(db: Session, *, first_name: str, last_name: str, document_type: str,
                   document_number: str, phone: str, email: str = "", birth_date: date | None = None,
                   notes: str = "") -> Patient:
    first_name, last_name = _trim(first_name, 100), _trim(last_name, 100)
    document_number, phone = _trim(document_number, 35), _trim(phone, 30)
    if not all([first_name, last_name, document_number, phone]):
        raise BusinessError("Nombre, apellido, documento y teléfono son obligatorios.")
    if len(document_number) < 4:
        raise BusinessError("El documento debe tener al menos 4 caracteres.")
    email = _trim(email, 200).lower()
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise BusinessError("El correo electrónico no es válido.")
    if birth_date and birth_date > date.today():
        raise BusinessError("La fecha de nacimiento no puede ser futura.")
    if db.scalar(select(Patient).where(Patient.document_number == document_number)):
        raise BusinessError("Ya existe un paciente registrado con ese documento.")
    p = Patient(first_name=first_name, last_name=last_name, document_type=_trim(document_type, 15) or "CC",
                document_number=document_number, phone=phone, email=email or None,
                birth_date=birth_date, notes=_trim(notes, 3000) or None)
    db.add(p)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessError("No fue posible registrar al paciente; verifica el documento.") from exc
    return p


def update_patient(db: Session, patient_id: str, **fields) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise BusinessError("Paciente no encontrado.")
    for name in ("first_name", "last_name", "phone", "email", "notes"):
        if name in fields:
            setattr(patient, name, _trim(fields[name], 3000 if name == "notes" else 200))
    if not all((patient.first_name, patient.last_name, patient.phone)):
        raise BusinessError("El nombre, el apellido y el teléfono son obligatorios.")
    if patient.email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", patient.email):
        raise BusinessError("Correo electrónico no válido.")
    db.commit()
    return patient


def create_professional(db: Session, name: str, specialty: str, color: str = "#14B8A6") -> Professional:
    if not _trim(name, 160):
        raise BusinessError("Indica el nombre del profesional.")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise BusinessError("El color debe ser un código hexadecimal válido.")
    professional = Professional(name=_trim(name, 160), specialty=_trim(specialty, 100) or "Odontología general", color=color)
    db.add(professional)
    db.commit()
    return professional


def create_service(db: Session, name: str, duration_min: int, price_cop: int = 0) -> Service:
    if not _trim(name, 120) or duration_min not in range(15, 241) or duration_min % 15 or price_cop < 0:
        raise BusinessError("Indica un servicio, duración de 15 a 240 minutos en intervalos de 15 y precio no negativo.")
    obj = Service(name=_trim(name, 120), duration_min=duration_min, price_cop=price_cop)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessError("Ya existe un servicio con ese nombre.") from exc
    return obj


def list_patients(db: Session) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.first_name, Patient.last_name)).all())


def list_professionals(db: Session, active_only: bool = False) -> list[Professional]:
    stmt = select(Professional).order_by(Professional.name)
    if active_only:
        stmt = stmt.where(Professional.active.is_(True))
    return list(db.scalars(stmt).all())


def list_services(db: Session, active_only: bool = False) -> list[Service]:
    stmt = select(Service).order_by(Service.name)
    if active_only:
        stmt = stmt.where(Service.active.is_(True))
    return list(db.scalars(stmt).all())


def list_appointments(db: Session, from_date: date, through_date: date,
                      professional_id: str | None = None) -> list[Appointment]:
    low = datetime.combine(from_date, time.min)
    high = datetime.combine(through_date + timedelta(days=1), time.min)
    stmt = select(Appointment).where(Appointment.start_at >= low, Appointment.start_at < high)
    if professional_id:
        stmt = stmt.where(Appointment.professional_id == professional_id)
    return list(db.scalars(stmt.order_by(Appointment.start_at)).all())


def list_blocks(db: Session, from_date: date, through_date: date) -> list[Block]:
    low = datetime.combine(from_date, time.min)
    high = datetime.combine(through_date + timedelta(days=1), time.min)
    return list(db.scalars(select(Block).where(Block.end_at > low, Block.start_at < high)).all())


def _available(db: Session, professional_id: str, starts: datetime, ends: datetime, exclude_id: str | None = None) -> bool:
    stmt = select(Appointment.id).where(
        Appointment.professional_id == professional_id,
        Appointment.status.in_(BUSY_STATUSES),
        Appointment.start_at < ends,
        Appointment.end_at > starts,
    )
    if exclude_id:
        stmt = stmt.where(Appointment.id != exclude_id)
    if db.scalar(stmt.limit(1)) is not None:
        return False
    blocked = db.scalar(select(Block.id).where(
        Block.professional_id == professional_id,
        Block.start_at < ends,
        Block.end_at > starts,
    ).limit(1))
    return blocked is None


def _validate_hours(db: Session, starts: datetime, ends: datetime) -> None:
    if starts >= ends or starts.date() != (ends - timedelta(microseconds=1)).date():
        raise BusinessError("La cita debe empezar y terminar el mismo día.")
    workday = db.scalar(select(Workday).where(Workday.weekday == starts.weekday()))
    if not workday or not workday.enabled or starts.time() < workday.opening or ends.time() > workday.closing:
        raise BusinessError("El horario está fuera de la jornada configurada para ese día.")
    if starts.minute % 15 or starts.second or starts.microsecond:
        raise BusinessError("Las citas deben comenzar en bloques de 15 minutos.")


def create_appointment(db: Session, *, patient_id: str, professional_id: str,
                       service_id: str, starts: datetime, reason: str = "", notes: str = "",
                       created_by: str = "Administrador", allow_past: bool = False) -> Appointment:
    if starts.tzinfo is not None:
        raise BusinessError("El horario se debe proporcionar en hora local de Colombia, sin zona horaria adjunta.")
    patient = db.get(Patient, patient_id)
    if not patient or not patient.active:
        raise BusinessError("Selecciona un paciente activo.")
    # Bloquea la fila del profesional en PostgreSQL durante la validación contra dobles reservas.
    professional = db.scalar(select(Professional).where(Professional.id == professional_id).with_for_update())
    service = db.get(Service, service_id)
    if not professional or not professional.active or not service or not service.active:
        raise BusinessError("Selecciona un profesional y un servicio activos.")
    ends = starts + timedelta(minutes=service.duration_min)
    _validate_hours(db, starts, ends)
    if not allow_past and starts < local_now():
        raise BusinessError("No es posible agendar una cita en el pasado.")
    if not _available(db, professional_id, starts, ends):
        raise BusinessError("Este profesional ya tiene una cita o un bloqueo en ese intervalo.")
    appointment = Appointment(patient_id=patient_id, professional_id=professional_id,
                              service_id=service_id, start_at=starts, end_at=ends,
                              reason=_trim(reason, 250) or None, notes=_trim(notes, 3000) or None,
                              created_by=_trim(created_by, 200))
    db.add(appointment)
    db.flush()
    db.add(AppointmentEvent(appointment_id=appointment.id, action="Creación",
                            detail=f"Reserva {starts:%d/%m/%Y %H:%M} · {service.duration_min} min",
                            actor=_trim(created_by, 200)))
    db.commit()
    return appointment


def reschedule_appointment(db: Session, appointment_id: str, starts: datetime,
                           professional_id: str | None = None, service_id: str | None = None,
                           allow_past: bool = False, actor: str = "Administrador") -> Appointment:
    a = db.get(Appointment, appointment_id)
    if not a:
        raise BusinessError("La cita no existe.")
    if a.status in ("Cancelada", "Atendida", "No asistió"):
        raise BusinessError("No se pueden reprogramar citas canceladas o cerradas.")
    target_professional = professional_id or a.professional_id
    professional = db.scalar(select(Professional).where(Professional.id == target_professional).with_for_update())
    service = db.get(Service, service_id or a.service_id)
    if not professional or not professional.active or not service or not service.active:
        raise BusinessError("Profesional o servicio inactivo.")
    if starts.tzinfo is not None:
        raise BusinessError("Utiliza la hora local de Colombia.")
    ends = starts + timedelta(minutes=service.duration_min)
    _validate_hours(db, starts, ends)
    if not allow_past and starts < local_now():
        raise BusinessError("No es posible reprogramar hacia el pasado.")
    if not _available(db, target_professional, starts, ends, exclude_id=a.id):
        raise BusinessError("El horario solicitado ya se encuentra ocupado o bloqueado.")
    original = a.start_at
    a.start_at, a.end_at, a.professional_id, a.service_id = starts, ends, target_professional, service.id
    a.updated_at = local_now()
    db.add(AppointmentEvent(appointment_id=a.id, action="Reprogramación",
                            detail=f"{original:%d/%m/%Y %H:%M} → {starts:%d/%m/%Y %H:%M}",
                            actor=_trim(actor, 200)))
    db.commit()
    return a


def change_status(db: Session, appointment_id: str, new_status: str, actor: str = "Administrador") -> Appointment:
    if new_status not in STATUSES:
        raise BusinessError("Estado de cita no válido.")
    a = db.get(Appointment, appointment_id)
    if not a:
        raise BusinessError("La cita no existe.")
    if a.status in ("Cancelada", "Atendida", "No asistió") and new_status != a.status:
        raise BusinessError("La cita ya está cerrada. No es posible reabrirla desde esta pantalla.")
    if new_status == "Programada" and a.status == "En atención":
        raise BusinessError("Una cita en atención no puede volver a Programada.")
    old_status = a.status
    a.status, a.updated_at = new_status, local_now()
    if old_status != new_status:
        db.add(AppointmentEvent(appointment_id=a.id, action="Cambio de estado",
                                detail=f"{old_status} → {new_status}", actor=_trim(actor, 200)))
    db.commit()
    return a


def free_slots(db: Session, professional_id: str, service_id: str, target_date: date) -> list[datetime]:
    service = db.get(Service, service_id)
    workday = db.scalar(select(Workday).where(Workday.weekday == target_date.weekday()))
    if not service or not workday or not workday.enabled:
        return []
    cursor = datetime.combine(target_date, workday.opening)
    limit = datetime.combine(target_date, workday.closing)
    slots = []
    while cursor + timedelta(minutes=service.duration_min) <= limit:
        if cursor >= local_now() and _available(db, professional_id, cursor, cursor + timedelta(minutes=service.duration_min)):
            slots.append(cursor)
        cursor += timedelta(minutes=15)
    return slots


def add_block(db: Session, professional_id: str, starts: datetime, ends: datetime, reason: str) -> Block:
    professional = db.scalar(select(Professional).where(Professional.id == professional_id).with_for_update())
    if not professional:
        raise BusinessError("Profesional no encontrado.")
    if ends <= starts:
        raise BusinessError("El fin del bloqueo debe ser posterior al inicio.")
    if not _available(db, professional_id, starts, ends):
        raise BusinessError("El bloqueo se superpone con una cita o un bloqueo existente.")
    block = Block(professional_id=professional_id, start_at=starts, end_at=ends,
                  reason=_trim(reason, 150) or "No disponible")
    db.add(block)
    db.commit()
    return block


def delete_block(db: Session, block_id: str) -> None:
    block = db.get(Block, block_id)
    if not block:
        raise BusinessError("Bloqueo no encontrado.")
    db.delete(block)
    db.commit()


def set_workday(db: Session, weekday: int, enabled: bool, opening: time, closing: time) -> Workday:
    if not 0 <= weekday <= 6 or opening >= closing:
        raise BusinessError("Jornada no válida.")
    obj = db.scalar(select(Workday).where(Workday.weekday == weekday))
    if not obj:
        raise BusinessError("Día no encontrado.")
    obj.enabled, obj.opening, obj.closing = enabled, opening, closing
    db.commit()
    return obj


def get_workdays(db: Session) -> list[Workday]:
    return list(db.scalars(select(Workday).order_by(Workday.weekday)).all())
