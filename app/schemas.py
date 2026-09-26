import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

SPECIALTIES = ['Kaygı ve stres', 'İlişkiler', 'Özgüven', 'Duygusal zorluklar', 'İş ve yaşam dengesi', 'Kendini tanıma']
MOODS = ['iyi', 'karisik', 'kaygili', 'uzgun', 'yorgun']

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal['client', 'therapist'] = 'client'

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class TherapistCreateOrUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    bio: str | None = Field(default=None, max_length=3000)
    license_no: str = Field(min_length=3, max_length=50)
    session_minutes: int = Field(default=50, ge=20, le=120)
    session_price: Decimal = Field(gt=0, le=99999999, decimal_places=2)
    education: list[str] = Field(default_factory=list, max_length=10)
    specialties: list[str] = Field(default_factory=list, max_length=6)

    @field_validator('education')
    @classmethod
    def education_lengths(cls, value):
        if any(not x.strip() or len(x) > 250 for x in value):
            raise ValueError('Eğitim bilgileri 1–250 karakter olmalı')
        return [x.strip() for x in value]

    @field_validator('specialties')
    @classmethod
    def known_specialties(cls, value):
        if any(x not in SPECIALTIES for x in value):
            raise ValueError('Geçerli çalışma alanlarını seçin')
        return list(dict.fromkeys(value))

class TherapistProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    bio: str | None
    is_verified: bool
    session_minutes: int
    session_price: float
    education: list[str]
    full_name: str
    specialties: list[str]
    rating: float | None
    review_count: int
    match_reasons: list[str] = Field(default_factory=list)

class AvailabilityRuleCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode='after')
    def valid_interval(self):
        for value in (self.start_time, self.end_time):
            if value.tzinfo or value.second or value.microsecond:
                raise ValueError('Saatleri SS:DD biçiminde girin')
        if self.start_time >= self.end_time:
            raise ValueError('Bitiş saati başlangıçtan sonra olmalı')
        return self

class AvailabilityRuleOut(AvailabilityRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID

class AppointmentCreate(BaseModel):
    therapist_id: uuid.UUID
    date: date
    start_time: time
    mood: Literal['iyi', 'karisik', 'kaygili', 'uzgun', 'yorgun'] | None = None
    expectations: list[str] = Field(default_factory=list, max_length=6)

    @field_validator('start_time')
    @classmethod
    def local_minutes(cls, value):
        if value.tzinfo or value.second or value.microsecond:
            raise ValueError('Saatleri SS:DD biçiminde girin')
        return value

    @field_validator('expectations')
    @classmethod
    def known_expectations(cls, value):
        if any(x not in SPECIALTIES for x in value):
            raise ValueError('Geçersiz beklenti')
        return list(dict.fromkeys(value))

class AppointmentOut(BaseModel):
    id: uuid.UUID
    therapist_id: uuid.UUID
    client_id: uuid.UUID
    therapist_name: str
    client_name: str
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime
    mood: str | None
    expectations: list[str]
    session_price: float | None
    reviewed: bool

class AppointmentStatusUpdate(BaseModel):
    status: Literal['confirmed', 'cancelled', 'completed']

class ReviewCreate(BaseModel):
    therapist_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)

class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    therapist_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime
