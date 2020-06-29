#!/bin/bash

EOS_TAG=""

INSTALL_APPS=(
    "tmux"
    "axel"
    "git"
    "apt-transport-https"
    "ca-certificates"
    "curl"
    "python-pip"
    "tree"
    "supervisor"
    "python-setuptools"
    "python-dev"
    "libssl-dev"
    "hexcurse"
    "ntpstat"
    )

PIP_APPS=(
    "requests"
    "docker-compose"
    "libconf"
    "argparse"
    "pyjsonrpc"
    "stormssh"
    )

APP_REPO=(
    "ppa:git-core/ppa"
    "ppa:deadsnakes/ppa"
    #"deb [arch=amd64] https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
    )

GPG_KEYS=(
    #"https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu/gpg"
    )

INIT_PATH="${HOME}/inithost"
mkdir -p $INIT_PATH
cd $INIT_PATH
if [[ $? -ne 0 ]]; then
    echo "FAILED to cd $INIT_PATH"
    exit 1
fi


if [[ $1 != "init" && $1 != "source" && $1 != "docker" && $1 != "pull" ]]; then
    echo "Usage: $0 init|pull|source|docker"
    echo "      init: just initialize the machine"
    echo "      pull: just pull the latest code for EOSIO"
    echo "      source: just pull the latest code for EOSIO and call eosio_build.sh"
    echo "      docker: just pull the latest code for EOSIO and wait for docker build"
    exit 1
fi


function install_docker() {
    echo ">>>>>>>>>>> install Docker"
    sudo mkdir -p /etc/docker/
    sudo wget https://raw.githubusercontent.com/EOSBIXIN/eostoolkit/master/docker-etc-daemon.json -O /etc/docker/daemon.json

    curl -fsSL get.docker.com -o get-docker.sh
    sudo sh get-docker.sh

    sudo systemctl enable docker
    sudo systemctl start docker

    sudo usermod -aG docker $USER
}

function init_pip() {
    echo ">>>>>>>>>>> install PIP apps"
    sudo pip install --upgrade pip
    for item in "${PIP_APPS[@]}"; do
        sudo pip install "$item" --upgrade
    done
}

function pull_eostoolkit() {
    cd $INIT_PATH
    if [[ ! -e eostoolkit ]]; then
        git clone https://github.com/winlin/eostoolkit.git
        if [[ $? -ne 0 ]]; then
            echo "FAILED to get eostoolkit code"
            exit 1
        fi
    fi
    cd eostoolkit
    git pull origin
}

function init_host() {
    sudo mkdir -p /data
    sudo chown $USER:$USER /data

    sudo apt-get update
    echo ">>>>>>>>>>> install GPG Keys"
    for item in "${GPG_KEYS[@]}"; do
        curl -fsSL "$item" | sudo apt-key add -
    done

    sudo apt-get install -y software-properties-common

    echo ">>>>>>>>>>> install repositories"
    for item in "${APP_REPO[@]}"; do
        sudo apt-add-repository "$item"
    done
    sudo apt-get update

    echo ">>>>>>>>>>> install apps"
    for item in "${INSTALL_APPS[@]}"; do
        sudo apt-get install -y "$item"
        if [[ $? -ne 0 ]]; then
            echo "FAILED to install $item"
            exit 1
        fi
    done
    # initialize bashrc
    alias | grep dlog
    if [[ $? != 0 ]]; then
        echo "alias dlog='sudo docker-compose logs -t -f'" >> ~/.bashrc
    fi
    wget https://raw.githubusercontent.com/EOSBIXIN/eostoolkit/master/tmux.conf -O ~/.tmux.conf

    install_docker
    init_pip
    pull_eostoolkit
}



if [[ $1 == "init" ]]; then
    init_host
    exit 0
fi
