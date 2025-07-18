conda create -n peptide python=3.10.14
conda activate peptide
pip install git+https://github.com/HeliXonProtein/OmegaFold
wget -O ADFRsuite_Linux-x86_64_1.0.tar.gz "https://ccsb.scripps.edu/adfr/download/1038/"
tar zxvf ADFRsuite_Linux-x86_64_1.0.tar.gz
cd ADFRsuite_x86_64Linux_1.0
 ./install.sh -d ~/ADFRsuite-1.0 -c 0
 echo 'export PATH=/home/davis/ADFRsuite-1.0/bin:$PATH' >> ~/.bashrc
 source ~/.bashrc
 which adfr

pip install vina