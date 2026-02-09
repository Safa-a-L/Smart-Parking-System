#main.py
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from models import *
from database import create_db_and_tables, get_session
from parking_system_operations import ParkingSystem, PaymentType, ParkingType
from datetime import datetime, timedelta
import os

# إنشاء مجلد لحفظ QR codes إذا ما موجود
os.makedirs("qr_codes", exist_ok=True)

app = FastAPI(title="Smart Parking Management System")

# --- تفعيل CORS للسماح بالربط بين الفرونت والباك ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# عرض مجلد الـ QR عبر المتصفح ليظهر في التذكرة
app.mount("/qr_codes", StaticFiles(directory="qr_codes"), name="qr_codes")

# تهيئة نظام العمليات
parking_system = ParkingSystem()

# سعة المواقف لكل فئة
CAPACITIES = {
    ParkingType.car: 40,
    ParkingType.bike: 20,
    ParkingType.disabled: 40
}

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

ADMIN_KEY = "shl123"

# 1. تسجيل الدخول أو إنشاء حساب
@app.post("/login/")
def login(name: str, phone_number: str, password: str, session: Session = Depends(get_session)):
    if not phone_number.startswith("+964"):
        raise HTTPException(status_code=400, detail="Phone number must start with +964")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain letters and numbers")

    user = session.exec(
        select(Users_Informations).where(
            Users_Informations.name == name,
            Users_Informations.phone_number == phone_number,
            Users_Informations.password == password
        )
    ).first()

    if not user:
        user = Users_Informations(
            name=name,
            phone_number=phone_number,
            password=password,
            vehicle_type="",
            plate_number="",
            color=""
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    return {
        "message": "Login successful", 
        "user_id": user.id, 
        "user_name": user.name,
        "phone_number": user.phone_number,
        "password": user.password,
        "vehicle_type": user.vehicle_type,
        "plate_number": user.plate_number,
        "color": user.color
    }

# 2. تحديث معلومات المركبة
@app.post("/user_vehicle/")
def update_vehicle_info(
    password: str,
    vehicle_type: str,
    plate_number: str,
    color: str,
    session: Session = Depends(get_session)
):
    user = session.exec(
        select(Users_Informations).where(Users_Informations.password == password)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.vehicle_type = vehicle_type
    user.plate_number = plate_number
    user.color = color

    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Vehicle information updated successfully", "user": user}

# 3. حجز موقف (مع فحص التوفر والامتلاء)
@app.post("/reserve_spot")
def reserve_spot(
    password: str,
    parking_type: ParkingType,
    booking_hours: float,
    payment_type: PaymentType,
    session: Session = Depends(get_session)
):
    user = session.exec(
        select(Users_Informations).where(Users_Informations.password == password)
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.vehicle_type or not user.plate_number:
        raise HTTPException(status_code=400, detail="Please update vehicle info in profile first")

    active_reservations_count = len(session.exec(
        select(Parking_Reservations).where(
            Parking_Reservations.parking_type == parking_type,
            Parking_Reservations.status == "booked"
        )
    ).all())

    if active_reservations_count >= CAPACITIES.get(parking_type, 0):
        raise HTTPException(status_code=400, detail=f"Sorry, {parking_type.value} section is FULL!")

    success, result = parking_system.book_spot(parking_type, booking_hours, payment_type)
    if not success:
        raise HTTPException(status_code=400, detail=result)

    total_fee = result["total_fee"]
    
    reservation = Parking_Reservations(
        user_id=user.id,
        parking_type=parking_type,
        booking_date=datetime.now(),
        entry_time=datetime.now(),
        booking_hours=booking_hours,
        total_fee=total_fee,
        status="booked",
        qr_code=""
    )
    session.add(reservation)
    session.commit()
    session.refresh(reservation)

    qr_info = (
        f"Reservation ID: {reservation.id}\n"
        f"Name: {user.name}\n"
        f"Plate: {user.plate_number}\n"
        f"Type: {parking_type.value}\n"
        f"Fee: {total_fee:,} IQD"
    )
    qr_path = parking_system.generate_qr(reservation.id, info=qr_info)
    reservation.qr_code = qr_path
    session.add(reservation)
    session.commit()
    session.refresh(reservation)

    return {
        "message": "Reserved successfully",
        "reservation_id": reservation.id,
        "user_name": user.name,
        "plate_number": user.plate_number,
        "total_fee": total_fee,
        "qr_code_path": qr_path
    }

# 4. جلب حجوزات مستخدم معين
@app.get("/user_reservations/")
def get_user_reservations(name: str, plate_number: str, session: Session = Depends(get_session)):
    user = session.exec(
        select(Users_Informations).where(
            Users_Informations.name == name, 
            Users_Informations.plate_number == plate_number
        )
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    reservations = session.exec(
        select(Parking_Reservations).where(Parking_Reservations.user_id == user.id)
    ).all()
    
    return {
        "user": {"name": user.name, "plate_number": user.plate_number},
        "reservations": reservations
    }

# 5. تحديث بيانات الملف الشخصي (Profile Update)
@app.put("/update_user/")
def update_user_info(
    password: str,
    name: str = None,
    phone_number: str = None,
    new_password: str = None,
    session: Session = Depends(get_session)
):
    user = session.exec(
        select(Users_Informations).where(Users_Informations.password == password)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if name: user.name = name
    if phone_number: user.phone_number = phone_number
    if new_password: user.password = new_password
    
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "User updated successfully", "user": user}

# 6. تعديل حجز قائم (Edit Reservation)
@app.put("/reservations/{reservation_id}")
def update_reservation(
    reservation_id: int,
    name: str = None,
    vehicle_type: ParkingType = None,
    hours: float = None,
    session: Session = Depends(get_session)
):
    reservation = session.get(Parking_Reservations, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    user = session.get(Users_Informations, reservation.user_id)
    
    if name: user.name = name
    if vehicle_type: reservation.parking_type = vehicle_type
    if hours:
        reservation.booking_hours = hours
        price = 3000 if (vehicle_type or reservation.parking_type) == ParkingType.car else 1500
        reservation.total_fee = hours * price

    qr_path = parking_system.generate_qr(reservation.id, info=f"Updated: {user.name}")
    reservation.qr_code = qr_path
    
    session.add(reservation)
    session.add(user)
    session.commit()
    
    return {
        "message": "Reservation updated",
        "user_name": user.name,
        "plate_number": user.plate_number,
        "total_fee": reservation.total_fee,
        "qr_path": qr_path
    }

# 7. تحديث الحالة (المسار الموحد لصفحة Verification Portal) - تم التعديل لإضافة تحديث الباركود
@app.put("/update_status/{reservation_id}")
def update_reservation_status(reservation_id: int, status: str, session: Session = Depends(get_session)):
    reservation = session.get(Parking_Reservations, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    # تحديث الحالة
    reservation.status = status
    
    # إعادة توليد الباركود ليعكس الحالة الجديدة (Ended/Cancelled)
    user = session.get(Users_Informations, reservation.user_id)
    qr_info = (
        f"Reservation ID: {reservation.id}\n"
        f"Status: {status}\n"
        f"Name: {user.name}\n"
        f"Plate: {user.plate_number}\n"
        f"Fee: {reservation.total_fee:,} IQD"
    )
    qr_path = parking_system.generate_qr(reservation.id, info=qr_info)
    reservation.qr_code = qr_path

    session.add(reservation)
    session.commit()
    session.refresh(reservation)
    return {"message": f"Status updated to {status}", "reservation": reservation}

# 8. إلغاء حجز (المسار المنفصل)
@app.post("/cancel_reservation/{reservation_id}")
def cancel_reservation(reservation_id: int, session: Session = Depends(get_session)):
    res = session.get(Parking_Reservations, reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Not found")
    res.status = "Cancelled"
    session.add(res)
    session.commit()
    return {"message": "Reservation cancelled"}

# 9. إنهاء حجز (المسار المنفصل)
@app.post("/end_reservation/{reservation_id}")
def end_reservation(reservation_id: int, session: Session = Depends(get_session)):
    res = session.get(Parking_Reservations, reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Not found")
    res.status = "Ended"
    session.add(res)
    session.commit()
    return {"message": "Reservation ended"}

# 10. إحصائيات الأدمن
@app.get("/admin/statistics")
def admin_statistics(admin_key: str = Query(...), session: Session = Depends(get_session)):
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized Access")
    
    all_res_active = session.exec(select(Parking_Reservations).where(Parking_Reservations.status == "booked")).all()
    total_earnings = sum(r.total_fee for r in session.exec(select(Parking_Reservations)).all())
    
    occupied = {
        "Car Parking": len([r for r in all_res_active if r.parking_type == ParkingType.car]),
        "Bike Parking": len([r for r in all_res_active if r.parking_type == ParkingType.bike]),
        "Disabled Parking": len([r for r in all_res_active if r.parking_type == ParkingType.disabled])
    }
    
    return {
        "status": "success",
        "data": {
            "total_earnings": total_earnings,
            "occupied_spots": occupied
        }
    }

# 11. تسجيل الخروج
@app.post("/logout/")
def logout(password: str = None): 
    return {"message": "Logged out successfully"}