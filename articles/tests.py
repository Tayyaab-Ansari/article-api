from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Article
from django.test import override_settings
from unittest.mock import patch
from django.utils import timezone
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


    def test_list_is_public_and_hides_drafts(self):
        Article.objects.create(title="Hidden", description="x", author=self.bob, is_published=False)
        r = self.client.get("/articles/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)

    

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
    @override_settings(AUTO_PUBLISH_ARTICLES=True)
    def test_create_uses_env_default_true(self):
        auth(self.client, self.bob)
        r = self.client.post("/articles/", self.payload)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_published"])

    @override_settings(AUTO_PUBLISH_ARTICLES=False)
    def test_create_uses_env_default_false(self):
        auth(self.client, self.bob)
        r = self.client.post("/articles/", self.payload)
        self.assertFalse(r.data["is_published"])

    @override_settings(AUTO_PUBLISH_ARTICLES=False)
    def test_create_user_value_beats_env(self):
        auth(self.client, self.bob)
        r = self.client.post("/articles/", {**self.payload, "is_published": True}, format="json")
        self.assertTrue(r.data["is_published"])
    @override_settings(REVERT_ARTICLES_STATUS=True)
    def test_update_flips_status_when_flag_true(self):
        auth(self.client, self.alice)
        r = self.client.patch(self.url, {"title": "Changed"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_published"])

    @override_settings(REVERT_ARTICLES_STATUS=True)
    def test_update_flips_back_on_second_update(self):
        auth(self.client, self.alice)
        self.client.patch(self.url, {"title": "One"})
        r = self.client.patch(self.url, {"title": "Two"})
        self.assertTrue(r.data["is_published"])

    @override_settings(REVERT_ARTICLES_STATUS=False)
    def test_update_keeps_status_when_flag_false(self):
        auth(self.client, self.alice)
        r = self.client.patch(self.url, {"title": "Changed"})
        self.assertTrue(r.data["is_published"])

    @override_settings(REVERT_ARTICLES_STATUS=True)
    def test_update_user_value_beats_flip(self):
        auth(self.client, self.alice)
        r = self.client.patch(self.url, {"is_published": True}, format="json")
        self.assertTrue(r.data["is_published"])
    def test_delete_clears_author_before_deleting(self):
        from unittest.mock import patch

        auth(self.client, self.alice)
        calls = []
        original_save = Article.save

        def spy_save(instance, *args, **kwargs):
            calls.append(instance.author)
            return original_save(instance, *args, **kwargs)

        with patch.object(Article, "save", spy_save):
            r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(calls, [None])
        self.assertFalse(Article.objects.filter(pk=self.article.id).exists())
    def _positions(self):
        return {
            a.title: a.position
            for a in Article.objects.filter(is_published=True)
        }

    def test_new_published_article_goes_to_top(self):
        auth(self.client, self.bob)
        r = self.client.post(
            "/articles/", {**self.payload, "is_published": True}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Article.objects.get(pk=r.data["id"]).position, 1)

    def test_new_draft_has_no_position(self):
        auth(self.client, self.bob)
        r = self.client.post(
            "/articles/", {**self.payload, "is_published": False}, format="json"
        )
        self.assertIsNone(Article.objects.get(pk=r.data["id"]).position)

    def test_new_article_pushes_others_down(self):
        auth(self.client, self.bob)
        r = self.client.post(
            "/articles/", {**self.payload, "is_published": True}, format="json"
        )
        self.article.refresh_from_db()
        self.assertEqual(self.article.position, 2)

    def test_publishing_draft_moves_it_to_top(self):
        draft = Article.objects.create(
            title="D", description="x", author=self.alice, is_published=False
        )
        auth(self.client, self.alice)
        self.client.patch(f"/articles/{draft.id}/", {"is_published": True}, format="json")
        draft.refresh_from_db()
        self.assertEqual(draft.position, 1)

    def test_unpublishing_closes_gap(self):
        second = Article.objects.create(
            title="Second", description="x", author=self.alice, is_published=True
        )
        auth(self.client, self.alice)
        self.client.patch(f"/articles/{second.id}/", {"is_published": False}, format="json")
        second.refresh_from_db()
        self.article.refresh_from_db()
        self.assertIsNone(second.position)
        self.assertEqual(self.article.position, 1)

    def test_delete_closes_gap(self):
        second = Article.objects.create(
            title="Second", description="x", author=self.alice, is_published=True
        )
        auth(self.client, self.alice)
        self.client.delete(self.url)
        second.refresh_from_db()
        self.assertEqual(second.position, 1)
    @override_settings(REVERT_ARTICLES_STATUS=True)
    def test_delete_with_flag_still_closes_gap(self):
        second = Article.objects.create(
            title="Second", description="x", author=self.alice, is_published=True
        )
        auth(self.client, self.alice)
        r = self.client.delete(f"/articles/{second.id}/")
        self.assertEqual(r.status_code, 204)
        self.article.refresh_from_db()
        self.assertEqual(self.article.position, 1)
    def _make_published(self, n):
        arts = []
        for i in range(n):
            arts.append(Article.objects.create(
                title=f"A{i}", description="x", author=self.alice, is_published=True
            ))
        return arts

    def test_move_down_slides_window(self):
        # Order ab (top se): A2=1, A1=2, A0=3, First=4
        a0, a1, a2 = self._make_published(3)
        auth(self.client, self.bob)
        r = self.client.post(f"/articles/{a2.id}/move/", {"position": 3}, format="json")
        self.assertEqual(r.status_code, 200)
        for a in (a0, a1, a2, self.article):
            a.refresh_from_db()
        self.assertEqual(
            [a2.position, a1.position, a0.position, self.article.position],
            [3, 1, 2, 4],
        )

    def test_move_up_slides_window(self):
        a0, a1, a2 = self._make_published(3)
        auth(self.client, self.bob)
        r = self.client.post(f"/articles/{self.article.id}/move/", {"position": 2}, format="json")
        self.assertEqual(r.status_code, 200)
        for a in (a0, a1, a2, self.article):
            a.refresh_from_db()
        self.assertEqual(
            [a2.position, self.article.position, a1.position, a0.position],
            [1, 2, 3, 4],
        )

    def test_move_requires_token(self):
        r = self.client.post(f"/articles/{self.article.id}/move/", {"position": 1}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_move_out_of_range(self):
        auth(self.client, self.bob)
        r = self.client.post(f"/articles/{self.article.id}/move/", {"position": 99}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_move_draft_rejected(self):
        draft = Article.objects.create(title="D", description="x", author=self.alice, is_published=False)
        auth(self.client, self.alice)
        r = self.client.post(f"/articles/{draft.id}/move/", {"position": 1}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_move_works_on_others_article(self):
        auth(self.client, self.bob)
        r = self.client.post(f"/articles/{self.article.id}/move/", {"position": 1}, format="json")
        self.assertEqual(r.status_code, 200)
    @patch("articles.views.generate_ai_summary")
    def test_ai_summary_queues_task(self, mock_task):
        auth(self.client, self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(f"/articles/{self.article.id}/ai-summary/")
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.data["summary_status"], "pending")
        mock_task.delay.assert_called_once_with(self.article.id)

    @patch("articles.views.generate_ai_summary")
    def test_ai_summary_not_requeued_while_pending(self, mock_task):
        auth(self.client, self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/articles/{self.article.id}/ai-summary/")
            self.client.post(f"/articles/{self.article.id}/ai-summary/")
        self.assertEqual(mock_task.delay.call_count, 1)

    def test_ai_summary_rejects_draft(self):
        draft = Article.objects.create(
            title="D", description="x", author=self.alice, is_published=False
        )
        auth(self.client, self.alice)
        r = self.client.post(f"/articles/{draft.id}/ai-summary/")
        self.assertEqual(r.status_code, 400)

    def test_ai_summary_requires_token(self):
        r = self.client.post(f"/articles/{self.article.id}/ai-summary/")
        self.assertEqual(r.status_code, 401)
    def test_edit_summary_by_any_logged_in_user(self):
        auth(self.client, self.bob)
        r = self.client.patch(
            f"/articles/{self.article.id}/summary/",
            {"ai_summary": "My own summary"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["ai_summary"], "My own summary")
        self.assertEqual(r.data["summary_status"], "done")

    def test_edit_summary_rejects_empty(self):
        auth(self.client, self.bob)
        r = self.client.patch(
            f"/articles/{self.article.id}/summary/",
            {"ai_summary": "   "},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_edit_summary_rejects_draft(self):
        draft = Article.objects.create(
            title="D", description="x", author=self.alice, is_published=False
        )
        auth(self.client, self.alice)
        r = self.client.patch(
            f"/articles/{draft.id}/summary/", {"ai_summary": "x"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_edit_summary_blocked_while_pending(self):
        Article.objects.filter(pk=self.article.id).update(
            summary_status="pending", summary_requested_at=timezone.now()
        )
        auth(self.client, self.bob)
        r = self.client.patch(
            f"/articles/{self.article.id}/summary/",
            {"ai_summary": "x"},
            format="json",
        )
        self.assertEqual(r.status_code, 409)

    def test_edit_summary_requires_token(self):
        r = self.client.patch(
            f"/articles/{self.article.id}/summary/",
            {"ai_summary": "x"},
            format="json",
        )
        self.assertEqual(r.status_code, 401)

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


    def test_search_default_mode_is_contains(self):
        r = self.client.get("/articles/search/?q=docker")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)

    def test_search_explicit_contains_mode(self):
        r = self.client.get("/articles/search/?q=docker&mode=contains")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)

    def test_search_empty_mode_falls_back_to_default(self):
        r = self.client.get("/articles/search/?q=docker&mode=")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)

    def test_search_invalid_mode_returns_400(self):
        r = self.client.get("/articles/search/?q=docker&mode=abc")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mode", r.data)

    def test_search_contains_hides_other_users_drafts(self):
        Article.objects.create(
            title="Docker secret draft", description="x", author=self.bob, is_published=False
        )
        r = self.client.get("/articles/search/?q=secret&mode=contains")
        self.assertEqual(r.data["count"], 0)
    def test_fulltext_finds_stemmed_word(self):
        Article.objects.create(
            title="Deploying apps", description="Notes", author=self.alice, is_published=True
        )
        r = self.client.get("/articles/search/?q=deployment&mode=fulltext")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["title"], "Deploying apps")

    def test_fulltext_title_ranks_above_description(self):
        Article.objects.create(
            title="Misc", description="a long note about docker usage", author=self.alice, is_published=True
        )
        r = self.client.get("/articles/search/?q=docker&mode=fulltext")
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(r.data["results"][0]["title"], "Docker basics")

    def test_fulltext_hides_other_users_drafts(self):
        Article.objects.create(
            title="Docker secret draft", description="x", author=self.bob, is_published=False
        )
        r = self.client.get("/articles/search/?q=secret&mode=fulltext")
        self.assertEqual(r.data["count"], 0)

    def test_fulltext_empty_query_returns_all_visible(self):
        r = self.client.get("/articles/search/?mode=fulltext")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 2)
    def test_fuzzy_finds_typo(self):
        r = self.client.get("/articles/search/?q=dokcer&mode=fuzzy")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["title"], "Docker basics")

    def test_fuzzy_no_match(self):
        r = self.client.get("/articles/search/?q=xyzabc&mode=fuzzy")
        self.assertEqual(r.data["count"], 0)

    def test_fuzzy_hides_other_users_drafts(self):
        Article.objects.create(
            title="Dokcer secret draft", description="x", author=self.bob, is_published=False
        )
        r = self.client.get("/articles/search/?q=secret&mode=fuzzy")
        self.assertEqual(r.data["count"], 0)

    def test_search_is_public(self):
        self.client.credentials()
        r = self.client.get("/articles/search/?q=docker")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1) 
