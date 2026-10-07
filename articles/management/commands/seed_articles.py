from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from articles.models import Article

User = get_user_model()

DEMO_USERS = ["demo_alice", "demo_bob", "demo_carol"]

# (title, subtitle, description, author index)
ARTICLES = [
    ("Getting Started with Django REST Framework", "Build your first API in minutes",
     """Django REST Framework (DRF) is a powerful and flexible toolkit for building Web APIs. It sits on top of standard Django, taking the complexity out of serializing database models into JSON and handling incoming request data. For developers transitioning from traditional server-rendered Django templates, DRF offers a seamless bridge into the world of decoupled, API-driven architectures.

At its core, DRF relies on three main components: Serializers, ViewSets, and Routers. Serializers act as the translation layer, converting complex querysets into Python datatypes that can be easily rendered into JSON, while also validating incoming data. ViewSets abstract away standard CRUD logic, allowing you to handle list, create, retrieve, update, and destroy operations without writing repetitive boilerplate code.

Finally, Routers automatically wire your ViewSets to URL endpoints. This means you can scaffold a fully functional API, complete with a browsable web interface, in just a few dozen lines of code. This browsable API is one of DRF's most beloved features, allowing developers to test and interact with endpoints directly from their web browser during development.""", 0),

    ("Understanding JWT Authentication", "Stateless auth for modern APIs",
     """JSON Web Tokens (JWT) have become the industry standard for securing stateless REST APIs. Unlike traditional session-based authentication—where the server stores an active session ID in memory or a database—JWTs allow the client to prove its identity using a mathematically signed payload. This stateless nature makes scaling your backend across multiple servers significantly easier, as no server needs to keep track of who is logged in.

A JWT consists of three parts separated by dots: a Header, a Payload, and a Signature. The payload contains the 'claims' (such as the user's ID and token expiration time), which are Base64 encoded. The critical piece is the signature, generated using a secret key known only to the server. When a client sends a JWT in the Authorization header, the server simply recalculates the signature to ensure the payload hasn't been tampered with.

To mitigate security risks if a token is stolen, modern JWT implementations use a two-token system: Access Tokens and Refresh Tokens. Access tokens are short-lived (often expiring in 5 to 15 minutes) and are used for API requests. When they expire, the client silently uses a long-lived Refresh token to obtain a new Access token, keeping the user logged in while limiting the window of vulnerability.""", 0),

    ("PostgreSQL Indexing Basics", "Make your queries fast",
     """As your database grows from thousands to millions of rows, queries that used to take milliseconds can suddenly bring your application to a crawl. This happens because the database is forced to perform a 'sequential scan'—reading every single row in a table to find the ones that match your query. Database indexes solve this by maintaining a separate, highly optimized data structure.

The most common type of index is the B-Tree (Balanced Tree). It works much like the index at the back of a textbook: instead of reading the whole book to find a specific term, you look it up in the alphabetical index to find the exact page number. In PostgreSQL, adding a B-Tree index on frequently filtered or sorted columns (like user emails or creation dates) changes the search complexity from linear to logarithmic, resulting in massive speed improvements.

However, indexes are not a silver bullet. Every time you insert, update, or delete a row, PostgreSQL must also update all associated indexes. This means that while indexes drastically speed up read operations, they incur a performance penalty on write operations and consume additional disk space. The key is to use the `EXPLAIN ANALYZE` command to identify exactly which queries are slow and add indexes only where they provide a measurable benefit.""", 1),

    ("ModelViewSet vs GenericViewSet", "Choosing the right abstraction",
     """Django REST Framework provides several layers of abstraction for writing API views, ranging from highly explicit APIViews to highly magical ViewSets. For most developers building standard RESTful resources, the decision often comes down to choosing between a ModelViewSet and a GenericViewSet. Understanding the difference is crucial for maintaining a secure and intentional API surface.

A `ModelViewSet` is the quickest way to get an endpoint running. By simply assigning a queryset and a serializer class, it automatically generates the full suite of CRUD operations: `list()`, `retrieve()`, `create()`, `update()`, `partial_update()`, and `destroy()`. This is perfect for internal dashboards or resources where users need full control over the data. However, exposing all these actions by default can become a security liability if you forget to restrict access.

In contrast, `GenericViewSet` provides the base mechanics of a ViewSet (like URL routing and get_object integrations) but includes zero actions by default. To add functionality, you compose it with specific mixins. If you only want users to read data and create new records—but never delete or edit them—you would inherit from `GenericViewSet`, `CreateModelMixin`, `ListModelMixin`, and `RetrieveModelMixin`. This "opt-in" approach leads to safer, more explicit API design.""", 1),

    ("Writing Tests for Django APIs", "Confidence before every deploy",
     """Automated testing is the safety net that allows development teams to move fast without breaking things. In the context of a Django REST API, relying solely on manual testing via Postman or the browser is a recipe for regressions. Fortunately, Django provides a robust testing framework, and DRF extends it with specialized tools designed specifically for API verification.

The cornerstone of API testing in Django is the `APITestCase` class, alongside the `APIClient`. Unlike standard Django request testing, `APIClient` correctly handles JSON payloads, authentication headers, and multi-part file uploads out of the box. A typical API test will set up database fixtures, authenticate a test user, make a GET or POST request to a specific endpoint, and then assert that the returned data matches expectations.

Effective API tests should cover more than just the "happy path." You must also write tests to verify that permissions are enforced (asserting a 403 Forbidden status when an unauthenticated user tries to delete a resource) and that data validation works (asserting a 400 Bad Request when an email is formatted incorrectly). By automating these checks, you guarantee that your API contract remains stable as the codebase evolves.""", 2),

    ("Docker for Python Developers", "Reproducible environments",
     """The phrase "it works on my machine" is a symptom of inconsistent development environments. When developers use different operating systems, Python versions, and system-level libraries, code that runs perfectly on a local laptop often crashes in production. Docker solves this by packaging your application and all its dependencies into an isolated, standardized unit called a container.

For a Django project, this begins with writing a `Dockerfile`. This file acts as a blueprint, instructing Docker to start with a base Python image, set up a working directory, copy your `requirements.txt`, install dependencies, and finally copy over your application code. By using multi-stage builds and carefully ordering your Dockerfile commands, you can utilize Docker's layer caching to make subsequent rebuilds incredibly fast.

Beyond standardizing the Python environment, Docker Compose takes containerization a step further by orchestrating multiple services. With a single `docker-compose.yml` file, you can spin up your Django web container alongside a PostgreSQL database, a Redis cache, and a Celery worker. This ensures that every developer on your team, and your production server, is running the exact same infrastructure architecture.""", 2),

    ("Pagination in REST APIs", "Do not return everything at once",
     """When an API endpoint returns a list of database records, sending the entire dataset in a single response is a critical anti-pattern. If a table grows from hundreds to millions of rows, an unpaginated endpoint will consume massive amounts of server memory, slow down the database, and crash the client’s browser with a giant payload. Pagination is mandatory for scalable APIs.

Django REST Framework offers several built-in pagination styles. `PageNumberPagination` is the most common, allowing clients to request specific pages (e.g., `?page=3`). It returns the paginated data alongside metadata like the total item count and URLs for the next and previous pages. While intuitive, it can become slow on massive datasets because counting the total number of rows requires a full table scan.

For high-performance or infinite-scroll applications, `LimitOffsetPagination` and `CursorPagination` are often better choices. Cursor pagination is particularly robust; it uses a unique database index (like a timestamp) as an anchor point rather than an offset. This guarantees stable pagination even if records are added or deleted while the user is navigating the list, though it sacrifices the ability to jump directly to a specific page number.""", 0),

    ("Searching and Filtering Data", "Help users find what they need",
     """A well-designed API does more than just dump data; it allows clients to query exactly what they need. Without server-side filtering, front-end applications are forced to download entire datasets and filter them locally, which is incredibly inefficient. Django REST Framework provides a flexible architecture for parsing URL query parameters and dynamically applying them to the underlying database queries.

For exact matches and conditional logic, the third-party `django-filter` package is the industry standard. By defining a `FilterSet`, you can easily map query parameters to ORM lookups. This allows clients to construct complex queries simply by appending to the URL, such as filtering products by a price range (`?price__gte=50&price__lte=100`) or filtering articles by a specific category.

Additionally, DRF includes built-in `SearchFilter` and `OrderingFilter` backends. The `SearchFilter` enables quick full-text search across specified model fields, allowing users to find records based on keyword matching. Meanwhile, the `OrderingFilter` lets clients dictate the sorting of the returned list (e.g., `?ordering=-created_at`). Combining these filters creates a highly dynamic API surface with minimal backend code.""", 1),

    ("Python Virtual Environments with uv", "Fast dependency management",
     """For years, Python developers have relied on tools like `pip`, `venv`, and `pip-tools` to manage virtual environments and dependencies. While these tools are reliable, they can be notoriously slow, especially when resolving complex dependency trees or installing packages in CI/CD pipelines. Enter `uv`, an extremely fast Python package and project manager written in Rust.

Designed as a drop-in replacement for standard pip commands, `uv` performs dependency resolution and installation orders of magnitude faster. Because it is a single compiled binary, it doesn't require a pre-existing Python environment to bootstrap itself. You can use it to create isolated virtual environments, lock dependencies, and install packages in fractions of a second, drastically reducing wait times during development.

Beyond raw speed, modern tooling like `uv` encourages better project hygiene. It supports generating deterministic lockfiles (ensuring the exact same package versions are installed everywhere) and makes managing multiple Python versions on a single machine painless. As the Python ecosystem continues to mature, adopting Rust-based tooling is becoming a standard practice for performance-conscious teams.""", 2),

    ("Securing Your API with Permissions", "Who can do what",
     """In API development, Authentication verifies *who* the user is, while Authorization (Permissions) dictates *what* they are allowed to do. Building a secure application requires strict permission boundaries to ensure that users can only interact with data they own or are authorized to see. Django REST Framework handles this through a highly customizable permission system evaluated before any view code runs.

DRF includes several built-in permission classes for global access control. `IsAuthenticated` guarantees that anonymous users cannot access an endpoint, while `IsAdminUser` restricts access to staff members. These are easily applied to ViewSets using the `permission_classes` attribute. However, global permissions are rarely enough for complex applications; you often need to check permissions against the specific object being accessed.

This is where custom object-level permissions shine. By subclassing `BasePermission` and overriding the `has_object_permission` method, you can implement granular rules. For instance, you can create an `IsAuthorOrReadOnly` permission that allows anyone to view an article, but only permits the actual author (or an admin) to edit or delete it. This logic keeps your views clean and centralizes your security rules.""", 0),

    ("Swagger and OpenAPI Documentation", "Self-documenting APIs",
     """Writing and maintaining API documentation manually is a notoriously painful process. As your codebase evolves, handwritten documentation inevitably falls out of sync with the actual API, leading to frustrated frontend developers and broken integrations. The modern solution is to generate documentation dynamically directly from your application's code using the OpenAPI specification.

The OpenAPI schema is a standard, machine-readable JSON or YAML file that describes every endpoint, request parameter, and response payload in your API. In the Django ecosystem, the `drf-spectacular` package is the premier tool for generating this schema. It inspects your serializers, ViewSets, and type hints to automatically deduce the structure of your API, ensuring your documentation is always 100% accurate on every deploy.

Once you have an OpenAPI schema, you can serve it via a Swagger UI or Redoc web interface. Swagger UI is particularly powerful because it acts as an interactive playground. Developers, QA testers, and third-party consumers can read the endpoint descriptions, authenticate, and execute test requests directly from their browser without needing a tool like Postman. This "self-documenting" approach drastically accelerates cross-team collaboration.""", 1),

    ("Handling Errors Gracefully", "Clear messages for API clients",
     """A robust API is defined not just by how it behaves when things go right, but how it communicates when things go wrong. If an API returns standard HTML error pages or inconsistent JSON structures during a failure, frontend applications will struggle to parse the errors, resulting in broken user experiences. Graceful error handling requires strict adherence to HTTP status codes and a standardized error format.

The first rule of API error handling is using the correct HTTP status code. A `400 Bad Request` should be used for validation failures, `401 Unauthorized` when credentials are missing, `403 Forbidden` when credentials lack permission, and `404 Not Found` when a resource doesn't exist. Django REST Framework's serializers automatically handle `400` errors by returning a dictionary detailing exactly which fields failed validation and why.

For more complex applications, you often need to standardize error payloads globally. By overriding DRF's default custom exception handler, you can catch generic Python exceptions, database integrity errors, or custom application logic errors, and wrap them in a consistent JSON envelope (e.g., always returning `{"error_code": "...", "message": "..."}`). This predictability makes it much easier for frontend clients to display helpful error messages to the end user.""", 2),

    ("Database Migrations Explained", "Evolving your schema safely",
     """In a Django project, your Python models act as the definitive source of truth for your database structure. However, relational databases require explicit SQL commands (like `CREATE TABLE` or `ALTER TABLE`) to change their schemas. Django’s migration system acts as the bridge between your object-oriented Python code and the underlying SQL database, allowing you to evolve your schema safely over time.

The workflow relies on two primary commands. When you modify a model in `models.py`, you run `makemigrations`. This inspects your changes and generates a Python file (the migration) containing the instructions needed to alter the database. These files should be committed to version control so your team stays in sync. When you are ready to apply those changes to your local database or production server, you run `migrate`.

Migrations go beyond simple schema changes. They can also be used to move or transform data. By creating an empty migration and writing custom Python functions, you can write "Data Migrations" to populate new columns, sanitize existing data, or transfer records between tables before a schema change drops them. Mastering the migration system, including how to safely roll back failed migrations, is essential for maintaining production database integrity.""", 0),

    ("Optimizing Queries with select_related", "Avoid the N+1 problem",
     """The 'N+1 query problem' is the most common performance killer in Django applications. It occurs when you fetch a list of objects from the database, and then iterate through them to access a related Foreign Key object. The ORM will execute one query to get the initial list, and then 'N' additional queries for every single item in the loop. A simple page load can easily trigger hundreds of unnecessary database hits.

Django provides powerful tools to solve this, primarily `select_related` and `prefetch_related`. If you are iterating over a list of Articles and need to display the Author's username, using `Article.objects.select_related('author')` instructs PostgreSQL to perform an SQL `JOIN`. This fetches the articles and all their related authors in a single, highly efficient database round-trip, completely eliminating the N+1 issue.

Choosing the right tool depends on the relationship type. `select_related` is used for single-valued relationships (ForeignKeys and OneToOnes) because SQL joins are efficient for 1-to-1 mappings. For ManyToMany or reverse ForeignKey relationships, you use `prefetch_related`. This executes a second query and joins the data in Python, preventing the massive memory overhead that complex SQL joins can cause on multi-valued relationships.""", 1),

    ("Deploying Django to Production", "From laptop to server",
     """Taking a Django application from your local development environment and deploying it safely to a production server requires a significant shift in configuration. The built-in `runserver` command is designed for debugging; it is single-threaded, highly insecure, and completely unsuitable for handling real web traffic. A production deployment requires a robust stack of specialized services.

First, the application must be secured. This means strictly setting `DEBUG = False` to prevent sensitive stack traces from leaking to users. You must also configure `ALLOWED_HOSTS` to prevent HTTP Host header attacks, and move all secrets (database passwords, secret keys, API tokens) out of your codebase and into server Environment Variables.

To actually serve the application, Django relies on the WSGI or ASGI specification. You use an application server like Gunicorn to run multiple worker processes of your Django app, ensuring it can handle concurrent requests. Finally, you place a reverse proxy like Nginx in front of Gunicorn. Nginx acts as the gatekeeper: it handles SSL/TLS termination, prevents slow-client attacks, and efficiently serves static and media files directly from disk without bothering the Django application.""", 2),
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
        updated_count = 0

        for title, subtitle, description, idx in ARTICLES:
            # (title, author) se record dhoondta hai.
            # defaults (subtitle, description) create aur update dono mein lagte hain.
            _, created = Article.objects.update_or_create(
                title=title,
                author=users[idx],
                defaults={"subtitle": subtitle, "description": description,"is_published": True,},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} created, {updated_count} updated. "
            f"Total articles: {Article.objects.count()}."
        ))