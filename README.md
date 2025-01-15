# MIE-GAT (Multi-perspective Information Enhancement Graph Attention Network)
Code for the paper "MIE-GAT: A Multi-perspective Information Enhancement Graph Attention Network for Benign and Malignant Classification of Pulmonary Nodules".
## Requirement
Python 3.9.18

PyTorch == 2.1.1

tensorboardX == 2.6.2.2

numpy == 1.26.3
## Installation
pytorch: http://pytorch.org/

tensorboardX: https://github.com/lanpa/tensorboard-pytorch

Download and unzip this project: MIE-GAT-master.zip.
## Dataset
Original LIDC-IDRI dataset can be found in the official website: [https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=1966254](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=1966254)

The LIDP dataset can be found in the MICCAI'2022 paper "[Lidp: A lung image dataset with pathological information for
lung cancer screening](https://link.springer.com/chapter/10.1007/978-3-031-16437-8_74)"
## Todos
* Scripts for the dataset configuration and model hyperparameter configuration are provided in ./config.
* Scripts for the model architecture are provided in ./models.
* In the main running scripts, the parameter "mode" is "train" for training mode, "mode" is "eval" for test mode.
* Modify the dataset configuration and the output directory in main running scripts.
* Run main running scripts.
