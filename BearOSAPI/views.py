from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse


class DashBoardAPIView(APIView):
    def get(self, request):
        # 创建一些示例数据
        data = [
            {
                "nodeId": 1,
                "nodeName": "beargpu1",
                "gpuType": "a6000",
                "gpuTotal": 8,
                "gpuRemains": 8,
                "cpuTotal": 128,
                "cpuRemains": 64,
                "memoryTotal": 502,
                "memoryRemains": 256,
                "nodeStatus": "在线"
            },
            {
                "nodeId": 2,
                "nodeName": "beargpu2",
                "gpuType": "3090",
                "gpuTotal": 8,
                "gpuRemains": 0,
                "cpuTotal": 128,
                "cpuRemains": 64,
                "memoryTotal": 502,
                "memoryRemains": 256,
                "nodeStatus": "在线"
            },
            {
                "nodeId": 3,
                "nodeName": "beargpu3",
                "gpuType": "3090",
                "gpuTotal": 8,
                "gpuRemains": 0,
                "cpuTotal": 128,
                "cpuRemains": 64,
                "memoryTotal": 502,
                "memoryRemains": 256,
                "nodeStatus": "在线"
            },
            {
                "nodeId": 4,
                "nodeName": "beargpu4",
                "gpuType": "3090",
                "gpuTotal": 8,
                "gpuRemains": 0,
                "cpuTotal": 128,
                "cpuRemains": 64,
                "memoryTotal": 502,
                "memoryRemains": 256,
                "nodeStatus": "在线"
            },
            {
                "nodeId": 5,
                "nodeName": "beargpu5",
                "gpuType": "3090",
                "gpuTotal": 8,
                "gpuRemains": 0,
                "cpuTotal": 128,
                "cpuRemains": 64,
                "memoryTotal": 502,
                "memoryRemains": 256,
                "nodeStatus": "在线"
            },
            {
                "nodeId": 6,
                "nodeName": "beargpu6",
                "gpuType": "3090",
                "gpuTotal": 8,
                "gpuRemains": 0,
                "cpuTotal": 128,
                "cpuRemains": 64,
                "memoryTotal": 502,
                "memoryRemains": 256,
                "nodeStatus": "在线"
            }
        ]

        # 返回JSON响应
        return Response(data)
