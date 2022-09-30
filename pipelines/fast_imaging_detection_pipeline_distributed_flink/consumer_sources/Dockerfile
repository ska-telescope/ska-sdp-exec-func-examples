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

FROM nvidia/cuda:11.6.0-base-ubuntu20.04
RUN apt-get -y update \
    && apt-get install -y software-properties-common \
    && apt-get -y update \
    && add-apt-repository universe
RUN apt-get -y update
RUN apt-get -y install python3
RUN apt-get -y install python3-pip
# dont write pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# dont buffer to stdout/stderr
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/src/consumer_sources
COPY ./consumer_sources ./
COPY ./functions/pipeline_functions.py ./pipeline_functions.py
COPY ./functions/func_requirements.txt ./func_requirements.txt

RUN set -ex;

# install other pyhon packages
RUN apt-get -y install libc-dev
RUN apt-get -y install build-essential
RUN pip3 install -r requirements.txt
RUN pip3 install -r func_requirements.txt

CMD ["python3", "-u", "./consume_data.py"]
