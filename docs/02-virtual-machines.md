# ecHome - Virtual Machines

Virtual Machine management is the primary feature of ecHome. There's a couple of components of the virtual machines that you'll need to become familiar with.

## Components

* Image: A file that contains all information needed to produce a virtual machine. These images can either be in the form of a cloud image where linux or Windows is already installed or a disk image where installation 

* Guest Machine Image (`gmi`): These are images that can be used by all users on the server.

* Virtual Machine Image (`vmi`): These are images created by users that have been customized from the Guest Machine Image and are only accessible to the same account.

### Accounts and users

A quick note on users. Although not yet officially supported, ecHome has basic functionality for accounts and users. This means that an ecHome installation can have separate accounts with their own users managing their own virtual machines which helps to provide segmentation. Guest Machine Images (`gmi`) are available to all users and accounts on the server while Virtual Machine Images (`vmi`) are only available to the same account that created them.

<br>

## Getting Started

<br>

### Adding Guest Machine Images

To take advantage of ecHome, you'll need to obtain cloud images. Most Linux distributions publish a "Cloud" version of their operating system that's designed specifically for cloud providers.

> Be sure to download the correct architecture type for your hardware. In most cases, that's **AMD64** (not to be confused with _ARM64_) or **x86_64**. ecHome has not been tested with other architectures. 

<br>

* Debian - https://cloud.debian.org/images/cloud/
  * Use **"Generic"** and not "GenericCloud". The GenericCloud images may not contain the necessary network drivers to function.
* Ubuntu - https://cloud-images.ubuntu.com/
* CentOS Stream - https://www.centos.org/centos-stream/
  * Note: This image is untested. Help us test this image and verify compatibility
* Amazon Linux - https://cdn.amazonlinux.com/os-images/2.0.20220121.0/kvm/
* Windows - https://cloudbase.it/windows-cloud-images/
  * Note: Windows cloud images have not been tested

<br>

### **Saving Cloud Images**

#### **1. Designate a directory on your server for storing the guest images.**

As an example, this may be on a secondary drive mounted at `/mnt/hdd` and the guest image directory would be in that mount:  `/mnt/hdd/guest_images`. 

<br>

#### **2. Using `wget` or `curl` (or your tool of choice), download the cloud images to your guest images directory:**

```
/mnt/hdd/guest_images $ wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

--2022-02-10 01:49:53--  https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
Resolving cloud-images.ubuntu.com (cloud-images.ubuntu.com)... 91.189.88.248, 91.189.88.247, 2001:67c:1360:8001::33, ...
Connecting to cloud-images.ubuntu.com (cloud-images.ubuntu.com)|91.189.88.248|:443... connected.
HTTP request sent, awaiting response... 200 OK
Length: 608043008 (580M) [application/octet-stream]
Saving to: ‘jammy-server-cloudimg-amd64.img’

jammy-server-cloudimg-amd64.img                       100%[======================================================================================================================>] 579.88M  26.3MB/s    in 23s

2022-02-10 01:50:16 (25.6 MB/s) - ‘jammy-server-cloudimg-amd64.img’ saved [608043008/608043008]
```

You can choose to rename this file for organizational purposes (or name the downloaded file with the `curl/wget` command using flags) or continue on.

<br>

#### **3. Next, register the image with ecHome.**

Run this command either locally on your computer or on the same server logged in as an admin. The command to run will be `echome vm register-guest-image`. Try entering this command with the `-h` command for more information.

```
$ echome vm register-guest-image -h
usage: echome vm register-guest-image [-h] --image-path </path/to/image> --image-name <image-name> --image-description <image-desc> [--image-user <image-user>] [--tags {"Key": "Value", "Key": "Value"}]

Register an image

optional arguments:
  -h, --help            show this help message and exit
  --image-path </path/to/image>
                        Path to the new image. This image must exist on the new server and exist in the configured guest images directory.
  --image-name <image-name>
                        Name of the new image
  --image-description <image-desc>
                        Description of the new image
  --image-user <image-user>
                        Default user for logging into the image
  --tags {"Key": "Value", "Key": "Value"}
                        Tags
```

You'll need to enter the required parameters to register this image:

* ImagePath (--image-path): The full path to the image that you downloaded. This would be in the guest images directory we created earlier.
* ImageName (--image-name): The short name for the image. It should contain the distro and version, however, it can contain any information you like (60 char max). This is displayed in areas such as listing 
* ImageDescription (--image-description): More details about the image can be specified such as build-date, creator, etc.

The optional parameters include specifying the image user, which is the username that you'll use to log in to the instance). This isn't currently used for any purposes other than to help remind users what username to use when logging in. You can also specify tags to assign to this image.

```
$ echome vm register-guest-image --image-path /mnt/nvme/guestimages/jammy-server-cloudimg-amd64.img --image-name "Ubuntu Server 22.04" --image-description "Ubuntu Server 22.04 Jammy Jellyfish Cloud image"
{
    "success": true,
    "details": "",
    "results": "gmi-62591a79"
}
```

You'll receive your image ID back. Notice that since you've registered a Guest Image, its prefix is `gmi`.

<br>

#### **4. View all of the images you've registered so far.**

To view the images, run the following command:

```
$ echome vm describe-all-guest-images
Name                 Image Id      Format    State      Description
-------------------  ------------  --------  ---------  ----------------------------------------------------------
Ubuntu Server 22.04  gmi-62591a79  qcow2     AVAILABLE  Ubuntu Server 22.04 Jammy Jellyfish Cloud image
```

If the state is `AVAILABLE`, it's ready for you to use for any virtual machines.

<br>

### **Adding your SSH Key**

Cloud images by default do not allow you to login with passwords and because there is no installation or setup process, no ability to set or define this configuration outside of modifying the image. Therefore, setting up SSH keys is important to logging in to your virtual machine.

There are two parts to an SSH key: The **private key** and the **public key**. When ecHome creates an ssh key for you, it provides the **private key** and saves the **public key** on the server. That public key is then added to new virtual machines that you create and specify. The private key is sent to you and never stored on the server. This private key must be kept safe as it allows anyone to log in to the server that's accessible on the same network.

> Keep your private key file safe and do not delete it! You will not be able to log in to your virtual machines if you misplace or delete this file.

<br>

#### **Creating a new SSH key**

If you prefer to use a new key for your virtual machines, the procedure is simple. 

The `echome keys create-sshkey` command can create a new key for you:

```
$ echome keys create-sshkey -h
usage: echome keys create-sshkey [-h] (--file <./key-name.pem> | --no-file) <key-name>

Create an SSH Key

positional arguments:
  <key-name>            SSH Key Name

optional arguments:
  -h, --help            show this help message and exit
  --file <./key-name.pem>
                        Where a new file will be created with the contents of the private key
  --no-file             Output only the PEM key in JSON to stdout instead of a file.
```

Specify the name you wish to give the key and where to output the key. If you specify `--file`, the contents of the key will be placed on a file in the location you specify. If you specify `--no-file`, the contents of the key will be displayed but not saved to any file

> Make sure you save this key as you will not be able to retrieve the private key contents after its created!

```
$ echome keys create-sshkey my-new-key --file mykey.pem
'PrivateKey'
```

When logging in to the virtual machine with the key applied, you can specify which key to use with `-i`.

```
ssh ubuntu@10.0.0.10 -i ~/mykey.pem
```

---
Next Article: [Virtual Machines](./02-virtual-machines.md)
