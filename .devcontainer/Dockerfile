FROM python:3.10

# avoid common warnings
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_ROOT_USER_ACTION=ignore
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# configure environment
ARG ENVNAME="GraphRAG"
ARG USERNAME=vscode
ARG USER_UID=1001
ARG USER_GID=$USER_UID
ARG WORKDIR=/${ENVNAME}

# install python, pip, git, and other required tools
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libicu-dev \
    git \
    curl \
    sudo \
    pre-commit \
    wget \
    jq \
    apt-transport-https \
    lsb-release \
    gnupg \
    software-properties-common
# install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
RUN az bicep install
# install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
# install helm
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \
    && chmod 700 get_helm.sh \
    && ./get_helm.sh \
    && rm ./get_helm.sh
# install yq
RUN wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/bin/yq \
    && chmod +x /usr/bin/yq

# install docker
RUN curl -fsSL https://get.docker.com -o install-docker.sh \
    && sh install-docker.sh \
    && rm install-docker.sh

# cleanup to keep the image size down
RUN rm -rf /var/lib/apt/lists/* \
    && apt-get purge -y --auto-remove \
    && apt-get autoremove \
    && apt-get clean

# set the location for the virtual environments to be outside the project directory
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# set up non-root user
RUN useradd -ms /bin/bash -u ${USER_GID} ${USERNAME} \
    && echo "${USERNAME}:${USERNAME}" | chpasswd \
    # add user to sudo group and docker group
    && adduser ${USERNAME} sudo \
    && echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers \
    && usermod -aG docker ${USERNAME}

# switch to non-root user
USER ${USERNAME}

# install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# add the local bin to the PATH for the non-root user
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"
# Add venv to beginning of path so we don't have to activate it
ENV PATH=/graphrag-accelerator/.venv/bin:$PATH

# copy the project files into the container and set ownership
COPY --chown=${USERNAME}:${USER_GID} . ${WORKDIR}

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Create directories for vscode server and extensions
RUN mkdir -p /home/$USERNAME/.vscode-server/extensions \
    && chown -R $USER_UID:$USER_GID /home/$USERNAME/.vscode-server

ENTRYPOINT [ "/usr/local/bin/entrypoint.sh" ]
CMD ["bash"]
