from django.urls import path
from rest_framework.routers import DefaultRouter

from .demo_views import (
    ArticleManualDemoViewSet,
    ArticleMixinDemoViewSet,
    ArticleModelDemoViewSet,
)

from .views import ArticleViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("articles-demo/model", ArticleModelDemoViewSet, basename="demo-model")
router.register("articles-demo/mixins", ArticleMixinDemoViewSet, basename="demo-mixins")
router.register("articles-demo/manual", ArticleManualDemoViewSet, basename="demo-manual")

urlpatterns = router.urls