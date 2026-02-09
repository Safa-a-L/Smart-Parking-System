# parking_system_operations.py
import qrcode
from models import ParkingType
from enum import Enum

# نوع الدفع
class PaymentType(str, Enum):
    cash = "Cash"
    electronic = "Electronic"

# نظام المواقف
class ParkingSystem:
    def __init__(self):
        # سعة المواقف لكل نوع
        self.sorts = {
            ParkingType.car: 40,
            ParkingType.bike: 20,
            ParkingType.disabled: 40,
        }
        # أسعار كل نوع موقف
        self.prices = {
            ParkingType.car: 3.0,
            ParkingType.bike: 1.5,
            ParkingType.disabled: 2.5,
        }


    # حجز موقف مع نوع الدفع

    def book_spot(self, vehicle_type: ParkingType, hours: float, payment_type: PaymentType):
        if self.sorts[vehicle_type] == 0:
            return False, f"Sorry, no {vehicle_type.value} spots available."

        self.sorts[vehicle_type] -= 1
        total_fee = hours * self.prices[vehicle_type]

        # محاكاة عملية الدفع الإلكتروني
        if payment_type == PaymentType.electronic:
            payment_status = "Paid electronically"
        else:
            payment_status = "To be paid in cash"

        return True, {"total_fee": total_fee, "payment_status": payment_status}


    # توليد QR مع معلومات الحجز

    def generate_qr(self, reservation_id: int, info: str = None):
        qr = qrcode.QRCode()
        data = f"Reservation ID: {reservation_id}"
        if info:
            data += f"\n{info}"
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image()
        # حفظ QR في مجلد qr_codes
        path = f"qr_codes/reservation_{reservation_id}.png"
        img.save(path)
        return path
    