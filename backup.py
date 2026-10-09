"""
سكريبت النسخ الاحتياطي التلقائي
يشتغل كل يوم - يحفظ 7 نسخ آخر
"""
import os
import shutil
import datetime

DB_PATH = "/home/Jutia/jutia/shop.db"
BACKUP_DIR = "/home/Jutia/backups"
MAX_BACKUPS = 7  # نحفظو 7 نسخ آخر

os.makedirs(BACKUP_DIR, exist_ok=True)

# اسم النسخة
date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
backup_file = os.path.join(BACKUP_DIR, f"shop_{date_str}.db")

# نسخ
shutil.copy(DB_PATH, backup_file)
print(f"✅ نسخة احتياطية: {backup_file}")
print(f"📦 الحجم: {os.path.getsize(backup_file) / 1024:.1f} KB")

# حذف النسخ القديمة (نخليو 7)
backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("shop_")])
if len(backups) > MAX_BACKUPS:
    for old in backups[:-MAX_BACKUPS]:
        os.remove(os.path.join(BACKUP_DIR, old))
        print(f"🗑️ حذف: {old}")

print(f"📊 المجموع: {len(os.listdir(BACKUP_DIR))} نسخة")
