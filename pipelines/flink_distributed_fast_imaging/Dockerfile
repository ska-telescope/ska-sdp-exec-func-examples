###############################################################################
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
# limitations under the License.
###############################################################################

###############################################################################
# Build PyFlink Fast Imaging Image
###############################################################################
# This image is devised by looking at the individual docker images of:
# 1 Cuda, 2 Flink, 3 Pyflink 4 Cupy and then adding instructions to install:
# the requirements and the Science Data Processor Processing FUnction Library,
# (ska-sdp-func)
###############################################################################
# Step 1: Install Cuda
FROM nvidia/cuda:11.7.0-devel-ubuntu20.04
CMD nvidia-smi

# Step 2: Install Flink
# Based on https://hub.docker.com/_/flink
# https://github.com/apache/flink-docker/blob/bf3014dc4e866d0d213a45cea17010c2380b7e6b/1.14/scala_2.11-java11-debian/Dockerfile
ARG FLINK_VERSION=1.14.5

ARG DEBIAN_FRONTEND=noninteractive

#Install Java
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk && \
    apt-get install -y ant && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/ && \
    rm -rf /var/cache/oracle-jdk8-installer;

ENV JAVA_HOME /usr/lib/jvm/java-8-openjdk-amd64/
RUN export JAVA_HOME

RUN set -eux; \
	apt-get update; \
	apt-get install -y wget; \
	apt-get install -y --no-install-recommends \
# utilities for keeping Debian and OpenJDK CA certificates in sync
		ca-certificates p11-kit \
	; \
	rm -rf /var/lib/apt/lists/*

# Below from: https://github.com/apache/flink-docker/blob/bf3014dc4e866d0d213a45cea17010c2380b7e6b/1.14/scala_2.11-java8-debian/Dockerfile
# Install dependencies
RUN set -ex; \
  apt-get update; \
  apt-get -y install libsnappy1v5 gettext-base libjemalloc-dev; \
  rm -rf /var/lib/apt/lists/*

# Grab gosu for easy step-down from root
ENV GOSU_VERSION 1.11
RUN set -ex; \
  wget -nv -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$(dpkg --print-architecture)"; \
  wget -nv -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$(dpkg --print-architecture).asc"; \
  export GNUPGHOME="$(mktemp -d)"; \
  for server in ha.pool.sks-keyservers.net $(shuf -e \
                          hkp://p80.pool.sks-keyservers.net:80 \
                          keyserver.ubuntu.com \
                          hkp://keyserver.ubuntu.com:80 \
                          pgp.mit.edu) ; do \
      gpg --batch --keyserver "$server" --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && break || : ; \
  done && \
  gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu; \
  gpgconf --kill all; \
  rm -rf "$GNUPGHOME" /usr/local/bin/gosu.asc; \
  chmod +x /usr/local/bin/gosu; \
  gosu nobody true

# Configure Flink version
ENV FLINK_TGZ_URL=https://www.apache.org/dyn/closer.cgi?action=download&filename=flink/flink-1.14.5/flink-1.14.5-bin-scala_2.11.tgz \
    FLINK_ASC_URL=https://www.apache.org/dist/flink/flink-1.14.5/flink-1.14.5-bin-scala_2.11.tgz.asc \
    GPG_KEY=EB3FE0FA3282FAF822E434AE3C2C9FFB59DF9F3E \
    CHECK_GPG=true

# Prepare environment
ENV FLINK_HOME=/opt/flink
ENV PATH=$FLINK_HOME/bin:$PATH
RUN groupadd --system --gid=9999 flink && \
    useradd --system --home-dir $FLINK_HOME --uid=9999 --gid=flink flink
WORKDIR $FLINK_HOME

# Install Flink
RUN set -ex; \
  wget -nv -O flink.tgz "$FLINK_TGZ_URL"; \
  \
  if [ "$CHECK_GPG" = "true" ]; then \
    wget -nv -O flink.tgz.asc "$FLINK_ASC_URL"; \
    export GNUPGHOME="$(mktemp -d)"; \
    for server in ha.pool.sks-keyservers.net $(shuf -e \
                            hkp://p80.pool.sks-keyservers.net:80 \
                            keyserver.ubuntu.com \
                            hkp://keyserver.ubuntu.com:80 \
                            pgp.mit.edu) ; do \
        gpg --batch --keyserver "$server" --recv-keys "$GPG_KEY" && break || : ; \
    done && \
    gpg --batch --verify flink.tgz.asc flink.tgz; \
    gpgconf --kill all; \
    rm -rf "$GNUPGHOME" flink.tgz.asc; \
  fi; \
  \
  tar -xf flink.tgz --strip-components=1; \
  rm flink.tgz; \
  \
  chown -R flink:flink .;

# Configure container

COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
EXPOSE 6123 8081
CMD ["help"]

WORKDIR /opt/example-pipeline
COPY . .

# https://nightlies.apache.org/flink/flink-docs-release-1.13/docs/deployment/resource-providers/standalone/docker/#enabling-python
# Step 3: Install pyflink
RUN apt-get update -y && \
apt-get install -y build-essential libssl-dev zlib1g-dev libbz2-dev libffi-dev && \
wget https://www.python.org/ftp/python/3.7.9/Python-3.7.9.tgz && \
tar -xvf Python-3.7.9.tgz && \
cd Python-3.7.9 && \
./configure --without-tests --enable-shared && \
make -j6 && \
make install && \
ldconfig /usr/local/lib && \
cd .. && rm -f Python-3.7.9.tgz && rm -rf Python-3.7.9 && \
ln -s /usr/local/bin/python3 /usr/local/bin/python && \
apt-get clean && \
rm -rf /var/lib/apt/lists/*

# install PyFlink
RUN pip3 install apache-flink==1.14.5 && \
pip3 install kafka-python;

# install other python packages
RUN python3 -m pip install -U setuptools pip
RUN pip3 install wheel

# Install cupy with wheels
# based on https://hub.docker.com/r/cupy/cupy/
RUN pip3 install --no-cache-dir -f https://github.com/cupy/cupy/releases/v11.0.0rc1 "cupy-cuda11x[all]==11.0.0rc1"

RUN pip3 install -r requirements.txt

# Download connector libraries
RUN wget -P /opt/flink/lib/ https://repo.maven.apache.org/maven2/org/apache/flink/flink-json/${FLINK_VERSION}/flink-json-${FLINK_VERSION}.jar; \
    wget -P /opt/flink/lib/ https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka_2.11/${FLINK_VERSION}/flink-sql-connector-kafka_2.11-${FLINK_VERSION}.jar;

RUN echo "taskmanager.memory.jvm-metaspace.size: 512m" >> /opt/flink/conf/flink-conf.yaml;

WORKDIR /opt/flink

# Download and install sdp
# Download the correct branch, and version
RUN wget https://gitlab.com/ska-telescope/sdp/ska-sdp-func/-/archive/f264c46cba7a985c5da573fb4e738ea298d3b898/ska-sdp-func-f264c46cba7a985c5da573fb4e738ea298d3b898.tar.gz && \
tar -xf ska-sdp-func-f264c46cba7a985c5da573fb4e738ea298d3b898.tar.gz && mv ska-sdp-func-f264c46cba7a985c5da573fb4e738ea298d3b898 ska-sdp-func &&\
cd ska-sdp-func && \
# Install package inside folder as in https://developer.skao.int/projects/ska-sdp-func/en/latest/install.html
mkdir build && \
cd build && \
apt-get update -y && \
apt-get update && \
apt-get install -y cmake && \
cmake .. && \
make -j8 && \
make install && \
cd /opt/flink/ska-sdp-func && \
pip3 install .

COPY ./functions/pipeline_functions.py ./pipeline_functions.py
COPY ./functions/func_requirements.txt ./func_requirements.txt
RUN pip3 install -r func_requirements.txt
