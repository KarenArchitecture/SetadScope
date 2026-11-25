# راهنمای Docker — SetadScope

این دستورات را در **ریشه پروژه** (همان پوشه‌ای که فایل `compose.yaml` قرار دارد) و در **PowerShell** اجرا کنید.

## 1. دستورات اصلی

| عملیات                       | دستور                          |
| ---------------------------- | ------------------------------ |
| Build — ساخت Image           | `docker compose build`         |
| Start — اجرای سرویس‌ها       | `docker compose up -d`         |
| Stop — توقف بدون حذف کانتینر | `docker compose stop`          |
| Restart — راه‌اندازی مجدد    | `docker compose restart`       |
| Rebuild + Restart            | `docker compose up -d --build` |
| Down — توقف و حذف کانتینرها  | `docker compose down`          |
| Status — وضعیت سرویس‌ها      | `docker compose ps`            |
| Logs — نمایش زنده لاگ‌ها     | `docker compose logs -f`       |

## 2. آپدیت پروژه از GitHub

برای دریافت و اجرای آخرین تغییرات برنچ `UI-UX-improvement`:

```powershell
git pull origin UI-UX-improvement
docker compose up -d --build
```

> این دستور برای به‌روزرسانی نسخه اجراشده پروژه معمولاً کافی است. پیش از `git pull` مطمئن شوید روی برنچ موردنظر هستید و تغییرات ذخیره‌نشده تداخل ایجاد نمی‌کنند.

## 3. مدیریت سرویس‌های جداگانه

| عملیات               | دستور                                   |
| -------------------- | --------------------------------------- |
| Rebuild فرانت‌اند    | `docker compose up -d --build frontend` |
| Rebuild بک‌اند       | `docker compose up -d --build api`      |
| Restart فرانت‌اند    | `docker compose restart frontend`       |
| Restart بک‌اند       | `docker compose restart api`            |
| مشاهده لاگ بک‌اند    | `docker compose logs -f api`            |
| مشاهده لاگ فرانت‌اند | `docker compose logs -f frontend`       |
| مشاهده لاگ دیتابیس   | `docker compose logs -f db`             |

## 4. دستورات پیشرفته‌تر

| عملیات                                | دستور                                          |
| ------------------------------------- | ---------------------------------------------- |
| Build بدون Cache                      | `docker compose build --no-cache`              |
| دریافت Base Imageهای جدید هنگام Build | `docker compose build --pull`                  |
| ساخت مجدد اجباری کانتینرها            | `docker compose up -d --force-recreate`        |
| اجرای کانتینرهای متوقف‌شده            | `docker compose start`                         |
| مشاهده مصرف منابع کانتینرها           | `docker stats`                                 |
| مشاهده فضای اشغال‌شده توسط Docker     | `docker system df`                             |
| اجرای دستی Migration دیتابیس          | `docker compose exec api alembic upgrade head` |

## 5. تفاوت دستورات مهم

- **`docker compose build`** فقط Image می‌سازد و سرویس‌ها را اجرا نمی‌کند.
- **`docker compose up -d`** سرویس‌ها را در پس‌زمینه اجرا می‌کند و در صورت نیاز کانتینر می‌سازد؛ تغییرات سورس را لزوماً Build نمی‌کند.
- **`docker compose restart`** کانتینرهای موجود را راه‌اندازی مجدد می‌کند؛ Image جدید نمی‌سازد.
- **`docker compose up -d --build`** Imageها را در صورت نیاز بازسازی می‌کند و سرویس‌ها را با نسخه جدید اجرا می‌کند.
- **`docker compose down`** کانتینرها و شبکه Compose را حذف می‌کند، اما Volumeهای دائمی را حفظ می‌کند.

## 6. هشدار مهم: حذف داده‌های دیتابیس

**این دستور را فقط زمانی اجرا کنید که عمداً می‌خواهید Volumeهای پروژه را حذف کنید:**

```powershell
docker compose down -v
```

⚠️ دیتابیس PostgreSQL پروژه از Volume دائمی استفاده می‌کند. اجرای دستور بالا ممکن است همه داده‌های ذخیره‌شده مزایده‌ها، مناقصه‌ها و تنظیمات را حذف کند. برای خاموش کردن عادی برنامه، از `docker compose stop` یا `docker compose down` (بدون `-v`) استفاده کنید.

## 7. استفاده روزمره (خلاصه)

**پس از دریافت تغییرات جدید از GitHub:**

```powershell
git pull origin UI-UX-improvement
docker compose up -d --build
```

**برای روشن کردن پروژه بدون Build مجدد:**

```powershell
docker compose up -d
```

**برای خاموش کردن موقت پروژه:**

```powershell
docker compose stop
```

**برای بررسی خطاها:**

```powershell
docker compose ps
docker compose logs -f
```

### نکته Migration

در تنظیم فعلی `compose.yaml`، هنگام شروع سرویس `api`، دستور `alembic upgrade head` به‌طور خودکار اجرا می‌شود؛ بنابراین اجرای دستی Migration معمولاً لازم نیست.
