from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Article , ImportJob
from unittest.mock import patch
from django.utils import timezone
import tablib
from .importing import dataset_to_rows, rows_to_dataset
from .tasks import run_import_job
from .tasks import run_import_job as run_import_job_for_real
from django.core.files.uploadedfile import SimpleUploadedFile
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


    def test_create_defaults_to_draft(self):
        auth(self.client, self.bob)
        r = self.client.post("/articles/", self.payload)
        self.assertFalse(r.data["is_published"])


    def test_create_with_is_published_true(self):
        auth(self.client, self.bob)
        r = self.client.post("/articles/", {**self.payload, "is_published": True}, format="json")
        self.assertTrue(r.data["is_published"])


    def test_update_without_is_published_keeps_status(self):
        auth(self.client, self.alice)
        r = self.client.patch(self.url, {"title": "Changed"})
        self.assertTrue(r.data["is_published"])
    def test_put_without_is_published_keeps_status(self):
        auth(self.client, self.alice)
        r = self.client.put(self.url, self.payload, format="json")
        self.assertEqual(r.status_code, 200)
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
class ArticleExportTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="pass12345")
        cls.bob = User.objects.create_user("bob", password="pass12345")
        Article.objects.create(
            title="Pub one", subtitle="s", description="d",
            author=cls.alice, is_published=True,
        )
        Article.objects.create(
            title="Pub two", description="d", author=cls.bob, is_published=True
        )
        Article.objects.create(
            title="My draft", description="d", author=cls.alice, is_published=False
        )

    def _rows(self, response):
        return tablib.Dataset().load(response.content, format="xlsx")

    def test_export_requires_token(self):
        r = self.client.get("/articles/export/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_returns_xlsx_download(self):
        auth(self.client, self.alice)
        r = self.client.get("/articles/export/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertIn("attachment", r["Content-Disposition"])

    def test_export_has_only_published_articles(self):
        auth(self.client, self.alice)
        rows = self._rows(self.client.get("/articles/export/"))
        self.assertEqual(
            rows.headers, ["title", "subtitle", "description", "status", "author"]
        )
        self.assertEqual(sorted(rows["title"]), ["Pub one", "Pub two"])
        self.assertEqual(set(rows["status"]), {"published"})
        self.assertEqual(sorted(rows["author"]), ["alice", "bob"])

    def test_export_escapes_formulas(self):
        Article.objects.create(
            title="=1+1", description="d", author=self.alice, is_published=True
        )
        auth(self.client, self.alice)
        rows = self._rows(self.client.get("/articles/export/"))
        self.assertFalse(any(t.startswith("=") for t in rows["title"]))


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def xlsx_upload(rows, headers=("title", "subtitle", "description", "status"), name="articles.xlsx"):
    ds = tablib.Dataset(headers=list(headers))
    for row in rows:
        ds.append(row)
    return SimpleUploadedFile(name, ds.export("xlsx"), content_type=XLSX_TYPE)


class ArticleImportPreviewTests(APITestCase):
    URL = "/articles/import-preview/"

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="pass12345")
        cls.bob = User.objects.create_user("bob", password="pass12345")
        cls.mine = Article.objects.create(
            title="Mine", description="d", author=cls.alice, is_published=True
        )
        Article.objects.create(
            title="Bobs", description="d", author=cls.bob, is_published=True
        )

    def _post(self, upload):
        return self.client.post(self.URL, {"file": upload}, format="multipart")

    def test_requires_token(self):
        r = self._post(xlsx_upload([["A", "", "d", "draft"]]))
        self.assertEqual(r.status_code, 401)

    def test_preview_classifies_rows(self):
        auth(self.client, self.alice)
        r = self._post(
            xlsx_upload(
                [
                    ["Brand new", "s", "d", "published"],  # row 2: ready
                    ["Bad status", "s", "d", "pending"],  # row 3: error
                    ["Mine", "s", "d", "draft"],  # row 4: conflict
                    ["Empty status", "s", "d", None],  # row 5: ready, draft
                    ["Bobs", "s", "d", "published"],  # row 6: bob ka title, mera nahi
                ]
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data["summary"], {"total": 5, "ready": 3, "conflict": 1, "error": 1}
        )
        by_row = {row["row"]: row for row in r.data["rows"]}
        self.assertEqual(by_row[2]["result"], "ready")
        self.assertEqual(by_row[3]["result"], "error")
        self.assertIn("status", by_row[3]["messages"][0])
        self.assertEqual(by_row[4]["result"], "conflict")
        self.assertEqual(by_row[5]["result"], "ready")
        self.assertEqual(by_row[5]["status"], "draft")
        self.assertEqual(by_row[6]["result"], "ready")

    def test_preview_does_not_change_database(self):
        auth(self.client, self.alice)
        self.mine.refresh_from_db()
        before = (
            Article.objects.count(),
            self.mine.position,
            self.mine.description,
            self.mine.is_published,
        )
        r = self._post(
            xlsx_upload([["Brand new", "s", "d", "published"], ["Mine", "x", "y", "draft"]])
        )
        self.assertEqual(r.status_code, 200)
        self.mine.refresh_from_db()
        after = (
            Article.objects.count(),
            self.mine.position,
            self.mine.description,
            self.mine.is_published,
        )
        self.assertEqual(before, after)

    def test_spaces_around_title_are_ignored(self):
        auth(self.client, self.alice)
        r = self._post(xlsx_upload([["  Mine  ", "s", "d", "draft"]]))
        self.assertEqual(r.data["rows"][0]["result"], "conflict")

    def test_duplicate_title_inside_file_is_error(self):
        auth(self.client, self.alice)
        r = self._post(
            xlsx_upload([["Twin", "s", "d", "draft"], ["Twin", "s", "d", "draft"]])
        )
        self.assertEqual(
            r.data["summary"], {"total": 2, "ready": 1, "conflict": 0, "error": 1}
        )
        self.assertEqual(r.data["rows"][1]["result"], "error")
        self.assertIn("row 2", r.data["rows"][1]["messages"][0])

    def test_extra_columns_are_ignored(self):
        auth(self.client, self.alice)
        upload = xlsx_upload(
            [["Fresh", "s", "d", "draft", "alice"]],
            headers=("title", "subtitle", "description", "status", "author"),
        )
        r = self._post(upload)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["rows"][0]["result"], "ready")

    def test_rejects_non_xlsx(self):
        auth(self.client, self.alice)
        upload = SimpleUploadedFile("articles.csv", b"title\nA", content_type="text/csv")
        r = self._post(upload)
        self.assertEqual(r.status_code, 400)
        self.assertIn("file", r.data)

    def test_rejects_broken_xlsx(self):
        auth(self.client, self.alice)
        upload = SimpleUploadedFile("articles.xlsx", b"not a real excel file", content_type=XLSX_TYPE)
        r = self._post(upload)
        self.assertEqual(r.status_code, 400)

    def test_rejects_missing_columns(self):
        auth(self.client, self.alice)
        r = self._post(xlsx_upload([["A", "d"]], headers=("title", "description")))
        self.assertEqual(r.status_code, 400)
        self.assertIn("file", r.data)
    def test_several_own_articles_with_same_title_is_error(self):
        Article.objects.create(
            title="Twin", description="d", author=self.alice, is_published=True
        )
        Article.objects.create(
            title="Twin", description="d", author=self.alice, is_published=False
        )
        auth(self.client, self.alice)
        r = self._post(xlsx_upload([["Twin", "s", "d", "draft"]]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["rows"][0]["result"], "error")
        self.assertIn("more than one", r.data["rows"][0]["messages"][0])

    def test_blank_subtitle_is_accepted(self):
        auth(self.client, self.alice)
        r = self._post(xlsx_upload([["No subtitle", None, "d", "draft"]]))
        self.assertEqual(r.data["rows"][0]["result"], "ready")
    def test_preview_saves_a_job(self):
        auth(self.client, self.alice)
        r = self._post(
            xlsx_upload(
                [["Fresh", "s", "d", "published"], ["Mine", "s", "d", "draft"]],
                name="my.xlsx",
            )
        )
        self.assertEqual(r.status_code, 200)
        job = ImportJob.objects.get(pk=r.data["job_id"])
        self.assertEqual(job.user, self.alice)
        self.assertEqual(job.status, "previewed")
        self.assertEqual(job.filename, "my.xlsx")
        self.assertEqual([x["title"] for x in job.rows], ["Fresh", "Mine"])
        self.assertEqual([x["row"] for x in job.rows], [2, 3])

    def test_rejected_file_creates_no_job(self):
        auth(self.client, self.alice)
        upload = SimpleUploadedFile("articles.csv", b"title\nA", content_type="text/csv")
        r = self._post(upload)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(ImportJob.objects.count(), 0)

    def test_rows_roundtrip_through_json(self):
        ds = tablib.Dataset(headers=["title", "subtitle", "description", "status"])
        ds.append(["A", None, 123, "draft"])
        rows = dataset_to_rows(ds)
        self.assertEqual(
            rows[0],
            {"row": 2, "title": "A", "subtitle": None, "description": "123", "status": "draft"},
        )
        again = rows_to_dataset(rows)
        self.assertEqual(again.headers, ["title", "subtitle", "description", "status"])
        self.assertEqual(again[0], ("A", None, "123", "draft"))
    def test_header_names_ignore_case_and_spaces(self):
        auth(self.client, self.alice)
        upload = xlsx_upload(
            [["Fresh", "s", "d", "Published"]],
            headers=(" Title ", "SUBTITLE", "Description", "Status"),
        )
        r = self._post(upload)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["rows"][0]["result"], "ready")
        self.assertEqual(r.data["rows"][0]["status"], "published")
class ImportJobModelTests(APITestCase):
    def test_new_job_defaults(self):
        user = User.objects.create_user("jobber", password="pass12345")
        job = ImportJob.objects.create(user=user, filename="a.xlsx")
        self.assertEqual(job.status, "previewed")
        self.assertEqual(job.rows, [])
        self.assertEqual(job.update_rows, [])
        self.assertEqual(job.new_count, 0)
        self.assertIsNone(job.started_at)
        self.assertEqual(list(user.import_jobs.all()), [job])
def make_job(user, rows, update_rows=(), status="queued"):
    ds = tablib.Dataset(headers=["title", "subtitle", "description", "status"])
    for row in rows:
        ds.append(row)
    return ImportJob.objects.create(
        user=user,
        filename="t.xlsx",
        rows=dataset_to_rows(ds),
        update_rows=list(update_rows),
        status=status,
    )


class ImportRunTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="pass12345")
        cls.bob = User.objects.create_user("bob", password="pass12345")
        cls.mine = Article.objects.create(
            title="Mine", description="Original", author=cls.alice, is_published=True
        )
        cls.bobs = Article.objects.create(
            title="Bobs", description="Bob text", author=cls.bob, is_published=True
        )

    def test_ready_rows_are_created_for_the_job_owner(self):
        job = make_job(
            self.alice,
            [
                ["New pub", "s", "d", "published"],
                ["New draft", "s", "d", "draft"],
                ["No status", "s", "d", None],
            ],
        )
        run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(
            (job.new_count, job.updated_count, job.skipped_count), (3, 0, 0)
        )
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)
        pub = Article.objects.get(title="New pub")
        self.assertEqual(pub.author, self.alice)
        self.assertTrue(pub.is_published)
        self.assertEqual(pub.position, 1)
        self.assertIsNone(Article.objects.get(title="New draft").position)
        self.assertFalse(Article.objects.get(title="No status").is_published)

    def test_conflict_is_skipped_by_default(self):
        job = make_job(self.alice, [["Mine", "changed", "changed body", "draft"]])
        run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(
            (job.new_count, job.updated_count, job.skipped_count), (0, 0, 1)
        )
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.description, "Original")
        self.assertTrue(self.mine.is_published)

    def test_conflict_is_updated_when_user_chose_it(self):
        job = make_job(
            self.alice,
            [["Mine", "changed", "changed body", "draft"]],
            update_rows=[2],
        )
        run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(
            (job.new_count, job.updated_count, job.skipped_count), (0, 1, 0)
        )
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.description, "changed body")
        self.assertFalse(self.mine.is_published)
        self.assertIsNone(self.mine.position)

    def test_error_rows_are_skipped_and_the_rest_imported(self):
        job = make_job(
            self.alice,
            [
                ["Good", "s", "d", "draft"],
                ["Bad status", "s", "d", "pending"],
                ["", "s", "d", "draft"],
            ],
        )
        run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(
            (job.new_count, job.updated_count, job.skipped_count), (1, 0, 2)
        )
        self.assertTrue(Article.objects.filter(title="Good").exists())
        self.assertFalse(Article.objects.filter(title="Bad status").exists())

    def test_another_users_article_is_never_touched(self):
        job = make_job(
            self.alice, [["Bobs", "x", "y", "draft"]], update_rows=[2]
        )
        run_import_job(job.pk)
        self.bobs.refresh_from_db()
        self.assertEqual(self.bobs.description, "Bob text")
        self.assertEqual(Article.objects.filter(title="Bobs").count(), 2)
        self.assertTrue(
            Article.objects.filter(title="Bobs", author=self.alice).exists()
        )

    def test_blank_subtitle_is_saved_as_empty_string(self):
        job = make_job(self.alice, [["Blank sub", None, "d", "draft"]])
        run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(Article.objects.get(title="Blank sub").subtitle, "")

    def test_job_that_is_not_queued_is_ignored(self):
        job = make_job(
            self.alice, [["Nope", "s", "d", "draft"]], status="previewed"
        )
        run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "previewed")
        self.assertFalse(Article.objects.filter(title="Nope").exists())

    def test_failure_rolls_back_every_row(self):
        job = make_job(
            self.alice,
            [
                ["Good row", "s", "d", "draft"],
                ["Bad row", "s", "d", "pending"],
            ],
        )
        with patch("articles.importing.select_rows_to_import", return_value=job.rows):
            run_import_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIn("could not be saved", job.error_message)
        self.assertFalse(Article.objects.filter(title="Good row").exists())
class ImportJobApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="pass12345")
        cls.bob = User.objects.create_user("bob", password="pass12345")

    def _job(self, user=None, rows=None, status="previewed"):
        return make_job(
            user or self.alice,
            rows or [["Fresh", "s", "d", "published"]],
            status=status,
        )

    def _confirm(self, job, body=None):
        return self.client.post(
            f"/import-jobs/{job.pk}/confirm/", body or {}, format="json"
        )

    def test_requires_token(self):
        job = self._job()
        self.assertEqual(self.client.get(f"/import-jobs/{job.pk}/").status_code, 401)
        self.assertEqual(self._confirm(job).status_code, 401)

    def test_owner_sees_status(self):
        auth(self.client, self.alice)
        job = self._job(rows=[["A", "s", "d", "draft"], ["B", "s", "d", "draft"]])
        r = self.client.get(f"/import-jobs/{job.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "previewed")
        self.assertEqual(r.data["total_rows"], 2)

    def test_other_users_job_is_404(self):
        job = self._job(user=self.alice)
        auth(self.client, self.bob)
        self.assertEqual(self.client.get(f"/import-jobs/{job.pk}/").status_code, 404)
        self.assertEqual(self._confirm(job).status_code, 404)

    @patch("articles.import_views.run_import_job")
    def test_confirm_queues_the_task(self, mock_task):
        auth(self.client, self.alice)
        job = self._job(rows=[["A", "s", "d", "draft"], ["B", "s", "d", "draft"]])
        with self.captureOnCommitCallbacks(execute=True):
            r = self._confirm(job, {"update_rows": [3, 2, 3]})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.data["status"], "queued")
        job.refresh_from_db()
        self.assertEqual(job.update_rows, [2, 3])
        mock_task.delay.assert_called_once_with(job.pk)

    @patch("articles.import_views.run_import_job")
    def test_confirm_without_body_means_skip_conflicts(self, mock_task):
        auth(self.client, self.alice)
        job = self._job()
        with self.captureOnCommitCallbacks(execute=True):
            r = self._confirm(job)
        self.assertEqual(r.status_code, 202)
        job.refresh_from_db()
        self.assertEqual(job.update_rows, [])

    @patch("articles.import_views.run_import_job")
    def test_second_confirm_is_409(self, mock_task):
        auth(self.client, self.alice)
        job = self._job()
        with self.captureOnCommitCallbacks(execute=True):
            first = self._confirm(job)
            second = self._confirm(job)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(mock_task.delay.call_count, 1)

    @patch("articles.import_views.run_import_job")
    def test_unknown_row_number_is_rejected(self, mock_task):
        auth(self.client, self.alice)
        job = self._job()
        r = self._confirm(job, {"update_rows": [99]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("update_rows", r.data)
        job.refresh_from_db()
        self.assertEqual(job.status, "previewed")
        mock_task.delay.assert_not_called()

    def test_header_row_number_is_rejected(self):
        auth(self.client, self.alice)
        job = self._job()
        r = self._confirm(job, {"update_rows": [1]})
        self.assertEqual(r.status_code, 400)

    @patch("articles.import_views.run_import_job")
    def test_confirmed_job_runs_end_to_end(self, mock_task):
        auth(self.client, self.alice)
        job = self._job(rows=[["End to end", "s", "d", "published"]])
        with self.captureOnCommitCallbacks(execute=True):
            self._confirm(job)
        run_import_job_for_real(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(job.new_count, 1)
        self.assertTrue(Article.objects.filter(title="End to end", author=self.alice).exists())
class ImportPageTests(APITestCase):
    def test_import_page_is_served(self):
        r = self.client.get("/import/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Import articles")
        self.assertContains(r, 'id="upload-form"')

    def test_articles_page_links_to_import(self):
        r = self.client.get("/")
        self.assertContains(r, 'href="/import/"')

    def test_articles_page_has_one_summary_line(self):
        r = self.client.get("/")
        self.assertEqual(r.content.decode().count('id="summary"'), 1)