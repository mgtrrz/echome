# ecHome Web API - Virtual Machines

## vm/create

```
/api/v1/vm/vm/create
```

### POST 

#### Parameters

##### Required

- ImageId
- InstanceType
- NetworkProfile

##### Optional

- KeyName
- PrivateIp
- DiskSize
- EnableVnc
- VncPort
- UserDataScript

### Example

```
curl -X POST -H 'Accept: application/json' -H "${AUTH_HEADER}" ${URL}/api/v1/vm/vm/create -d "ImageId=gmi-92fcfbbc&InstanceType=standard.nano&NetworkProfile=home-network&KeyName=my-key&PrivateIp=10.0.15.24"
```

### Returns 

#### Success

```
{'success': True, 'details': '', 'results': {'virtual_machine_id': 'vm-eef65680'}}
```

### Documentation

Create and launch a virtual machine.

## vm/describe/<id|all>

```
/api/v1/vm/vm/describe/<id|all>
```

## vm/terminate/<id>

```
/api/v1/vm/vm/describe/<id|all>
```

## vm/modify/<id>

```
/api/v1/vm/vm/modify/<id|all>
```
