# Generated by Django 5.1.6 on 2025-04-12 03:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BearOSAPI', '0003_alter_userpodaccess_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpodaccess',
            name='calculate_resource',
            field=models.CharField(default='暂无GPU', max_length=255, verbose_name='计算资源'),
        ),
        migrations.AddField(
            model_name='userpodaccess',
            name='images',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='镜像环境'),
        ),
        migrations.AddField(
            model_name='userpodaccess',
            name='runtime_duration',
            field=models.IntegerField(blank=True, null=True, verbose_name='已运行时长(小时)'),
        ),
        migrations.AddField(
            model_name='userpodaccess',
            name='start_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='启动时间'),
        ),
        migrations.AddField(
            model_name='userpodaccess',
            name='status',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='状态'),
        ),
        migrations.AddField(
            model_name='userpodaccess',
            name='total_duration',
            field=models.IntegerField(blank=True, null=True, verbose_name='总时长(小时)'),
        ),
    ]
