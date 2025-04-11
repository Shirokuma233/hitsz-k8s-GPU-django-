import shutil
from datetime import datetime
import os
from django.conf import settings
from django.core.files.storage import Storage
from django.core.files import File


class NFSStorage:
    """封装NFS文件操作"""

    def __init__(self, username):
        self.base_path = os.path.join(settings.NFS_ROOT, username)
        os.makedirs(self.base_path, exist_ok=True)

    def list_files(self, relative_path):
        """列出指定目录下的文件和文件夹"""
        print(relative_path)
        target_path = os.path.join(self.base_path, relative_path)
        items = []

        for item_name in os.listdir(target_path):
            item_path = os.path.join(target_path, item_name)
            stat = os.stat(item_path)

            items.append({
                'name': item_name,
                'type': 'file' if os.path.isfile(item_path) else 'directory',
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                'size': stat.st_size if os.path.isfile(item_path) else 0,
                'path': os.path.join(relative_path, item_name)  # 关键：返回相对路径
            })

        return items

    def save_file(self, relativepath, uploaded_file):
        """保存上传文件"""
        filepath = os.path.join(self.base_path, relativepath, uploaded_file.name)
        print(filepath)
        with open(filepath, 'wb+') as dst:
            for chunk in uploaded_file.chunks():
                dst.write(chunk)
        return filepath

    def delete_file(self, relativapath):
        """删除文件"""
        filepath = os.path.join(self.base_path, relativapath)
        if os.path.isfile(filepath):
            os.remove(filepath)  # 删除单个文件
            return True
        else:
            shutil.rmtree(filepath)  # 递归删除文件夹
            return True
        return False

    def get_file(self, relativepath):
        """获取文件对象"""
        filepath = os.path.join(self.base_path, relativepath)
        print("filepath", filepath)
        if os.path.exists(filepath):
            return open(filepath, 'rb')
        return None
