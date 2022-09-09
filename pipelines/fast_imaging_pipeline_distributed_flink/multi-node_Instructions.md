# Deploying Example Pipelines on many nodes.

As the example is already containerised and orchestrated using docker-compose deploying it on many nodes in a containerised fashion is not difficult. This document will walk through how to deploy it on multiple hosts(nodes) using [docker swarm](https://docs.docker.com/engine/swarm/key-concepts/).

You may want to forward ports from the manager node to see the applications web UI's, to do this use:
```
 ssh -L 1234:localhost:8081 -L 1235:localhost:5601 -L 1236:localhost:9200 <remote machine acting as manager>

```

this will forward the services to the same ports as in the [local case](README.md).

The first step would be to create a swarm, if you do not already have one.
## Setting up a docker swarm.
The process is outlined [here](https://docs.docker.com/engine/swarm/swarm-tutorial/), you require: ``two or more machines where you have sudo access``.

### Install docker on all machines
ssh into **each machine you want to be either a worker or manager node** and install docker using:
```
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

To confirm that docker is installed correctly you can run:
```
sudo docker run hello-world
```

### Install nvidia container toolkit
Follow instructions [here](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) by:
```
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
            
sudo apt-get update

sudo apt-get install -y nvidia-docker2

sudo systemctl restart docker
```
Check it is installed correctly:
```
sudo docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
```

### Change default runtime to nvidia
To for a docker stack deployment toi access GPU's the default docker runtime on the nodes must be nvidia:
To fix this on **each node**, edit ``/etc/docker/daemon.json`` as a superuser (you can use editor of choice) if using VIM:
```
sudo vim /etc/docker/daemon.json
```
Then press I to enter insert mode, set the default runtime by changing the file to:
```
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
```

Now save and exit vim (Press ``ESc`` to get back to command mode, then type ``:wq`` and hit enter)
Now restart the docker deamon and runtime:
```
sudo systemctl reload docker
```
Check that the default runtime is ``nvidia``:
```
sudo docker info
```
To check that it works see if you can execute the gpu test command without the gpu option:
```
sudo docker run --rm nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
```
### Initialise the swarm and add workers
**From this point on it is important whether you execute the commands on the Manager or Worker nodes**.

**On the Manager Node**, initialise the cluster, this node will then become the leader. To do this you need the IP-address of the node, run:
```
curl ifconfig.me
```
to get the IP-address.
Then initialise the cluster **on the Manager Node** and advertise the IP-address using:
```
sudo docker swarm init --advertise-addr <Manager's IP-address>
```
The above command produces an output like:
```
Swarm initialized: current node (dxn1zf6l61qsb1josjja83ngz) is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join \
    --token SWMTKN-1-49nj1cmql0jkz5s954yi3oex3nedyz0fb0xx14ie39trti4wxv-8vxv8rssmk743ojnwacrr2e7c \
    192.168.99.100:2377

To add a manager to this swarm, run 'docker swarm join-token manager' and follow the instructions.
```

You can run ``sudo docker swarm join-token worker`` **on the Manager Node** to see this message again.

**On the Worker Nodes**, you simply run the command you recieved from the manager node att add them as workers in the swarm. If you get permission denied, add sudo.

To see what nodes are in the swarm run: ``sudo docker node ls``  **on the Manager Node**, this should display the workers you have added.

## Preparing swarm
Swarm is not able to build images, therefore the images must be build and stored in a register beforehand to then be loaded from the register dusirng swarm deployment. This may sound intimidating, but it is actually very simple. More information is found [here](https://docs.docker.com/engine/swarm/stack-deploy/).

### Start a local registry to manage images
**On the manager node** start a registry service using:
```
sudo docker service create --name registry --publish published=5000,target=5000 registry:2
```
Check that the registry is running using:
```
sudo docker service ls
```
### Push images to registry
Because of the need for a registry in swarmode, the docker-compose.yml file for swarm mode is different from the one for local deployments, outlined in the [README](README.md). For swarm mode we use ``docker-compose-swarm.yml``, the difference between this file and the one for local deployments is that it saves and loads the images from the registry we just created, it also contains some simple instructions regarding what processes to put on what type of host. On the whole it is however very similar to ``docker-compose.yml``.

**The process for pushing images to registry** consists of **1. building the images using docker-compose**, **2. pushing the built images**, **3. taking down the application**.

The first step is to run docker-compose **on the Manager** to build the images and start the application, the same way as when starting it locally but using ``docker-compose-swarm.yml``.

Build **on Manager** using:
```
sudo docker-compose --file docker-compose-swarm.yml build
```
Then test that the app is working locally before trying to deploy it. **On the Manager** run:
```
sudo docker-compose --file docker-compose-swarm.yml up -d
```
If the comand executes ok (warnings that the engine is in swarm mode are expected) than take the app down. **On Manager** shut the application down using:
```
sudo docker-compose --file docker-compose-swarm.yml down --volumes
```

**Now push the build images** to the registry by on the **Manager** running:
```
sudo docker-compose --file docker-compose-swarm.yml push
```

You can check the contents of the registry with:
```
curl -X GET http://localhost:5000/v2/_catalog
```
## Deploying the application using swarm
You now have a swarm running, and the images in a registry. You are ready to deploy the example pipeline.

This is done **on the Manager** by running:

```
sudo docker stack deploy --compose-file docker-compose-swarm.yml flinkdemo
```
which will create a stack called flinkdemo. you should see services being started.

**On the Manager node** you can inspect all the services (it is expected that flinkdemo_generator has 0/1 replicas, do not worry) using: 
```
sudo docker stack services flinkdemo
```
and to see on what nodes individual services (for example taskmanagers) are running use:
```
sudo docker service ps flinkdemo_taskmanager
```
The taskmanagers should be spread out, the jobmanager and kafka should run on the manager node.

### Scaling up number of taskmanagers
To increase the number of taskmanagers, to 2 for example, the command is:
```
sudo docker service scale flinkdemo_taskmanager=2
```
**Important: each taskmanager in FLink will read data from 1 or more kafka partition, multiple TaskManagers cannot read data from the same partition, it is therefore required to set the number of topic partitions to be the same or greater than the parallelism you intend to use (in this example there are two partitions by default, as seen in the docker-compose files).
These will be deployed to the different nodes and their placement can be seen using:
```
sudo docker service ps flinkdemo_taskmanager
```
**The Flink job requires 5 taskmanagers**
### Submitting Flink Job
The job is submitted by **on the Manager node** running:
```
sudo docker exec $(sudo docker ps -q -f name="flinkdemo_jobmanager*") ./bin/flink run -py /opt/example-pipeline/fast_imaging_job.py -p 2 -d -pyfs pipeline_functions.py
```

To start analysing a visibilities in a MeasurementSet, start a generator job **on the Manager Node** using:
Mount the directory which contains the MeasurementSet with Visibilities.
```
sudo docker run --mount type=bind,source=/mnt/FIP/,target=/mnt/FIP/ -d --name generator_job --network flinkdemo_default 127.0.0.1:5000/generator:1.0 python3 -u ./generate_source_data.py <local path to MeasurementSet>
```
For example:
```
sudo docker run --mount type=bind,source=/mnt/FIP/,target=/mnt/FIP/ -d --name generator_job --network flinkdemo_default 127.0.0.1:5000/generator:1.0 python3 -u ./generate_source_data.py /mnt/FIP/1636091170_sdp_l0_1024ch_MTP0013_scan8.ms
```

Now check the generator_job logs:
```
sudo docker logs generator_job -f
```
And now you will see in Flink UI that records are processed, and in the consumer/fits folder there should be the processed fits files.

To make png images and an mp4 movie from the visibilities, follow the same process as for a single node deployment.
## Shutting down deployment
When you are finsihed the deployment of the pipeline can be closed down by **on the Manager node** running:
```
sudo docker rm -f generator_job
sudo docker stack rm flinkdemo
```
To delete the registry we created run:
```
sudo docker service rm registry
```