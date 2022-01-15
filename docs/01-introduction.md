# ecHome - Introduction

Welcome to the documentation for ecHome. This guide will provide the steps for installation, setup, and interacting with ecHome to create virtual machines.

ecHome is short for Elastic Compute at Home and is inspired by cloud services such as Amazon Web Services. These services have made it easy to spin up and down virtual machines in seconds along with providing a whole host of other features. Although the feature set of ecHome does not come anywhere close, it will hopeflly provide some of the convenience that comes with using cloud infrastructure at home with far fewer costs.

> The examples in this guide use the `echome` CLI to interface with ecHome which is the most common way to perform tasks. If you're working with a programming language and wish to integrate ecHome with your applications, consider using the [echome-python-sdk](https://github.com/mgtrrz/echome-python-sdk/) module in Python or the [web API](../web-api/01-introduction.md) for other languages.

## Features

* Launch a virtual machine of your flavor linux distribution in seconds.
* Launch virtual machines with IPs in your home-network that will allow them to be seen by other guests, perfect for home environments and running applications such as Pihole or Homebridge.
* Customize your own virtual machines and create images of them to later launch your prepared VM.
* Add shell scripts as user-data to your virtual machines that run on first-boot.
* Create, upload, and manage SSH keys that can be automatically imported to any linux instances that are launched.
* Launch and manage your own kubernetes clusters in a few minutes
* ecHome CLI makes it easy to manage and view several aspects of your environment from any computer within your network in the terminal.
* Use the Python SDK to manage your environment with code or use the web API to work in any other language you prefer.

## Installation

If this is your first time and you have not yet setup ecHome, follow the guide below to get started:

[Installation and Setup](./installation/01-install.md)

---
Next Article: [Virtual Machines](./02-virtual-machines.md)
