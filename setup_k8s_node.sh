# !/bin/bash

echo "============================================"
echo " Starting Kubernetes Cluster Initialization "
echo "============================================"

# Set hostname resolution
echo ">>> Setting up /etc/hosts entries..."
cat >> /etc/hosts << EOF
172.25.95.4 k8s-master
172.25.95.5 k8s-node1
172.25.95.6 k8s-node2
172.25.95.7 k8s-node3
EOF
echo "/etc/hosts configured successfully."

# Disable firewall
echo ">>> Disabling firewall..."
systemctl disable --now ufw

iptables -F
iptables -X
iptables -Z 
echo "Firewall disabled."

# Disable swap
echo ">>> Disabling swap..."
sed -ri 's/^([^#].*swap.*)$/#\1/' /etc/fstab  && swapoff -a && free -h
echo "Swap disabled."

# Configure kernel parameters
echo ">>> Configuring kernel parameters..."

cat >> /etc/sysctl.conf <<EOF
vm.swappiness = 0
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF
cat >> /etc/modules-load.d/neutron.conf <<EOF
overlay
br_netfilter
EOF
#加载模块
modprobe  br_netfilter
modprobe  overlay
#让配置生效
sysctl --system
echo "Kernel parameters configured."

# Configure timezone
echo ">>> Configuring timezone..."
timedatectl set-timezone Asia/Shanghai
echo "Timezone set to Asia/Shanghai."

# Install Docker
echo ">>> Installing Docker..."
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release
curl -fsSL http://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] http://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
apt-get install -y docker-ce docker-ce-cli containerd.io
echo "Docker installed successfully."

# Configure Docker
echo ">>> Configuring Docker..."
cat > /etc/docker/daemon.json <<EOF
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ],
  "insecure-registries":["172.25.95.4:5000"]
}
EOF
systemctl enable docker
systemctl restart docker
echo "Docker configured successfully."

# Install cri-docker
echo ">>> Installing cri-docker..."
curl -LO https://github.com/Mirantis/cri-dockerd/releases/download/v0.3.17/cri-dockerd_0.3.17.3-0.ubuntu-jammy_amd64.deb
apt install -y ./cri-dockerd_0.3.17.3-0.ubuntu-jammy_amd64.deb
cat > /usr/lib/systemd/system/cri-docker.service << 'EOF'
[Unit]
Description=CRI Interface for Docker Application Container Engine
Documentation=https://docs.mirantis.com
After=network-online.target firewalld.service docker.service
Wants=network-online.target
Requires=cri-docker.socket

[Service]
Type=notify
ExecStart=/usr/bin/cri-dockerd --network-plugin=cni --pod-infra-container-image=registry.aliyuncs.com/google_containers/pause:3.9
ExecReload=/bin/kill -s HUP $MAINPID
TimeoutSec=0
RestartSec=2
Restart=always
 
StartLimitBurst=3
 
StartLimitInterval=60s
 
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
 
TasksMax=infinity
Delegate=yes
KillMode=process
 
[Install]
WantedBy=multi-user.target
EOF

systemctl enable cri-docker --now
systemctl restart cri-docker
systemctl daemon-reload
echo "cri-docker installed and running."

# Install Kubernetes components
echo ">>> Installing Kubernetes components..."
apt update && apt install -y apt-transport-https curl ca-certificates curl gpg
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | \
sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg && \
sudo chmod 644 /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /' \
| sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt update && \
sudo apt install -y  --allow-change-held-packages kubelet kubectl kubeadm && \
sudo apt-mark hold kubelet kubeadm kubectl

systemctl enable --now kubelet
kubeadm version
echo "Kubernetes components installed successfully."

echo "============================================"
echo " Kubernetes Node Initialization Complete "
echo "============================================"


cat > /etc/docker/daemon.json << 'EOF'
{
    "exec-opts": [
        "native.cgroupdriver=systemd"
    ],
    "insecure-registries": [
        "172.25.95.4:5000"
    ],
    "registry-mirrors": [
        "https://docker.1ms.run",
        "https://docker.xuanyuan.me"
    ],
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF
sudo apt install -y nfs-common


