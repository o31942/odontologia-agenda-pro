"""Persistencia de DentalFlow; los datos reales residen fuera de GitHub."""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time
from functools import lru_cache

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(15), nullable=False, default="CC")
    document_number: Mapped[str] = mapped_column(String(35), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    birth_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Professional(Base):
    __tablename__ = "professionals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, default="Odontología general")
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#14B8A6")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Workday(Base):
    __tablename__ = "workdays"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    opening: Mapped[time] = mapped_column(Time, nullable=False)
    closing: Mapped[time] = mapped_column(Time, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[str] = mapped_column(ForeignKey("professionals.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="Programada")
    reason: Mapped[str | None] = mapped_column(String(250))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(200), default="Administrador")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    patient: Mapped[Patient] = relationship(lazy="joined")
    professional: Mapped[Professional] = relationship(lazy="joined")
    service: Mapped[Service] = relationship(lazy="joined")


class AppointmentEvent(Base):
    __tablename__ = "appointment_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(35), nullable=False)
    detail: Mapped[str] = mapped_column(String(250), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="Administrador")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Block(Base):
    __tablename__ = "blocks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    professional_id: Mapped[str] = mapped_column(ForeignKey("professionals.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(150), nullable=False)
    professional: Mapped[Professional] = relationship(lazy="joined")


DEFAULT_SERVICES = [
    ("Valoración odontológica", 30, 80000),
    ("Profilaxis y limpieza", 45, 120000),
    ("Restauración dental", 60, 160000),
    ("Control de ortodoncia", 30, 90000),
    ("Endodoncia", 90, 350000),
    ("Urgencia odontológica", 30, 120000),
]


@lru_cache(maxsize=8)
def make_engine(url: str):
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    is_sqlite = url.startswith("sqlite")
    kwargs = {"pool_pre_ping": True}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 20}
    engine = create_engine(url, **kwargs)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def set_sqlite_fk(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    return engine


def session_factory(url: str):
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)


def initialize(url: str) -> None:
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    with session_factory(url)() as db:
        if db.query(Service).count() == 0:
            db.add_all([Service(name=n, duration_min=d, price_cop=p) for n, d, p in DEFAULT_SERVICES])
        for w in range(7):
            if db.query(Workday).filter_by(weekday=w).first() is None:
                db.add(Workday(weekday=w, opening=time(8, 0), closing=time(13 if w == 5 else 18, 0), enabled=w < 6))
        db.commit()
