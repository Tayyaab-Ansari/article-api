from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Article

User = get_user_model()


def auth(client, user):
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class ArticleCRUDTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.article = Article.objects.create(
            title="First", subtitle="Sub", description="Body", author=self.alice ,is_published=True
        )
        self.payload = {"title": "New", "subtitle": "S", "description": "D"}
        self.url = f"/articles/{self.article.id}/"

    def test_list_requires_token(self):
        r = self.client.get("/articles/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_with_token(self):
        auth(self.client, self.bob)
        r = self.client.get("/articles/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)

    def test_retrieve_requires_token(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_with_token(self):
        auth(self.client, self.bob)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["author"], "alice")

    def test_retrieve_404(self):
        auth(self.client, self.alice)
        self.assertEqual(self.client.get("/articles/9999/").status_code, 404)

    def test_invalid_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        r = self.client.get("/articles/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    
    def test_create_requires_token(self):
        r = self.client.post("/articles/", self.payload)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_sets_author_from_token(self):
        auth(self.client, self.bob)
        r = self.client.post("/articles/", {**self.payload, "author": "alice"})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["author"], "bob")

    def test_put_by_author(self):
        auth(self.client, self.alice)
        r = self.client.put(self.url, self.payload)
        self.assertEqual(r.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "New")

    def test_patch_by_author(self):
        auth(self.client, self.alice)
        r = self.client.patch(self.url, {"title": "Patched"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["description"], "Body")

    def test_non_author_cannot_update_or_delete(self):
        auth(self.client, self.bob)
        self.assertEqual(self.client.patch(self.url, {"title": "x"}).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)

    def test_delete_by_author(self):
        auth(self.client, self.alice)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Article.objects.filter(pk=self.article.id).exists())

    def test_missing_title_rejected(self):
        auth(self.client, self.alice)
        r = self.client.post("/articles/", {"description": "no title"})
        self.assertEqual(r.status_code, 400)
    def test_draft_hidden_from_other_users_list(self):
        Article.objects.create(title="Secret draft", description="x", author=self.bob, is_published=False)
        auth(self.client, self.alice)
        r = self.client.get("/articles/search/?q=Secret")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)

    def test_draft_visible_to_its_author(self):
        Article.objects.create(title="Secret draft", description="x", author=self.bob, is_published=False)
        auth(self.client, self.bob)
        r = self.client.get("/articles/search/?q=Secret")
        self.assertEqual(r.data["count"], 1)

    def test_draft_returns_404_for_other_users(self):
        draft = Article.objects.create(title="Secret draft", description="x", author=self.bob, is_published=False)
        auth(self.client, self.alice)
        self.assertEqual(self.client.get(f"/articles/{draft.id}/").status_code, 404)
class ArticleSearchTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        Article.objects.create(
            title="Docker basics", subtitle="Containers",
            description="Run apps anywhere", author=self.alice,is_published=True
        )
        Article.objects.create(
            title="JWT guide", subtitle="Tokens",
            description="Login with tokens", author=self.bob,is_published=True
        )
        auth(self.client, self.alice)

    def test_search_by_title(self):
        r = self.client.get("/articles/search/?q=docker")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["title"], "Docker basics")

    def test_search_is_case_insensitive(self):
        r = self.client.get("/articles/search/?q=DOCKER")
        self.assertEqual(r.data["count"], 1)

    def test_search_by_author_username(self):
        r = self.client.get("/articles/search/?q=bob")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["title"], "JWT guide")

    def test_search_no_match(self):
        r = self.client.get("/articles/search/?q=xyzabc")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 0)

    def test_search_requires_token(self):
        self.client.credentials()
        r = self.client.get("/articles/search/?q=docker")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)