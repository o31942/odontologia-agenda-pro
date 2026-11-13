"""Pruebas de persistencia y reglas críticas de agendamiento."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from dentalflow.db import Appointment, Patient, Professional, Service, initialize, session_factory
from dentalflow.services import (
    BusinessError, add_block, change_status, create_appointment, create_patient,
    create_professional, free_slots, list_appointments, local_now, reschedule_appointment,
)


@pytest.fixture
def clinic(tmp_path):
    url = f"sqlite:///{tmp_path / 'tests.sqlite3'}"
    initialize(url)
    with session_factory(url)() as db:
        patient = create_patient(db, first_name="Paciente", last_name="Prueba",
                                 document_type="CC", document_number=str(uuid.uuid4())[:12], phone="3000000000")
        dentist = create_professional(db, "Dra. Pruebas", "Odontología general")
        service = db.scalar(select(Service).where(Service.duration_min == 30))
        yield db, patient, dentist, service


def future_weekday():
    day = local_now().date() + timedelta(days=3)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, datetime.strptime("10:00", "%H:%M").time())


def book(clinic, when=None):
    db, patient, dentist, service = clinic
    return create_appointment(db, patient_id=patient.id, professional_id=dentist.id,
                              service_id=service.id, starts=when or future_weekday())


def test_patient_duplicate_document(clinic):
    db, patient, _, _ = clinic
    with pytest.raises(BusinessError, match="existe"):
        create_patient(db, first_name="Otro", last_name="Prueba", document_type="CC",
                       document_number=patient.document_number, phone="3111111111")


def test_new_appointment_and_listing(clinic):
    a = book(clinic)
    db, _, _, _ = clinic
    rows = list_appointments(db, a.start_at.date(), a.start_at.date())
    assert len(rows) == 1
    assert rows[0].patient.full_name == "Paciente Prueba"
    assert rows[0].end_at - rows[0].start_at == timedelta(minutes=30)


def test_exact_overlap_and_partial_overlap_are_rejected(clinic):
    first = book(clinic)
    with pytest.raises(BusinessError, match="cita o un bloqueo"):
        book(clinic, first.start_at)
    with pytest.raises(BusinessError, match="cita o un bloqueo"):
        book(clinic, first.start_at + timedelta(minutes=15))
    following = book(clinic, first.end_at)
    assert following.start_at == first.end_at


def test_cancellation_frees_slot(clinic):
    first = book(clinic)
    db, _, dentist, svc = clinic
    assert first.start_at not in free_slots(db, dentist.id, svc.id, first.start_at.date())
    change_status(db, first.id, "Cancelada")
    assert first.start_at in free_slots(db, dentist.id, svc.id, first.start_at.date())
    new = book(clinic, first.start_at)
    assert new.id != first.id


def test_block_prevents_booking(clinic):
    db, _, dentist, _ = clinic
    at = future_weekday()
    add_block(db, dentist.id, at, at + timedelta(hours=2), "Vacaciones")
    with pytest.raises(BusinessError, match="cita o un bloqueo"):
        book(clinic, at)
    with pytest.raises(BusinessError, match="superpone"):
        add_block(db, dentist.id, at + timedelta(minutes=15), at + timedelta(minutes=45), "Reunión")


def test_reschedule_and_reschedule_conflict(clinic):
    first = book(clinic)
    later = book(clinic, first.end_at)
    db, _, _, _ = clinic
    with pytest.raises(BusinessError, match="ocupado"):
        reschedule_appointment(db, first.id, later.start_at)
    rescheduled = reschedule_appointment(db, first.id, later.end_at)
    assert rescheduled.start_at == later.end_at


def test_closed_status_prevents_reschedule(clinic):
    first = book(clinic)
    db, _, _, _ = clinic
    change_status(db, first.id, "Atendida")
    with pytest.raises(BusinessError, match="cerradas"):
        reschedule_appointment(db, first.id, first.start_at + timedelta(days=7))


def test_outside_working_hours_rejected(clinic):
    at = future_weekday().replace(hour=19)
    with pytest.raises(BusinessError, match="fuera"):
        book(clinic, at)


def test_appointment_in_past_rejected(clinic):
    at = future_weekday() - timedelta(days=30)
    while at.weekday() > 4:
        at -= timedelta(days=1)
    with pytest.raises(BusinessError, match="pasado"):
        book(clinic, at)


def test_halfhour_slot_respects_no_overlap(clinic):
    first = book(clinic)
    db, _, dentist, service = clinic
    slots = free_slots(db, dentist.id, service.id, first.start_at.date())
    assert first.start_at not in slots
    assert first.start_at + timedelta(minutes=15) not in slots
    assert first.end_at in slots


def test_audit_history_on_status_and_reschedule(clinic):
    from dentalflow.db import AppointmentEvent
    db, _, _, _ = clinic
    a = book(clinic)
    change_status(db, a.id, "Confirmada", actor="admin@clinic.test")
    reschedule_appointment(db, a.id, a.start_at + timedelta(hours=1), actor="admin@clinic.test")
    events = list(db.scalars(select(AppointmentEvent).where(AppointmentEvent.appointment_id == a.id)))
    assert {event.action for event in events} == {"Creación", "Cambio de estado", "Reprogramación"}
    assert events[-1].actor == "admin@clinic.test"
