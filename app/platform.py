"""Booking and discovery API. All calendar calculations use Europe/Istanbul."""
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m, schemas as s
from app.db import get_db

TZ = ZoneInfo('Europe/Istanbul')
ACTIVE = ('pending', 'confirmed')
LINK = m.Specialty.therapist_specialties


def commit(db, detail='Bu işlem mevcut kayıtlarla çakışıyor'):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail)


def own_profile(db, user, lock=False):
    if user.role != 'therapist':
        raise HTTPException(403, 'Bu alan uzman hesabı gerektirir')
    stmt = select(m.TherapistProfile).where(m.TherapistProfile.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    profile = db.scalar(stmt)
    if not profile:
        raise HTTPException(404, 'Önce uzman profilinizi oluşturun')
    return profile


def public_profile(db, profile_id, lock=False):
    stmt = select(m.TherapistProfile).join(m.User, m.User.id == m.TherapistProfile.user_id).where(
        m.TherapistProfile.id == profile_id, m.TherapistProfile.is_verified.is_(True), m.User.is_active.is_(True))
    if lock:
        stmt = stmt.with_for_update(of=m.TherapistProfile)
    profile = db.scalar(stmt)
    if not profile:
        raise HTTPException(404, 'Uzman bulunamadı veya henüz doğrulanmadı')
    return profile


def profile_data(db, p):
    names = list(db.scalars(select(m.Specialty.name).join(LINK, LINK.c.specialty_id == m.Specialty.id).where(LINK.c.therapist_id == p.id).order_by(m.Specialty.name)))
    rating, count = db.execute(select(func.avg(m.Review.rating), func.count(m.Review.id)).where(m.Review.therapist_id == p.id, m.Review.client_id.is_not(None))).one()
    return dict(id=p.id, user_id=p.user_id, full_name=db.get(m.User, p.user_id).full_name,
                title=p.title, bio=p.bio, is_verified=p.is_verified, education=p.education,
                session_minutes=p.session_minutes, session_price=float(p.session_price),
                specialties=names, rating=round(float(rating), 1) if rating else None, review_count=count)


def available_slots(db, p, day, client_id=None):
    now = datetime.now(TZ)
    if day < now.date() or day > now.date() + timedelta(days=90):
        return []
    rules = db.scalars(select(m.AvailabilityRule).where(m.AvailabilityRule.therapist_id == p.id, m.AvailabilityRule.weekday == day.weekday())).all()
    start = datetime.combine(day, datetime.min.time(), TZ)
    window = Range(start, start + timedelta(days=1), bounds='[)')
    booked = list(db.scalars(select(m.Appointment).where(m.Appointment.therapist_id == p.id, m.Appointment.status.in_(ACTIVE), m.Appointment.slot.overlaps(window))))
    if client_id:
        booked += list(db.scalars(select(m.Appointment).where(m.Appointment.client_id == client_id, m.Appointment.status.in_(ACTIVE), m.Appointment.slot.overlaps(window))))
    offs = db.scalars(select(m.TimeOff).where(m.TimeOff.therapist_id == p.id, m.TimeOff.starts_at < window.upper, m.TimeOff.ends_at > window.lower)).all()
    result = set()
    for rule in rules:
        cursor = datetime.combine(day, rule.start_time, TZ)
        limit = datetime.combine(day, rule.end_time, TZ)
        duration = timedelta(minutes=p.session_minutes)
        while cursor + duration <= limit:
            end = cursor + duration
            if cursor > now and not any(a.slot.lower < end and a.slot.upper > cursor for a in booked) and not any(o.starts_at < end and o.ends_at > cursor for o in offs):
                result.add(cursor)
            cursor += duration
    return sorted(result)


def appointment_data(db, a):
    p = db.get(m.TherapistProfile, a.therapist_id)
    reviewed = db.scalar(select(m.Review.id).where(m.Review.therapist_id == a.therapist_id, m.Review.client_id == a.client_id)) is not None
    return dict(id=a.id, therapist_id=a.therapist_id, client_id=a.client_id,
                therapist_name=db.get(m.User, p.user_id).full_name, client_name=db.get(m.User, a.client_id).full_name,
                starts_at=a.slot.lower, ends_at=a.slot.upper, status=a.status, created_at=a.created_at,
                mood=a.mood, expectations=a.expectations, session_price=float(a.session_price) if a.session_price is not None else None, reviewed=reviewed)


def build_router(current_user):
    router = APIRouter(prefix='/api')

    @router.get('/options')
    def options():
        return {'specialties': s.SPECIALTIES, 'moods': s.MOODS, 'timezone': str(TZ)}

    @router.get('/therapists', response_model=list[s.TherapistProfileOut])
    def therapists(expectations: list[str] = Query(default=[]), mood: str | None = None, db: Session = Depends(get_db)):
        if any(x not in s.SPECIALTIES for x in expectations) or (mood is not None and mood not in s.MOODS):
            raise HTTPException(422, 'Geçersiz seçim')
        # Transparent preference ranking, never a diagnosis or clinical assessment.
        mood_area = {'kaygili': 'Kaygı ve stres', 'uzgun': 'Duygusal zorluklar', 'yorgun': 'İş ve yaşam dengesi', 'karisik': 'Kendini tanıma'}
        preferred = set(expectations)
        if mood in mood_area:
            preferred.add(mood_area[mood])
        profiles = db.scalars(select(m.TherapistProfile).join(m.User, m.User.id == m.TherapistProfile.user_id).where(m.TherapistProfile.is_verified.is_(True), m.User.is_active.is_(True))).all()
        result = [profile_data(db, p) for p in profiles]
        for p in result:
            p['match_reasons'] = sorted(preferred.intersection(p['specialties']))
        if preferred:
            result = [p for p in result if p['match_reasons']]
        return sorted(result, key=lambda p: (-len(p['match_reasons']), p['full_name']))

    @router.get('/therapists/me')
    def my_profile(user=Depends(current_user), db: Session = Depends(get_db)):
        p = own_profile(db, user)
        return {**profile_data(db, p), 'license_no': p.license_no}

    @router.put('/therapists/me', response_model=s.TherapistProfileOut)
    def save_profile(payload: s.TherapistCreateOrUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
        if user.role != 'therapist':
            raise HTTPException(403, 'Uzman hesabı gerektirir')
        # Serialize profile creation as well as edits.
        db.scalar(select(m.User).where(m.User.id == user.id).with_for_update())
        p = db.scalar(select(m.TherapistProfile).where(m.TherapistProfile.user_id == user.id).with_for_update())
        if p is None:
            p = m.TherapistProfile(user_id=user.id)
            db.add(p)
        elif any(getattr(p, field) != getattr(payload, field) for field in ('license_no', 'title', 'education')):
            p.is_verified = False
        for key, value in payload.model_dump(exclude={'specialties'}).items():
            setattr(p, key, value)
        db.flush()
        db.execute(delete(LINK).where(LINK.c.therapist_id == p.id))
        # The catalog is inserted idempotently even for concurrent profile saves.
        from sqlalchemy.dialects.postgresql import insert
        for name in payload.specialties:
            db.execute(insert(m.Specialty).values(id=uuid.uuid4(), name=name).on_conflict_do_nothing(index_elements=['name']))
            specialty_id = db.scalar(select(m.Specialty.id).where(m.Specialty.name == name))
            db.execute(LINK.insert().values(therapist_id=p.id, specialty_id=specialty_id))
        commit(db)
        return profile_data(db, p)

    @router.get('/therapists/me/availability', response_model=list[s.AvailabilityRuleOut])
    def my_availability(user=Depends(current_user), db: Session = Depends(get_db)):
        p = own_profile(db, user)
        return list(db.scalars(select(m.AvailabilityRule).where(m.AvailabilityRule.therapist_id == p.id).order_by(m.AvailabilityRule.weekday, m.AvailabilityRule.start_time)))

    @router.post('/therapists/me/availability', response_model=s.AvailabilityRuleOut, status_code=201)
    def add_availability(payload: s.AvailabilityRuleCreate, user=Depends(current_user), db: Session = Depends(get_db)):
        p = own_profile(db, user, lock=True)
        clash = db.scalar(select(m.AvailabilityRule).where(m.AvailabilityRule.therapist_id == p.id, m.AvailabilityRule.weekday == payload.weekday, m.AvailabilityRule.start_time < payload.end_time, m.AvailabilityRule.end_time > payload.start_time))
        if clash:
            raise HTTPException(409, 'Bu gün için çakışan bir çalışma aralığı var')
        rule = m.AvailabilityRule(therapist_id=p.id, **payload.model_dump())
        db.add(rule)
        commit(db)
        return rule

    @router.delete('/therapists/me/availability/{rule_id}', status_code=204)
    def remove_availability(rule_id: uuid.UUID, user=Depends(current_user), db: Session = Depends(get_db)):
        p = own_profile(db, user, lock=True)
        rule = db.get(m.AvailabilityRule, rule_id)
        if not rule or rule.therapist_id != p.id:
            raise HTTPException(404, 'Çalışma aralığı bulunamadı')
        db.delete(rule)
        commit(db)

    @router.get('/therapists/{therapist_id}', response_model=s.TherapistProfileOut)
    def therapist(therapist_id: uuid.UUID, db: Session = Depends(get_db)):
        return profile_data(db, public_profile(db, therapist_id))

    @router.get('/therapists/{therapist_id}/slots')
    def slots(therapist_id: uuid.UUID, date: date, db: Session = Depends(get_db)):
        p = public_profile(db, therapist_id)
        return {'timezone': str(TZ), 'slots': [x.isoformat() for x in available_slots(db, p, date)]}

    @router.get('/therapists/{therapist_id}/reviews', response_model=list[s.ReviewOut])
    def reviews(therapist_id: uuid.UUID, db: Session = Depends(get_db)):
        public_profile(db, therapist_id)
        return list(db.scalars(select(m.Review).where(m.Review.therapist_id == therapist_id, m.Review.client_id.is_not(None)).order_by(m.Review.created_at.desc())))

    @router.post('/appointments', response_model=s.AppointmentOut, status_code=201)
    def book(payload: s.AppointmentCreate, user=Depends(current_user), db: Session = Depends(get_db)):
        if user.role != 'client':
            raise HTTPException(403, 'Randevu almak için danışan hesabı kullanın')
        p = public_profile(db, payload.therapist_id, lock=True)
        start = datetime.combine(payload.date, payload.start_time, TZ)
        if start not in available_slots(db, p, payload.date, user.id):
            raise HTTPException(409, 'Bu saat artık uygun değil. Başka bir saat seçin.')
        a = m.Appointment(therapist_id=p.id, client_id=user.id, slot=Range(start, start + timedelta(minutes=p.session_minutes), bounds='[)'),
                          status='pending', mood=payload.mood, expectations=payload.expectations, session_price=p.session_price)
        db.add(a)
        commit(db, 'Bu saat doldu veya başka bir randevunuzla çakışıyor')
        return appointment_data(db, a)

    @router.get('/appointments', response_model=list[s.AppointmentOut])
    def appointments(user=Depends(current_user), db: Session = Depends(get_db)):
        stmt = select(m.Appointment)
        if user.role == 'therapist':
            p = db.scalar(select(m.TherapistProfile).where(m.TherapistProfile.user_id == user.id))
            if not p:
                return []
            stmt = stmt.where(m.Appointment.therapist_id == p.id)
        else:
            stmt = stmt.where(m.Appointment.client_id == user.id)
        return [appointment_data(db, a) for a in db.scalars(stmt.order_by(m.Appointment.slot.desc()))]

    @router.patch('/appointments/{appointment_id}', response_model=s.AppointmentOut)
    def update_appointment(appointment_id: uuid.UUID, payload: s.AppointmentStatusUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
        a = db.scalar(select(m.Appointment).where(m.Appointment.id == appointment_id).with_for_update())
        if not a:
            raise HTTPException(404, 'Randevu bulunamadı')
        p = db.get(m.TherapistProfile, a.therapist_id)
        is_owner = user.role == 'therapist' and p.user_id == user.id
        if a.client_id != user.id and not is_owner:
            raise HTTPException(404, 'Randevu bulunamadı')
        now = datetime.now(TZ)
        if payload.status == 'cancelled':
            allowed = a.status in ACTIVE and a.slot.lower > now
        elif payload.status == 'confirmed':
            allowed = is_owner and a.status == 'pending' and a.slot.lower > now
        else:
            allowed = is_owner and a.status == 'confirmed' and a.slot.upper <= now
        if not allowed:
            raise HTTPException(409, 'Bu randevu için bu işlem şu anda yapılamaz')
        a.status = payload.status
        commit(db)
        return appointment_data(db, a)

    @router.post('/reviews', response_model=s.ReviewOut, status_code=201)
    def add_review(payload: s.ReviewCreate, user=Depends(current_user), db: Session = Depends(get_db)):
        if user.role != 'client':
            raise HTTPException(403, 'Yalnızca danışanlar değerlendirme yapabilir')
        attended = db.scalar(select(m.Appointment.id).where(m.Appointment.client_id == user.id, m.Appointment.therapist_id == payload.therapist_id, m.Appointment.status == 'completed'))
        if not attended:
            raise HTTPException(403, 'Değerlendirme için tamamlanmış bir seansınız olmalı')
        review = m.Review(client_id=user.id, **payload.model_dump())
        db.add(review)
        commit(db, 'Bu uzmanı zaten değerlendirdiniz')
        return review

    return router
