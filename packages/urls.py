from django.urls import path
from . import views

app_name = 'packages'

urlpatterns = [
    path('', views.index, name='index'),
    path('packages/', views.package_list, name='package_list'),
    path('packages/<str:package_name>/', views.package_detail, name='package_detail'),
    path('packages/<str:package_name>/<str:version>/binaries/<str:binary_id>/download/',
         views.download_binary, name='download_binary'),
    path('packages/<str:package_name>/<str:version>/bundle/preview/',
         views.bundle_preview, name='bundle_preview'),
    path('packages/<str:package_name>/<str:version>/bundle/',
         views.download_bundle, name='download_bundle'),
    path('packages/<str:package_name>/<str:version>/manifest/',
         views.download_manifest, name='download_manifest'),
    path('topics/', views.topic_list, name='topic_list'),
    path('topics/<slug:slug>/', views.topic_detail, name='topic_detail'),
    path('download-script/', views.download_script, name='download_script'),
]
