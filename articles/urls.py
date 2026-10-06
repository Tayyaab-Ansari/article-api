
from rest_framework.routers import DefaultRouter
from .views import ArticleViewSet

router = DefaultRouter()
router.include_root_view = False
router.register("articles", ArticleViewSet, basename="article")
urlpatterns = router.urls