from django.urls import path
from .views import DashBoardAPIView, ContainerManagementCreateView, LoginResourceView, LoginValidView, file_list, \
    file_upload, file_delete, file_download, file_share_list, ContainerManagementDistributeView, get_docker_images, \
    save_pod_image, delete_pod

urlpatterns = [
    path('login/valid', LoginValidView.as_view(), name='LoginValidView'),
    path('login/resource', LoginResourceView.as_view(), name='LoginResourceView'),
    path('home/dashboard', DashBoardAPIView.as_view(), name='DashBoardAPIView'),
    path('home/image-management', get_docker_images, name='image-management'),
    path('home/container-management/create', ContainerManagementCreateView.as_view(),
         name='ContainerManagementCreateView'),
    path('home/container-management/distribute', ContainerManagementDistributeView.as_view(),
         name='ContainerManagementDistributeView'),
    path('home/container-management/save', save_pod_image, name='save_pod_image'),
    path('home/container-management/delete', delete_pod, name='delete_pod'),

    path('home/file-share', file_share_list, name='file-share-list'),
    path('home/file-management/files/list', file_list, name='file-list'),
    path('home/file-management/files/upload', file_upload, name='file-upload'),
    path('home/file-management/files/delete', file_delete, name='file-delete'),
    path('home/file-management/files/download', file_download, name='file-download'),
]
