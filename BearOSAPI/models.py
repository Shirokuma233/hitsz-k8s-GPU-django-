from django.db import models
from django.contrib.auth.models import User  # 直接使用内置 User


class UserPodAccess(models.Model):
    user = models.ForeignKey(
        User,  # 关联到内置 User 表
        on_delete=models.CASCADE,  # 用户删除时级联删除记录
        verbose_name='用户'
    )
    pod_name = models.CharField(max_length=255, verbose_name='Pod名称')
    # 新添加的字段
    status = models.CharField(
        max_length=50,
        verbose_name='状态',
        null=True,
        blank=True
    )
    start_time = models.DateTimeField(
        verbose_name='启动时间',
        null=True,
        blank=True
    )
    calculate_resource = models.CharField(
        max_length=255,
        verbose_name='计算资源',
        default='暂无GPU'
    )
    total_duration = models.IntegerField(
        verbose_name='总时长(小时)',
        null=True,
        blank=True
    )
    runtime_duration = models.IntegerField(
        verbose_name='已运行时长(小时)',
        null=True,
        blank=True
    )
    images = models.CharField(
        max_length=255,
        verbose_name='镜像环境',
        null=True,
        blank=True
    )
    ssh_port = models.IntegerField(verbose_name='SSH端口')
    ssh_ip = models.CharField(max_length=255, verbose_name='SSHip')
    ssh_password = models.CharField(max_length=255, verbose_name='SSH密码')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'k8s_pod_access'
        verbose_name = '用户Pod访问'
        verbose_name_plural = '用户Pod访问'
        unique_together = ('user', 'pod_name')  # 确保唯一性

    def __str__(self):
        return f"{self.user} -> {self.pod_name}"
