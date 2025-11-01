from django.urls import path
from . import views
from .views import upload_views, simple_upload

app_name = 'packages'

urlpatterns = [
    # Web UI
    path('', views.index, name='index'),
    path('packages/', views.package_list, name='package_list'),
    path('packages/<str:package_name>/', views.package_detail, name='package_detail'),
    path('topics/', views.topic_list, name='topic_list'),
    path('topics/<slug:slug>/', views.topic_detail, name='topic_detail'),

    # Download endpoints
    path('packages/<str:package_name>/<str:version>/binaries/<str:binary_id>/download/',
         views.download_binary, name='download_binary'),
    path('packages/<str:package_name>/<str:version>/bundle/preview/',
         views.bundle_preview, name='bundle_preview'),
    path('packages/<str:package_name>/<str:version>/bundle/',
         views.download_bundle, name='download_bundle'),
    path('packages/<str:package_name>/<str:version>/manifest/',
         views.download_manifest, name='download_manifest'),
    path('packages/<str:package_name>/<str:version>/recipe/download/',
         views.download_views.download_recipe, name='download_recipe'),
    path('packages/<str:package_name>/<str:version>/recipe/',
         views.download_views.view_recipe, name='view_recipe'),
    path('download-script/', views.download_script, name='download_script'),

    # Simple unified upload API
    path('api/package/upload', simple_upload.upload_package, name='simple_upload'),

    # Conan V2 client uses REST API v1 (confusing naming!)
    # Remote URL: /v2 -> API paths: /v2/v1/...
    path('v2/ping', upload_views.ping, name='v2_ping'),  # Conan checks this first
    path('v2/v1/ping', upload_views.ping, name='api_ping'),
    path('v2/v1/users/check_credentials', upload_views.check_credentials, name='api_check_credentials'),
    path('v2/v1/conans/<str:package_name>/<str:package_version>/upload',
         upload_views.upload_recipe, name='api_upload_recipe'),
    path('v2/v1/conans/<str:package_name>/<str:package_version>/packages/<str:package_id>/upload',
         upload_views.upload_package, name='api_upload_package'),
    path('v2/v1/conans/<str:package_name>/<str:package_version>/recipe/manifest',
         upload_views.get_recipe_manifest, name='api_recipe_manifest'),
    path('v2/v1/conans/search', upload_views.search_packages, name='api_search'),
]
