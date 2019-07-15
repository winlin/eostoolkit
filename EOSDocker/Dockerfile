FROM winlin/eosbuilder:v1.0.1 as builder
ARG branch=master
ARG symbol=SYS

RUN git clone -b $branch https://github.com/EOSIO/eos.git --recursive 

WORKDIR /eos
RUN git remote update
RUN ./scripts/eosio_build.sh -s EOS -y -P \
RUN ./scripts/eosio_install.sh

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install openssl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/* /usr/local/lib/
COPY --from=builder /tmp/build/bin /opt/eosio/bin
COPY --from=builder /eos/Docker/config.ini /
COPY --from=builder /etc/eosio-version /etc
COPY --from=builder /eos/Docker/nodeosd.sh /opt/eosio/bin/nodeosd.sh
ENV EOSIO_ROOT=/opt/eosio
RUN chmod +x /opt/eosio/bin/nodeosd.sh
ENV LD_LIBRARY_PATH /usr/local/lib
ENV PATH /opt/eosio/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install vim net-tools lsof wget curl supervisor
RUN wget -O /root/.bashrc https://raw.githubusercontent.com/EOSBIXIN/eostoolkit/master/bashrc
RUN mkdir /root/eosio-wallet
RUN wget -O /root/eosio-wallet/config.ini https://raw.githubusercontent.com/EOSBIXIN/eostoolkit/master/wallet_config.ini
RUN wget -O /opt/eosio/bin/nodeosd.sh https://raw.githubusercontent.com/EOSBIXIN/eostoolkit/master/others/bos/nodeosd.sh
RUN chmod a+x /opt/eosio/bin/nodeosd.sh
