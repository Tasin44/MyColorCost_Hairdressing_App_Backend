# 🎨 My Color Backend

![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Django REST Framework](https://img.shields.io/badge/DJANGO-REST-ff1709?style=for-the-badge&logo=django&logoColor=white&color=ff1709&labelColor=gray)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Stripe](https://img.shields.io/badge/Stripe-626CD9?style=for-the-badge&logo=Stripe&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)

> **A Comprehensive B2B2C SaaS Backend for Salons, Spas, and Retail Businesses.**

---

## 📖 Overview
**My Color Backend** is a highly scalable, multi-tenant Software-as-a-Service (SaaS) platform tailored for the beauty and retail industries. It provides a complete end-to-end ecosystem allowing business owners to manage appointments, handle payments, track clients, manage staff, sell products, and run affiliate marketing campaigns.

Built with **Django** and **Django REST Framework (DRF)**, this backend architecture is engineered for performance, security, and scalability. It handles complex business logic including role-based access control (RBAC), timezone-aware dynamic scheduling, secure financial transactions via Stripe, and real-time inventory management.

---

## ✨ Key Features & Business Value

### 🔐 1. Advanced Authentication & RBAC
- **Multi-tiered User Roles:** Custom user models supporting `Owners`, `Self-Employed` professionals, and `Staff` sub-users.
- **Secure JWT Authentication:** Stateless, highly secure token-based authentication using `djangorestframework_simplejwt`.
- **Granular Permissions:** Specific access control lists (ACL) ensuring staff members can only access authorized data.

### 📅 2. Intelligent Appointment & Scheduling Engine
- **Dynamic Booking URLs:** Auto-generates unique, shareable booking links (e.g., `/book/{token}`) for individual business owners to share with clients.
- **Smart Time-Slot Management:** Calculates 15-minute interval availability dynamically based on team size, staff capacity, and daily working hours/off days.
- **Conflict Resolution:** Prevents double-booking through robust backend validation and capacity tracking.
- **Service Customization:** Owners can define custom services, pricing (fixed, free, 'from'), and service durations.

### 💳 3. Financial & Payment Ecosystem
- **Stripe Integration:** Seamlessly processes payments and handles platform service fees.
- **Automated Invoicing & Reporting:** Utilizes `ReportLab` and `Pandas` to generate comprehensive financial reports and PDF invoices.
- **Subscription & Fee Management:** Infrastructure to handle SaaS platform fees dynamically.

### 🛍️ 4. Retail & Inventory Management
- **Barcode Scanning API Integration:** Integrates with the `Barcode Spider API` to instantly identify and categorize physical retail products.
- **E-commerce Capabilities:** Allows salon owners to sell retail products directly alongside their services.

### 🤝 5. CRM & Affiliate Marketing
- **Client Management:** Tracks client history, preferences, and automated appointment reminders.
- **Affiliate System:** Built-in tools for tracking referrals, affiliate links, and calculating commission distributions.

### ⚡ 6. High-Performance Asynchronous Operations
- **Celery & Redis:** Offloads heavy tasks such as sending automated email reminders and generating reports to background workers.
- **WebSockets (Django Channels):** Infrastructure set up for real-time notifications and updates.

---

## 🛠️ Tech Stack & Architecture

- **Core Framework:** Python 3, Django 6.0, Django REST Framework
- **Database Engine:** PostgreSQL (Production) / SQLite (Local Dev)
- **Caching & Message Broker:** Redis
- **Task Queue:** Celery
- **WebSockets:** Django Channels, Daphne
- **API Documentation:** Swagger / OpenAPI (`drf-yasg`)
- **Third-Party APIs:** Stripe (Payments), Firebase Admin, Barcode Spider API
- **Deployment & DevOps:** Docker, Docker Compose, Gunicorn, Whitenoise, Nginx

---

## 🎯 Why This Project Stands Out (For Recruiters & Engineers)

This codebase demonstrates senior-level backend engineering capabilities, highlighting:
1. **Complex Database Design:** Carefully structured relational models (`OneToOne`, `ForeignKey` constraints) that flawlessly handle edge cases like staff-capacity limits during booking.
2. **Clean Code & Best Practices:** Strict adherence to PEP 8, separation of concerns (Apps: `authapp`, `appointmentapp`, `paymentapp`, etc.), and modular design.
3. **Enterprise-Grade Security:** Environment variable management via `django-environ`/`dotenv`, secure Stripe webhooks, and rate-limiting (`django-ratelimit`).
4. **Production Readiness:** Fully containerized with `Docker` and `docker-compose`, configured for `Gunicorn` and static file serving via `Whitenoise`.

---

*This project showcases my ability to design, build, and maintain a complex, real-world SaaS architecture capable of handling concurrent users, financial transactions, and complex business logic from scratch.*
