# ملف models

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from enum import Enum
from datetime import datetime


# أنواع المواقف
class ParkingType(str, Enum):
    car = "Car Parking"
    bike = "Bike Parking"
    disabled = "Disabled Parking"


# حالة الحجز
class ReservationStatus(str, Enum):
    booked = "Booked"
    cancelled = "Cancelled"
    ended = "Ended"
    completed = "Completed"


# جدول المستخدمين
class Users_Informations(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone_number: str  # نص لتجنب مشاكل الأرقام الطويلة
    password: str
    vehicle_type: str
    plate_number: str
    color: str

    # علاقة مع الحجوزات
    reservations: List["Parking_Reservations"] = Relationship(back_populates="user")


# جدول الحجوزات
class Parking_Reservations(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users_informations.id")  # ربط بالحساب
    parking_type: ParkingType
    booking_date: datetime  # تاريخ الحجز
    entry_time: datetime  # وقت الدخول
    booking_hours: float
    total_fee: float
    qr_code: Optional[str] = None

    # ⭐ حالة الحجز (الإضافة الجديدة)
    status: ReservationStatus = Field(default=ReservationStatus.booked)

    # علاقة مع المستخدم
    user: Optional[Users_Informations] = Relationship(back_populates="reservations")

