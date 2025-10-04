# Dynamic Forms Platform

A full-stack platform for creating, managing, and submitting dynamic forms with real-time notifications and role-based access control.

## 🏗️ Architecture

This project consists of two main components:

- **Frontend** (`my-project/`) — Next.js application with Clerk authentication
- **Backend** (`backend/`) — Django REST API with Celery for async tasks

---

## 📦 Tech Stack

### Frontend
- [Next.js 15](https://nextjs.org) (React framework)
- [Clerk](https://clerk.com/) (Authentication & user management)
- [Tailwind CSS](https://tailwindcss.com/) (Styling)
- TypeScript

### Backend
- [Django 5.x](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery](https://docs.celeryproject.org/) (Background tasks)
- [Redis](https://redis.io/) (Message broker & cache)
- SQLite (default) / PostgreSQL (production)

---

## ✨ Features

- **Dynamic Form Builder** — Create custom forms with JSON schema
- **Role-Based Access Control** — Admin and client portals
- **Real-Time Notifications** — In-app and email notifications
- **File Uploads** — Support for document attachments
- **Draft & Submission Management** — Save drafts and track submissions
- **Form Analytics** — View submission statistics and completion rates
- **Async Task Processing** — Background job handling with Celery

---

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- Redis (for Celery tasks)

### Frontend Setup

1. Navigate to the frontend directory:
```sh
cd my-project

Install dependencies:

shnpm install

Create .env.local and configure environment variables:

envNEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_key
CLERK_SECRET_KEY=your_clerk_secret

Start the development server:

shnpm run dev
The app will be available at http://localhost:3000
Backend Setup

Navigate to the backend directory:

shcd backend

Create a virtual environment and activate it:

shpython -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

Install dependencies:

shpip install -r requirements.txt

Create .env file with required variables:

envSECRET_KEY=your_django_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
SENDGRID_API_KEY=your_sendgrid_key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

Run migrations:

shpython manage.py migrate

Create a superuser (optional):

shpython manage.py createsuperuser

Start the development server:

shpython manage.py runserver
The API will be available at http://localhost:8000
Celery Setup
In separate terminal windows:

Start Redis:

shredis-server

Start Celery worker:

shcd backend
celery -A config worker --loglevel=info

Start Celery beat (for scheduled tasks):

shcelery -A config beat --loglevel=info

🔐 Authentication
Clerk Integration
The platform uses Clerk for authentication:

Frontend: Clerk provides UI components and hooks (useAuth, useUser)
Backend: Validates Clerk JWT tokens via custom authentication class
User Sync: Users are automatically created in Django when they sign in via Clerk

API Authentication
All protected endpoints require a JWT token in the Authorization header:
Authorization: Bearer <clerk_jwt_token>

📡 API Reference
Forms
Method Endpoint Description Auth Required
GET/api/forms/templates/List all form templatesYes
POST/api/forms/templates/Create form templateAdmin
GET/api/forms/templates/<id>/Get form detailsYes
PATCH/api/forms/templates/<id>/Update form templateAdmin
DELETE/api/forms/templates/<id>/Delete form templateAdmin
GET/api/forms/public/List public formsYes
GET/api/forms/analytics/<id>/Get form analyticsAdmin
Submissions
Method Endpoint Description Auth Required
GET/api/forms/submissions/List submissionsYes
POST/api/forms/submissions/Create submissionYes
GET/api/forms/submissions/<id>/Get submission detailsOwner/Admin
PATCH/api/forms/submissions/<id>/Update submissionOwner/Admin
DELETE/api/forms/submissions/<id>/Delete submissionOwner/Admin
POST/api/forms/submissions/<id>/upload/Upload fileOwner/Admin
Notifications
Method Endpoint Description Auth Required
GET/api/notifications/List notificationsYes
GET/api/notifications/unread-count/Get unread countYes
POST/api/notifications/<id>/mark-read/Mark as readYes
POST/api/notifications/mark-all-read/Mark all as readYes
DELETE/api/notifications/<id>/Delete notificationYes
Users
Method   Endpoint   Description  Auth Required
GET/api/users/me/Get current user infoYes
PATCH/api/users/me/Update user profileYes

👥 User Roles
The platform supports two user roles:

Admin — Full access to all forms, submissions, and analytics
Client — Can view assigned forms and manage own submissions

To set a user as admin, update their role in Django:
pythonpython manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.get(email='admin@example.com')
>>> user.role = 'admin'
>>> user.save()

🔔 Notifications
The platform sends notifications for:

New form submissions (to admins)
Form review/approval (to submitters)
Status changes

Notifications are delivered via:

In-app notifications (real-time)
Email (via SendGrid)


🐳 Docker Deployment (Optional)
A docker-compose.yml file is included for containerized deployment:
shdocker-compose up -d
This will start:

Django application
Celery worker
Celery beat
Redis


📝 Development Notes

CORS: Configure CORS_ALLOWED_ORIGINS in Django settings for cross-origin requests
File Storage: Files are stored locally by default; configure AWS S3 for production
Database: SQLite is used for development; use PostgreSQL for production
Email: Configure SendGrid API key for email notifications


🤝 Contributing
Contributions are welcome! Please follow these steps:

Fork the repository
Create a feature branch (git checkout -b feature/amazing-feature)
Commit your changes (git commit -m 'Add amazing feature')
Push to the branch (git push origin feature/amazing-feature)
Open a Pull Request


📄 License
This project is licensed under the MIT License.