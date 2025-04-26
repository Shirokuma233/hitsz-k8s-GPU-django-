import json
import os
from django.conf import settings
import subprocess
from datetime import datetime
from .utils.storage import NFSStorage
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse, FileResponse
from kubernetes import client, config
from BearOSAPI.models import UserPodAccess
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
import requests

# 加载 kube config（如果是集群外）
config.load_kube_config()
# 如果应用运行在集群内，则使用下面这一行代替上面一行
# config.load_incluster_config()
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()


class LoginValidView(APIView):
    """
    使用 Django auth_user 表验证用户名密码
    请求示例：
    POST /login/valid
    {
        "username": "your_username",
        "password": "your_password"
    }
    """

    def post(self, request):
        try:
            # 解析 JSON 数据
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            print(username)
            print(password)

            # 验证用户凭证
            user = authenticate(username=username, password=password)

            if user is not None:
                # 验证成功
                return Response(
                    {
                        "success": True,
                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "email": user.email,
                            "is_staff": user.is_staff
                        }
                    },
                    status=status.HTTP_200_OK
                )
            else:
                # 验证失败
                return Response(
                    {"error": "用户名或密码错误"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        except json.JSONDecodeError:
            return Response(
                {"error": "无效的JSON数据"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"服务器错误: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LoginResourceView(APIView):
    def create_nfs_directory(self, uid):
        try:
            # 在 NFS 服务器上创建目录
            subprocess.run(
                ["mkdir", "-p", f"/nfs/users/{uid}"], check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"创建目录失败: {e}")
            return False

    def post(self, request):
        data = json.loads(request.body)
        uid = data.get("username")
        # 1. 检查 PV 是否存在
        pv_name = f"pv-user-{uid}"
        pv_exists = True
        try:
            v1.read_persistent_volume(pv_name)
        except client.ApiException as e:
            if e.status == 404:
                pv_exists = False
            else:
                return Response(
                    {"error": f"检查PV时发生错误: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # 2. 如果 PV 不存在则创建
        if not pv_exists and self.create_nfs_directory(uid):
            try:
                # 创建 PV
                pv_manifest = {
                    "apiVersion": "v1",
                    "kind": "PersistentVolume",
                    "metadata": {
                        "name": pv_name,
                        "labels": {"user": uid}
                    },
                    "spec": {
                        "capacity": {"storage": "5Gi"},
                        "accessModes": ["ReadWriteMany"],
                        "persistentVolumeReclaimPolicy": "Retain",
                        "storageClassName": f"storage-user-{uid}",
                        "nfs": {
                            "path": f"/nfs/users/{uid}",
                            "server": f"{settings.NFS_SERVER}"
                        }
                    }
                }
                v1.create_persistent_volume(body=pv_manifest)
            except client.ApiException as e:
                return Response(
                    {"error": f"创建存储资源pv失败: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # 3. 检查 PVC 是否存在
        pvc_name = f"pvc-user-{uid}"
        pvc_exists = True
        try:
            v1.read_namespaced_persistent_volume_claim(pvc_name, "container-management")
        except client.ApiException as e:
            if e.status == 404:
                pvc_exists = False
            else:
                return Response(
                    {"error": f"检查PVC时发生错误: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # 4. 如果 PVC 不存在则创建
        if not pvc_exists:
            try:
                pvc_manifest = {
                    "apiVersion": "v1",
                    "kind": "PersistentVolumeClaim",
                    "metadata": {
                        "name": pvc_name,
                        "labels": {"user": uid}
                    },
                    "spec": {
                        "storageClassName": f"storage-user-{uid}",
                        "accessModes": ["ReadWriteMany"],
                        "resources": {
                            "requests": {"storage": "5Gi"}
                        },
                        "selector": {
                            "matchLabels": {"user": uid}
                        }
                    }
                }
                v1.create_namespaced_persistent_volume_claim(
                    namespace="container-management",
                    body=pvc_manifest
                )
            except client.ApiException as e:
                return Response(
                    {"error": f"创建存储资源pvc失败: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # 返回成功响应
        return Response(
            {
                "message": "资源检查/创建完成",
                "pv_created": not pv_exists,
                "pvc_created": not pvc_exists,
            },
            status=status.HTTP_200_OK
        )


class DashBoardAPIView(APIView):

    def get(self, request):

        nodes = v1.list_node()
        # 获取所有命名空间中的所有 Pods
        pods = v1.list_pod_for_all_namespaces(watch=False)
        total = {'gpu_capacity': 0, 'gpu_allocatable': 0, 'cpu_capacity': 0, 'cpu_allocatable': 0, 'memory_capacity': 0,
                 'memory_allocatable': 0, 'task': len(pods.items)}
        nodes_info = []
        for idx, node in enumerate(nodes.items):
            node_name = node.metadata.name
            cpu_capacity = node.status.capacity['cpu']
            memory_capacity = node.status.capacity['memory']
            capacity = node.status.capacity
            gpu_capacity = capacity.get('nvidia.com/gpu', 0)
            
            cpu_allocatable = node.status.allocatable['cpu']
            memory_allocatable = node.status.allocatable['memory']
            allocatable = node.status.allocatable
            gpu_allocatable = allocatable.get('nvidia.com/gpu', 0)
            ready_condition = next((condition for condition in node.status.conditions if condition.type == "Ready"),
                                   None)

            # 处理 GPU 资源
            if gpu_capacity != 0:
                total['gpu_capacity'] += int(gpu_capacity)
                total['gpu_allocatable'] += int(gpu_allocatable)

            # 处理 CPU 资源，单位可能是毫核(milliCPU)
            total['cpu_capacity'] += int(cpu_capacity)
            total['cpu_allocatable'] += int(cpu_allocatable)

            # 处理内存资源，单位可能是Ki、Mi或Gi，这里转换为GB
            def convert_to_GB(memory_str):
                if memory_str.endswith('Ki'):
                    return int(memory_str[:-2]) // (1024 * 1024)
                elif memory_str.endswith('Mi'):
                    return int(memory_str[:-2]) // 1024
                elif memory_str.endswith('Gi'):
                    return int(memory_str[:-2])
                else:
                    raise ValueError(f"Unsupported memory unit: {memory_str}")

            total['memory_capacity'] += convert_to_GB(memory_capacity)
            total['memory_allocatable'] += convert_to_GB(memory_allocatable)

            node_info = {
                "nodeId": idx + 1,
                "nodeName": node_name,
                "gpuType": "无" if gpu_capacity == 0 else "T4",
                "gpuCapacity": int(gpu_capacity),
                "gpuAllocatable": int(cpu_allocatable),
                "cpuCapacity": int(cpu_capacity),
                "cpuAllocatable": int(cpu_allocatable),
                "memoryCapacity": convert_to_GB(memory_capacity),  # 转换为GiB
                "memoryAllocatable": convert_to_GB(memory_allocatable),  # 转换为GiB
                "nodeStatus": '在线' if ready_condition.status == 'True' else '离线'
            }
            nodes_info.append(node_info)

        response_data = {
            "total": total,
            "nodes_info": nodes_info
        }
        print(response_data)
        return JsonResponse(response_data)

# 镜像仓库部分
def calculate_size(manifest):
    # 计算镜像层总大小（字节转MB/GB）
    layers = manifest.get('layers', [])
    total_size = sum(layer.get('size', 0) for layer in layers)
    return f'{total_size // 1024 // 1024}MB' if total_size else ''

def get_docker_images(request):
    try:
        # 1. 获取所有镜像名称
        catalog_url = f'{settings.DOCKER_REGISTRY_URL}/v2/_catalog'
        catalog_res = requests.get(catalog_url)
        catalog_res.raise_for_status()
        images = catalog_res.json().get('repositories', [])
        print(images)

        # 2. 获取每个镜像的标签信息
        result = []
        for image in images:
            tags_url = f'{settings.DOCKER_REGISTRY_URL}/v2/{image}/tags/list'
            tags_res = requests.get(tags_url)
            tags_res.raise_for_status()
            tags = tags_res.json().get('tags', [])

            for tag in tags:
                # 3. 获取镜像详情（可选）
                manifest_url = f'{settings.DOCKER_REGISTRY_URL}/v2/{image}/manifests/{tag}'
                manifest_res = requests.get(manifest_url)
                manifest_res.raise_for_status()
                size = calculate_size(manifest_res.json())  # 计算镜像大小

                result.append({
                    'title': image,
                    'tag': f'tag:{tag}',
                    'date': datetime.now().strftime('最近使用时间：%Y-%m-%d %H:%M:%S'),
                    'note': 'Auto commit before container finishing',
                    'size': size,
                })

        return JsonResponse({
            "totalEnvs": result,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



class ContainerManagementCreateView(APIView):

    def create_timed_pod(self, user, pod_name, password, image, gpu_resource="暂无", gpu_count=1, activeDeadlineSeconds=3600,cpu_limit="2",
                         memory_limit="1Gi"):
        # 加载Kubernetes配置
        config.load_kube_config()

        # 创建API客户端
        api = client.CoreV1Api()

        try:
            # Pod定义
            pod_manifest = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": pod_name,
                    "labels": {
                        "user": user,
                        "app": f"ssh-{pod_name}",  # 必须与Service的selector匹配
                    }
                },
                "spec": {
                    "restartPolicy": "Never",
                    "activeDeadlineSeconds": activeDeadlineSeconds,
                    "containers": [{
                        "name": "ssh-container",
                        "image": "lnterface/ubuntu-ssh",
                        "ports": [{"containerPort": 22}],
                        "resources": {  # 关键改动：添加 GPU 资源请求
                            "limits": {
                                # "nvidia.com/gpu" : 0,
                                "cpu": cpu_limit,  
                                "memory": memory_limit,  
                            },
                            "requests": {
                                # "nvidia.com/gpu" : 0,
                                "cpu": cpu_limit,  
                                "memory": memory_limit,  
                            }
                        },
                        "volumeMounts": [  # volumeMounts 部分
                            {
                                "name": "user-volume",
                                "mountPath": "/workspace"  # 容器内的挂载路径
                            }
                        ]
                    }],
                    "volumes": [  # volumes 部分
                        {
                            "name": "user-volume",
                            "persistentVolumeClaim": {
                                "claimName": f"pvc-user-{user}"
                            }
                        }
                    ],

                }
            }
            # 创建Pod
            pod = api.create_namespaced_pod(
                namespace="container-management",
                body=pod_manifest
            )
            print(f"Pod创建成功: {pod.metadata.name}")
            # 创建Service

            # service for ssh
            service_manifest = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": f"svc-{pod_name}",
                             "ownerReferences": [{
                                 "apiVersion": "v1",
                                 "kind": "Pod",
                                 "name": pod_name,
                                 "uid": pod.metadata.uid  # 关键：引用Pod的UID
                             }]
                             },
                "spec": {
                    "selector": {
                        "user": user,
                        "app": f"ssh-{pod_name}",  # 必须与Service的selector匹配
                    },
                    "externalTrafficPolicy": "Cluster",
                    "ports": [{
                        "protocol": "TCP",
                        "port": 22,
                        "targetPort": 22,
                    }],
                    "type": "NodePort"
                }
            }
            service = api.create_namespaced_service(
                namespace="container-management",
                body=service_manifest
            )
            ssh_port = service.spec.ports[0].node_port
            print(f"Service创建成功，NodePort: {ssh_port}")

            # 获取节点IP, 并存入数据库
            nodes = api.list_node()
            ssh_ip = nodes.items[0].status.addresses[0].address

            # 4. 获取或创建用户

            db_user = User.objects.get(username=user)

            # 5. 存储到数据库
            UserPodAccess.objects.update_or_create(
                user=db_user,
                pod_name=pod_name,
                defaults={
                    'ssh_port': ssh_port,
                    'ssh_ip': ssh_ip,
                    'ssh_password': password,
                    'status': "排队中",  # 新字段
                    'start_time': datetime.now(),  # 新字段（确保是datetime对象）
                    'calculate_resource': f"{gpu_resource} * {gpu_count}卡",  # 新字段
                    'total_duration': activeDeadlineSeconds // 3600,  # 新字段
                    'runtime_duration': 0,  # 新字段
                    'images': image  # 新字段
                }
            )

            print(f"\nSSH连接命令:")
            print(f"ssh -p {ssh_port} root@{ssh_ip}")
            return ssh_port, ssh_ip
        except client.ApiException as e:
            print(f"创建Pod失败: {str(e)}")
            raise

    def get_pods_info(self, user):

        namespace = "container-management"
        label_selector = f"user={user}"
        ret = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        pods_info = []
        for pod in ret.items:
            start_time = pod.status.start_time

            # 如果Pod已经开始运行，则计算运行时长
            if start_time:
                current_time = datetime.now(start_time.tzinfo)  # 确保使用相同的时区
                runtime_seconds = (current_time - start_time).total_seconds()  # 计算已运行时长（秒）
                runtime_hours = runtime_seconds // 3600
            else:
                runtime_hours = 0

            # 获取镜像环境
            images = str([container.image for container in pod.spec.containers] if pod.spec.containers else [])

            active_deadline_seconds = int(pod.spec.active_deadline_seconds) if pod.spec.active_deadline_seconds else 0
            display_status = "排队中"
            if pod.status.phase == "Succeeded" or pod.status.phase == "Failed":
                display_status = "已完成"
            elif pod.status.phase == "Running":
                display_status = "运行中"

            # 5. 及时更新内容存储到数据库
            UserPodAccess.objects.update_or_create(
                user__username=user,
                pod_name=pod.metadata.name,
                defaults={
                    'status': display_status,  # 新字段
                    'runtime_duration': runtime_hours,  # 新字段
                }
            )
            # 更新完后从数据库中获取这些内容
            db_info = None  # 初始化
            try:
                db_info = UserPodAccess.objects.get(
                    user__username=user,
                    pod_name=pod.metadata.name
                )
                print(f"找到访问信息: {db_info.ssh_ip}:{db_info.ssh_port}")
            except UserPodAccess.DoesNotExist:
                print(f"用户 {user} 的 Pod {pod.metadata.name} 无访问记录")
            except Exception as e:
                print(f"查询出错: {str(e)}")

            pod_info = {
                "name": db_info.pod_name,
                "status": db_info.status,
                "startTime": db_info.start_time,
                "calculateResource": db_info.calculate_resource,
                "totalDuration": db_info.total_duration,
                "runtimeDuration": db_info.runtime_duration,  # 已运行时长（h）
                "images": db_info.images,  # 镜像环境
                "operation": [
                    {
                        "action": "ssh",
                        "label": "SSH",
                        "tooltip": {
                            "command": f'ssh -p {db_info.ssh_port} root@{db_info.ssh_ip}',
                            "password": f'{db_info.ssh_password}'
                        }
                    },
                    {
                        "action": "menu",
                        "label": "更多操作",
                        "menuItems": [
                            {"action": 'save', "label": '保存容器'},
                            {"action": 'restart', "label": '重启容器'},
                            {"action": 'delete', "label": '删除容器'}
                        ]
                    },
                    {
                        "action": "deleteFinished",
                        "label": "删除",
                    }
                ]
            }
            pods_info.append(pod_info)

        return pods_info

    def get(self, request):
        print(request.GET.get('username'))
        tasks = self.get_pods_info(request.GET.get('username'))
        running_tasks = []
        finished_tasks = []
        for task in tasks:
            if task["status"] == "已完成":
                finished_tasks.append(task)
            else:
                running_tasks.append(task)
        pods_info = {
            "runningTask": running_tasks,
            "finishedTask": finished_tasks,
        }
        print(pods_info)
        return JsonResponse(pods_info)

    def post(self, request):
        data = json.loads(request.body)
        assigned_port, node_ip = self.create_timed_pod(data.get('username'), data.get('pod_name'), data.get('password'),
                                                       data.get('imageEnvironment'),data.get('gpuResource'), data.get('gpuCount'),
                                                       data.get('runtime') * 3600, )
        return JsonResponse({
            "status": "success",
            "ssh": f"ssh -p {assigned_port} root@{node_ip}"
        })


class ContainerManagementDistributeView(APIView):

    def create_mpi_job(
            self,user_name="bear",job_name="test",launcher_image="", 
            args="",worker_replicas=1,slot_per_worker=1,gpu="",cpu_limit="8",  
    ):
        # 加载kubeconfig配置
        config.load_kube_config()

        np_num = worker_replicas * slot_per_worker
        # 默认MPI命令参数
        default_mpirun_args = [
            "--allow-run-as-root",
            "-np", f"{np_num}",
            "-bind-to", "none",
            "-map-by", "slot",
            "-x", "PATH"
        ]

        args_list = args.split()  # 按空格拆分成列表，如 "--hostfile hosts.txt" → ["--hostfile", "hosts.txt"]
        # 合并用户自定义参数
        final_args = default_mpirun_args + (args_list if args_list else [])

        # 构建MPIJob对象
        mpi_job = {
            "apiVersion": "kubeflow.org/v2beta1",
            "kind": "MPIJob",
            "metadata": {"name": job_name},
            "spec": {
                "slotsPerWorker": slot_per_worker,
                "runPolicy": {"cleanPodPolicy": "Running"},
                "mpiReplicaSpecs": {
                    "Launcher": {
                        "replicas": 1,
                        "template": {
                            "spec": {
                                "containers": [{
                                    "name": "launcher",
                                    "image": launcher_image,
                                    "command": ["mpirun"] + final_args,
                                    "resources": {
                                        "limits": {"cpu": cpu_limit},
                                        "requests": {"cpu": cpu_request}
                                    }
                                }]
                            }
                        }
                    },
                    "Worker": {
                        "replicas": worker_replicas,
                        "template": {
                            "spec": {
                                "containers": [{
                                    "name": "worker",
                                    "image": worker_image,
                                    "resources": {
                                        "limits": {"cpu": cpu_limit},
                                        "requests": {"cpu": cpu_request}
                                    }
                                }]
                            }
                        }
                    }
                }
            }
        }

        print(mpi_job)

        # 创建MPIJob
        try:
            custom_api = client.CustomObjectsApi()
            mpi_job = custom_api.create_namespaced_custom_object(
                group="kubeflow.org",
                version="v2beta1",
                plural="mpijobs",
                namespace="container-management",  # 指定namespace
                body=mpi_job
            )

            db_user = User.objects.get(username=user_name)
            # 5. 存储到数据库
            UserPodAccess.objects.update_or_create(
                user=db_user,
                pod_name=job_name,
                defaults={
                    'ssh_port': 0,
                    'ssh_ip': "",
                    'ssh_password': "",
                    'status': "排队中",  # 新字段
                    'start_time': datetime.now(),  # 新字段（确保是datetime对象）
                    'calculate_resource': gpu,  # 新字段
                    'total_duration': 0,  # 新字段
                    'runtime_duration': 0,  # 新字段
                    'images': worker_image  # 新字段
                }
            )

            return mpi_job

        except client.ApiException as e:
            print(f"创建mpi_job失败: {str(e)}")
            raise

    def post(self, request):
        data = json.loads(request.body)
        job = self.create_mpi_job(data.get('username'), data.get('pod_name'), data.get('imageEnvironment'),
                                  data.get('imageEnvironment'), data.get('param'), data.get('workerReplicas'),
                                  data.get('slotPerWorker'), data.get('gpuResource')
                                  )
        return JsonResponse({
            "status": "success",
        })

# 保存、重启、删除容器相关
# 保存image
def save_pod_image(request):
    data = json.loads(request.body)
    pod_name = data.get('podName')
    namespace = data.get('namespace')
    
    try:
        # 1. 获取 Pod 所在节点信息
        config.load_kube_config()
        core_api = client.CoreV1Api()
        pod = core_api.read_namespaced_pod(pod_name, namespace)
        worker_node = pod.spec.node_name
        
        # 2. 在 Worker 节点执行 commit & push
        registry_address = f"{settings.MASTER}:5000"  # 主节点镜像仓库地址
        image_name = f"{registry_address}/{pod_name}:latest"
        
        # 通过 SSH 在 Worker 节点执行命令
        ssh_cmd = f"""
        pod_id=$(docker ps | grep {pod_name} | awk '{{print $1}}')
        docker commit $pod_id {image_name}
        docker push {image_name}
        """
        
        result = subprocess.run(
            f'ssh {worker_node} "{ssh_cmd}"',
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return JsonResponse({
                "status": "success",
                "image": image_name
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": result.stderr
            }, status=500)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


# 删除pod
def delete_pod(request):
    data = json.loads(request.body)
    pod_name = data.get('podName')
    namespace = data.get('namespace')
    print(pod_name)
    print(namespace)
    
    if not pod_name or not namespace:
        return JsonResponse({
            "status": "error",
            "message": "podName and namespace are required"
        }, status=400)

    try:
        # 删除 Pod
        delete_options = client.V1DeleteOptions()
        api_response = v1.delete_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body=delete_options
        )
        
        return JsonResponse({
            "status": "success",
            "message": f"Pod {pod_name} in namespace {namespace} is being deleted",
            "details": str(api_response.status)
        })

    except client.rest.ApiException as api_e:
        return JsonResponse({
            "status": "error",
            "message": f"K8s API error: {api_e.reason}",
            "details": api_e.body
        }, status=api_e.status)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

# file-management
def file_share_list(request):
    """获取文件列表"""
    username = request.GET.get("username")
    relativepath = request.GET.get("relativepath")
    storage = NFSStorage(username)
    files = storage.list_share_files(relativepath)
    print(files)
    return JsonResponse({'files': files})


def file_list(request):
    """获取文件列表"""
    username = request.GET.get("username")
    relativepath = request.GET.get("relativepath")
    storage = NFSStorage(username)
    files = storage.list_files(relativepath)
    print(files)
    return JsonResponse({'files': files})


def file_upload(request):
    """文件上传"""
    username = request.POST.get('username')  # 从附加数据获取
    relativepath = request.POST.get('relativepath')
    print(request.POST)
    storage = NFSStorage(username)
    files = request.FILES.getlist('file')
    print(files)
    for file in files:
        storage.save_file(relativepath, file)
    return JsonResponse({'status': 'success'})


def file_delete(request):
    """文件删除"""
    if request.method == 'POST':
        data = json.loads(request.body)
        relativepath = data.get('relativepath')
        storage = NFSStorage(data.get('username'))
        if storage.delete_file(relativepath):
            return JsonResponse({'status': 'success'})
        return JsonResponse({'error': 'File not found'}, status=404)


def file_download(request):
    """文件下载"""
    username = request.GET.get("username")
    relativepath = request.GET.get("relativepath")
    storage = NFSStorage(username)
    file_obj = storage.get_file(relativepath)
    if file_obj:
        response = FileResponse(file_obj)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = f'attachment; filename="temp"'
        return response
    return JsonResponse({'error': 'File not found'}, status=404)
