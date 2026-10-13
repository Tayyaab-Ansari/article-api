from rest_framework.routers import DefaultRouter

from .import_views import ImportJobViewSet
from .views import ArticleViewSet

router = DefaultRouter()
router.include_root_view = False
router.register("articles", ArticleViewSet, basename="article")
router.register("import-jobs", ImportJobViewSet, basename="import-job")
urlpatterns = router.urls