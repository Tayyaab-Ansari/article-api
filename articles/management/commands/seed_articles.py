from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from articles.models import Article

User = get_user_model()

DEMO_USERS = ["demo_alice", "demo_bob", "demo_carol"]

# (title, subtitle, description, author index)
ARTICLES = [
    ("Getting Started with Django REST Framework", "Build your first API in minutes",
     "Django REST Framework makes it easy to build Web APIs. This guide covers serializers, viewsets and routers step by step.", 0),
    ("Understanding JWT Authentication", "Stateless auth for modern APIs",
     "JSON Web Tokens let a client prove who it is without server-side sessions. We look at access tokens, refresh tokens and expiry.", 0),
    ("PostgreSQL Indexing Basics", "Make your queries fast",
     "Indexes speed up reads at the cost of writes. Learn when to add a B-tree index and how to read EXPLAIN output.", 1),
    ("ModelViewSet vs GenericViewSet", "Choosing the right abstraction",
     "ModelViewSet gives you full CRUD out of the box, while GenericViewSet with mixins lets you expose only the actions you need.", 1),
    ("Writing Tests for Django APIs", "Confidence before every deploy",
     "APITestCase, the test client and token helpers make it simple to verify permissions, validation and status codes.", 2),
    ("Docker for Python Developers", "Reproducible environments",
     "Containers remove the works on my machine problem. This article shows a minimal Dockerfile for a Django project.", 2),
    ("Pagination in REST APIs", "Do not return everything at once",
     "PageNumberPagination splits large result sets into pages. We explain page size, next and previous links, and total count.", 0),
    ("Searching and Filtering Data", "Help users find what they need",
     "SearchFilter and OrderingFilter in Django REST Framework allow keyword search and sorting through simple query parameters.", 1),
    ("Python Virtual Environments with uv", "Fast dependency management",
     "uv is a fast Python package manager. Learn how to create environments, add dependencies and run commands with it.", 2),
    ("Securing Your API with Permissions", "Who can do what",
     "Permissions such as IsAuthenticated and custom object-level checks make sure only authors can edit or delete their own articles.", 0),
    ("Swagger and OpenAPI Documentation", "Self-documenting APIs",
     "drf-spectacular generates an OpenAPI schema and a Swagger UI so your team can explore and test every endpoint.", 1),
    ("Handling Errors Gracefully", "Clear messages for API clients",
     "Consistent status codes and error bodies make your API easier to consume. We cover validation errors, 401 and 403.", 2),
    ("Database Migrations Explained", "Evolving your schema safely",
     "Migrations track model changes over time. Learn makemigrations, migrate and how to roll back when something goes wrong.", 0),
    ("Optimizing Queries with select_related", "Avoid the N+1 problem",
     "Fetching related objects in a single query reduces database round trips and keeps list endpoints fast.", 1),
    ("Deploying Django to Production", "From laptop to server",
     "Use environment variables, disable DEBUG, configure allowed hosts and serve the app with a production WSGI server.", 2),
]


class Command(BaseCommand):
    help = "Seed demo users and sample articles (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="DemoPass123!",
                            help="Password for the demo users (development only).")
        parser.add_argument("--clear", action="store_true",
                            help="Delete articles written by the demo users first.")

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Article.objects.filter(author__username__in=DEMO_USERS).delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} demo article(s)."))

        users = []
        for name in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=name, defaults={"email": f"{name}@example.com"}
            )
            if created:
                user.set_password(options["password"])
                user.save()
            users.append(user)

        created_count = 0
        for title, subtitle, description, idx in ARTICLES:
            _, created = Article.objects.get_or_create(
                title=title,
                author=users[idx],
                defaults={"subtitle": subtitle, "description": description},
            )
            created_count += created

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} new article(s); total articles: {Article.objects.count()}."
        ))