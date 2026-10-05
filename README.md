# Articles API (Django REST Framework + PostgreSQL + JWT)

A REST API for articles with JWT authentication, built with Django REST Framework.

## Why DRF? (vs. Next.js, Rails, MERN, Spring Boot)

**Pros**
- **Batteries included.** Serializers (validation and JSON), `ModelViewSet`, routers, pagination, permissions and a browsable API come built in. Django adds the ORM, migrations, admin and a ready-made user system, so full CRUD plus authentication takes very little code. In MERN you assemble most of that yourself.
- **Secure and mature.** Django protects against SQL injection, XSS and CSRF by default, and the Python ecosystem (data, AI, scripting) makes it easy to extend the API later.
- **Fast to build and easy to read.** Convention over configuration (like Rails), but with explicit serializers and permission classes that make API behaviour clear.

**Cons**
- **Lower raw performance and concurrency** than Spring Boot (JVM) or Node.js (event loop). Async support exists but is less natural than in Node.
- **API only.** Unlike Next.js (full-stack React with server rendering) or Rails (views plus API), DRF needs a separate frontend.
- **Less strictly typed** than Spring Boot, so larger teams rely more on tests and type hints.

## Schema

| Field | Type |
| --- | --- |
| id | auto primary key |
| title | CharField(255) |
| subtitle | CharField(255), optional |
| description | TextField |
| author | ForeignKey to the custom User (built on Django's AbstractUser) |
| created_at | DateTimeField (auto) |
| updated_at | DateTimeField (auto) |

## Endpoints

| Method and URL | Auth | Action |
| --- | --- | --- |
| GET /articles/ | public | list (10 per page) |
| POST /articles/ | login | create (author = logged-in user) |
| GET /articles/{id}/ | public | retrieve |
| PUT, PATCH /articles/{id}/ | author only | update |
| DELETE /articles/{id}/ | author only | delete |
| POST /auth/register/ | public | sign up |
| POST /auth/login/ | public | get access and refresh tokens |
| POST /auth/token/refresh/ | refresh token | get a new access token |
| POST /auth/logout/ | login | blacklist the refresh token |
| GET, PATCH /auth/me/ | login | own profile |

Send the token as `Authorization: Bearer <access token>`. Access tokens last 15 minutes and refresh tokens last 7 days.

## Setup

```bash
uv sync
cp .env.example .env     # then fill in the values
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

On Windows, copy the file with `copy .env.example .env`. You need a PostgreSQL database and user matching the values in `.env`.

## Tests

```bash
uv run python manage.py test
```