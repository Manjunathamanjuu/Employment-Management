## Order of Destroy

1.kubectl delete httproute employment-management -n stateful-demo
httproute.gateway.networking.k8s.io "employment-management" deleted from stateful-demo namespace
2.kubectl delete gateway employment-management-gateway -n stateful-demo
gateway.gateway.networking.k8s.io "employment-management-gateway" deleted from stateful-demo namespace
3.kubectl delete secret cloudaiops-tls -n stateful-demo
secret "cloudaiops-tls" deleted from stateful-demo namespace

## App Deletion

1.kubectl delete service employment-management -n stateful-demo
service "employment-management" deleted from stateful-demo namespace
2.kubectl delete deployment employment-management -n stateful-demo
deployment.apps "employment-management" deleted from stateful-demo namespace

## postgres Database Deletion

1.kubectl delete statefulset postgres -n stateful-demo
statefulset.apps "postgres" deleted from stateful-demo namespace
2. kubectl delete service postgres -n stateful-demo
service "postgres" deleted from stateful-demo namespace
3.kubectl get pvc -n stateful-demo
NAME                       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
postgres-data-postgres-0   Bound    pvc-1eaa3271-a628-4266-927c-901293b650e8   5
Gi        RWO            standard-rwo   <unset>                 19h
4.kubectl delete pvc --all -n stateful-demo
persistentvolumeclaim "postgres-data-postgres-0" deleted from stateful-demo namespace

## Namespace Deletion

1.kubectl delete namespace stateful-demo
namespace "stateful-demo" deleted

## Delete Cluster

gcloud container clusters delete k8s-postgres-lab \
  --region us-central1 \
  --project gcp-dev-july-2026
The following clusters will be deleted.
 - [k8s-postgres-lab] in [us-central1]

Do you want to continue (Y/n)?  y

Deleting cluster k8s-postgres-lab...done.
Deleted [https://container.googleapis.com/v1/projects/gcp-dev-july-2026/zones/us-central1/clusters/k8s-postgres-lab].

## Check Static IP

gcloud compute addresses describe cloudaiops-gateway-ip \
  --global \
  --project gcp-dev-july-2026
address: 8.233.53.213
addressType: EXTERNAL
creationTimestamp: '2026-09-03T00:23:38.985-07:00'
description: ''
id: '3315472811437629077'
ipVersion: IPV4
kind: compute#address
labelFingerprint: 42WmSpB8rSM=
name: cloudaiops-gateway-ip
networkTier: PREMIUM
selfLink: https://www.googleapis.com/compute/v1/projects/gcp-dev-july-2026/global/addresses/cloudaiops-gateway-ip
status: RESERVED

## Delete Static IP

 gcloud compute addresses delete cloudaiops-gateway-ip \
  --global \
  --project gcp-dev-july-2026
The following global addresses will be deleted:
 - [cloudaiops-gateway-ip]

Do you want to continue (Y/n)?  y

Deleted [https://www.googleapis.com/compute/v1/projects/gcp-dev-july-2026/global/addresses/cloudaiops-gateway-ip].

## Domain Check

nslookup -type=A cloudaiops.site 8.8.8.8

Expected:
Name:    cloudaiops.site
Address: 8.233.53.213

nslookup www.cloudaiops.site 8.8.8.8
deally it ultimately resolves to:
8.233.53.213

## 1. What is DNS?

When you type:
cloudaiops.site
your computer needs to find its IP address:
cloudaiops.site
        ↓
8.233.53.213
DNS is responsible for that translation.
Think of DNS as the Internet's phone book:
Name                         IP
────────────────────────────────────
cloudaiops.site       →      8.233.53.213
google.com            →      ...
github.com            →      ...

## 2. What is 8.8.8.8?

8.8.8.8 is a public DNS resolver operated by Google

So when you run:
nslookup -type=A cloudaiops.site 8.8.8.8
you are saying:

"Google DNS, please tell me the IPv4 (A) address for cloudaiops.site."

The flow is:
Your Computer
      │
      │ DNS query
      │
      ▼
Google DNS
8.8.8.8
      │
      │ Find A record
      ▼
cloudaiops.site
      │
      ▼
8.233.53.213

## 3. What is 1.1.1.1?

1.1.1.1 is another public DNS resolver, operated by Cloudflare.
So:
nslookup -type=A cloudaiops.site 1.1.1.1
means:
"Cloudflare DNS, please tell me the IPv4 address for cloudaiops.site."
Flow:
Your Computer
      │
      ▼
Cloudflare DNS
1.1.1.1
      │
      ▼
cloudaiops.site
      │
      ▼
8.233.53.213

## 4. Why do we use them?

When you ran:
your computer used its default DNS server:
2404:ba00:fd00::12
That server was timing out.
But when you ran:
nslookup cloudaiops.site 8.8.8.8
you explicitly told nslookup:
"Use Google DNS instead of my default DNS." That's why you got a response.

## 5. 8.8.8.8 vs 1.1.1.1

Both are public DNS resolvers.
| DNS       | Provider   | Purpose               |
| --------- | ---------- | --------------------- |
| `8.8.8.8` | Google     | Public DNS resolution |
| `8.8.4.4` | Google     | Google DNS secondary  |
| `1.1.1.1` | Cloudflare | Public DNS resolution |
| `1.0.0.1` | Cloudflare | Cloudflare secondary  |

You can use either:
nslookup -type=A cloudaiops.site 8.8.8.8 or nslookup -type=A cloudaiops.site 1.1.1.1

## 6. Very important distinction

Don't confuse these two IPs:
DNS server IP
8.8.8.8-->This is Google's DNS server.
Your website IP
8.233.53.213-->This is the GCP static IP you assigned to your GKE Gateway.
So:
8.8.8.8
   ↑
DNS SERVER
"Tell me where cloudaiops.site is"


8.233.53.213
   ↑
YOUR WEBSITE/GKE IP
"Here is where cloudaiops.site points"

## 7. Why did we use -type=A?

This is another important piece.

DNS supports different record types.
A       → IPv4 address
AAAA    → IPv6 address
CNAME   → Alias
NS      → Authoritative nameserver
MX      → Mail server
TXT     → Text/verification information
So:
nslookup -type=A cloudaiops.site 8.8.8.8
means:
              nslookup
                  │
                  ▼
             type = A
                  │
                  ▼
       "Give me IPv4 address"
                  │
                  ▼
          cloudaiops.site
                  │
                  ▼
          DNS server 8.8.8.8

## 8. The complete picture

For your domain:
                   YOUR COMPUTER
                         │
                         │
                         │ DNS query
                         ▼
                  ┌─────────────┐
                  │ Google DNS  │
                  │  8.8.8.8    │
                  └──────┬──────┘
                         │
                         │
                         │ "What is the A
                         │  record?"
                         ▼
                  cloudaiops.site
                         │
                         │ A record
                         ▼
                    8.233.53.213
                         │
                         ▼
                    GKE Gateway
                         │
                         ▼
                 Employment Management

### Easy way to remember


8.8.8.8 / 1.1.1.1 = "Who should I ask?"

8.233.53.213 = "Where is my application?"

And that's why explicitly specifying 8.8.8.8 or 1.1.1.1 is useful when troubleshooting DNS:
it lets you test your domain against a known public resolver instead of relying on your local ISP/router DNS
