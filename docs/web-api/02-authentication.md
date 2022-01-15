# ecHome Web API - Authentication

Ensure you have your access key ID and secret handy. Your username and password will not work with the API.

> ⚠️ ALL credentials and tokens that are retrieved or sent to the server must never be shared and kept secret. These tokens or keys can be used to authenticate to the server and make changes on your behalf. 

## 1. Retrieve access token

Your first request to the server will be to retrieve a JWT token which should be included for every subsequent request to the server.

```
curl -X POST -H "Content-Type: application/json" -d '{"username": "[USER_ACCESS_ID]", "password": "[SECRET]"}' [SERVER_ADDRESS]/api/v1/identity/token
```

Replace the variables above with your user access ID, secret key, and server address where your ecHome host is setup. If the request was successful, your credentials were valid and you should receive a response with a refresh token and access token:

```
{
  "refresh": "wejZoi23vq25JCwoj23ewqIkORqwXOCXJASO.eIISixTJGMpujOZ8ztWxLIe1J2IRmjGT3G9DMdM0YxNPwwsIvubtrruq86dnmfMuEDWVfBiehLIe1J2IRmjGT3G9DMdM0YxNPwwsIvubO7RUdekr9q_Fdubtrruq86UQPJEvaLefdza32gQg.7dJZ1P5fnaPWwTZlYeoqja0zW5lVEgx9WzX2wuypkZM",
  "access": "wejZoi23vq25JCwoj23ewqIkORqwXOCXJASO.RJiyvPRt3NpRtdaXNzIiwiTckJ3ZBRt3guvEdbe0fiQqasxLeckJ3ZB_WtckJ3ZBBQjiM7aSPStWyiv9L_ePMCtA7NRxJANckJ3ZB93UL0LpcRJiDMKla4dxD2IG3W9gVBT_g25yrIpcRJi.ukmDtDoiYMkxh0LEyDkFnRaGilAOsvBH15ns3Xem6aY"
}
```

The access token is a short-lived token that will authentication requests to the server. Keep the refresh token in a cache as it will be needed to refresh the access token when it expires.

## 2. Make a request with the access token

With the complete access token, make a request to the virtual machines endpoint:

```
ACCESS_TOKEN="wejZoi23vq25JCwoj23ewqIkORqwXOCXJASO.RJiyvPRt3NpRtdaXNzIiwiTckJ3ZBRt3guvEdbe0fiQqasxLeckJ3ZB_WtckJ3ZBBQjiM7aSPStWyiv9L_ePMCtA7NRxJANckJ3ZB93UL0LpcRJiDMKla4dxD2IG3W9gVBT_g25yrIpcRJi.ukmDtDoiYMkxh0LEyDkFnRaGilAOsvBH15ns3Xem6aY" \
curl -H 'Accept: application/json' -H "Authorization: Bearer ${ACCESS_TOKEN}" [SERVER_ADDRESS]/api/v1/vm/vm/describe/all
```

If you had any virtual machines setup, you would receive a successful response such as this:

```
{
  "success": true,
  "details": "",
  "results": [
    {
      "instance_id": "vm-f00000f6",
      "created": "2021-04-05T13:13:13.546513Z",
      "last_modified": "2021-04-05T13:13:13.546513Z",
      "instance_type": "standard",
      "instance_size": "medium",
      "metadata": {},
      "image_metadata": {
        "image_id": "gmi-d00000f2",
        "image_name": "Ubuntu 18.04"
      },
      "interfaces": {
        "config_at_launch": {
          "type": "BridgeToLan",
          "vnet_id": "vnet-7000000a",
          "private_ip": "192.168.0.42"
        }
      },
      "storage": {},
      "key_name": "my-key",
      "tags": {
        "Name": "kubernetes-node-2",
        "Cluster": "kube-6aa000v0"
      },
      "host": "host-fb00000d",
      "state": {
        "code": 1,
        "state": "running"
      }
    }
  ]
}
```

# 3. Refreshing access token

If during a request to the server you receive a 401 Unauthenticated response, try refreshing the access token

```
$ ACCESS_TOKEN="wejZoi23vq25JCwoj23ew..."
$ REFRESH_TOKEN="wejZoi23vq25JCwoj..."

$ curl -X POST -H 'Accept: application/json' -H "Authorization: Bearer ${ACCESS_TOKEN}" [SERVER_URL]/api/v1/identity/token/refresh -d "refresh=${REFRESH_TOKEN}"
```

Notice how the original access token is still required in the Authorization header. If it is omitted, refreshing will not work. The response will contain the new access token which should be used for all new requests.

Note: The rest of the documentation will exclude the example tokens above and will instead assume that you have an access token set!
