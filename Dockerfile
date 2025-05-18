FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

RUN apt update && apt install -y --no-install-recommends \
 openssh-server \
 openssh-client \
 libcap2-bin \
 openmpi-bin \
 && rm -rf /var/lib/apt/lists/*
# Add priviledge separation directoy to run sshd as root.
RUN mkdir -p /var/run/sshd
# Add capability to run sshd as non-root.
RUN setcap CAP_NET_BIND_SERVICE=+eip /usr/sbin/sshd
RUN apt remove libcap2-bin -y
# Allow OpenSSH to talk to containers without asking for confirmation
# by disabling StrictHostKeyChecking.
# mpi-operator mounts the .ssh folder from a Secret. For that to work, we need
# to disable UserKnownHostsFile to avoid write permissions.
# Disabling StrictModes avoids directory and files read permission checks.
RUN sed -i "s/[ #]\(.*StrictHostKeyChecking \).*/ \1no/g" /etc/ssh/ssh_config \
 && echo " UserKnownHostsFile /dev/null" >> /etc/ssh/ssh_config \
 && sed -i "s/#\(StrictModes \).*/\1no/g" /etc/ssh/sshd_config \
 && sed -i -r 's/^[# ]*(PermitRootLogin)[ ]+.*$/\1 yes/' /etc/ssh/sshd_config
RUN echo "HostKey /root/.ssh/id_rsa\nPidFile /root/sshd.pid" >> /etc/ssh/sshd_config
EXPOSE 22
ENTRYPOINT ["/usr/sbin/sshd", "-De"]