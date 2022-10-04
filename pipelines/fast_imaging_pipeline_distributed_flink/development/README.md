## Python Implementation of Pipeline Processing

To run the python implementation of the pipeline processing it is advised to use a conda virtual environment:
First install [anaconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html):
For example:
```
wget https://repo.anaconda.com/miniconda/Miniconda3-py39_4.12.0-Linux-x86_64.sh
bash Miniconda3-py39_4.12.0-Linux-x86_64.sh
```
With conda installed:
```
conda create --name FIP-python  python=3.8
conda activate FIP-python
```

And then install the requirements in this virtual environment:
```
conda install -c conda-forge cupy
conda install pip
pip install -r requirements.txt
```
Then install the SKA-SDP-PFL as specified here, use the same version as is used in the Dockerfile for the pyflink docker image: 
```
wget https://gitlab.com/ska-telescope/sdp/ska-sdp-func/-/archive/f264c46cba7a985c5da573fb4e738ea298d3b898/ska-sdp-func-f264c46cba7a985c5da573fb4e738ea298d3b898.tar.gz
tar -xf ska-sdp-func-f264c46cba7a985c5da573fb4e738ea298d3b898.tar.gz && mv ska-sdp-func-f264c46cba7a985c5da573fb4e738ea298d3b898 ska-sdp-func
```
```
cd ska-sdp-func
mkdir build
cd build
cmake ..
make -j8
cd ..
pip3 install .
```
Then check that all the required packages are installed:
```
conda list
```
To test it you need to make the fits and pics directories:
```
cd ..
mkdir fits
mkdir pic
```

Then run (for your measurement set):
```
python3 python_pipeline_implementation.py <MeasurementSet>
```
for example:
```
python3 python_pipeline_implementation.py /mnt/FIP/1636091170_sdp_l0_1024ch_MTP0013_scan8.ms
```
To close down the conda environment when done use:
```
conda deactivate
```