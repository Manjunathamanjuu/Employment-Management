# GKE Employment Management Deployment Guide

> Complete step-by-step deployment and troubleshooting guide for the Employment Management Spring Boot application on Google Kubernetes Engine (GKE).
>
> **Environment:** Learning/lab environment. Production recommendations are separated at the end.
>
> **Security:** Private keys, passwords, and raw Kubernetes secret material are intentionally omitted or represented by placeholders. Never commit `private.key` or raw secret data to Git.

---

## 1. Project Overview

### Application

- **Application:** Employment Management
- **Framework:** Spring Boot
- **Application port:** `8080`
- **REST API:** `/api/employees`

The application provides an employee-management UI and CRUD-style REST API. Employee records are persisted in PostgreSQL.

### Technologies

| Technology | Purpose |
|---|---|
| Git/GitHub | Source-code version control |
| Docker | Container image creation |
| Google Artifact Registry | Container image storage |
| GKE | Kubernetes runtime |
| Kubernetes Deployment | Runs the Spring Boot application |
| Kubernetes Service | Internal application access |
| PostgreSQL | Persistent relational database |
| Gateway API | External HTTP/HTTPS routing |
| GKE Gateway Controller | Programs the external Gateway |
| OpenSSL | Self-signed TLS certificate |
| Kubernetes TLS Secret | Stores TLS certificate/key |
| Hostinger DNS | Domain DNS management |
| curl | HTTPS/API verification |

---

## 2. Prerequisites

- Git
- Docker
- Google Cloud CLI (`gcloud`)
- `kubectl`
- GKE access
- PostgreSQL/`psql` knowledge
- Hostinger/domain access
- Working Spring Boot application and Dockerfile

---

## 3. Project and Environment Information

### Git

Repository:

```text
https://github.com/manjunath031984/Employment-Management
```

Branch:

```text
feature/Employment-Management
```

### GCP

| Resource | Value |
|---|---|
| Project ID | `gcp-dev-july-2026` |
| GKE cluster | `k8s-postgres-lab` |
| GKE region | `us-central1` |
| Artifact Registry repository | `employment-management` |
| Artifact Registry region | `us-central1` |

### Kubernetes

| Resource | Value |
|---|---|
| Namespace | `stateful-demo` |
| GatewayClass | `gke-l7-global-external-managed` |
| Gateway | `employment-management-gateway` |
| HTTPRoute | `employment-management` |
| Application Service | `employment-management` |
| PostgreSQL Service | `postgres` |
| PostgreSQL Pod | `postgres-0` |

### Database

| Setting | Value |
|---|---|
| Database | `employee-managementdb` |
| User | `postgres` |
| Port | `5432` |
| Employee table | `employees` |

> The lab used a simple PostgreSQL password. Do not reuse a weak lab credential in production.

### DNS and TLS

| Setting | Value |
|---|---|
| Domain | `cloudaiops.site` |
| Global static IP | `8.233.53.213` |
| DNS A record | `cloudaiops.site -> 8.233.53.213` |
| TLS approach | OpenSSL self-signed certificate + Kubernetes TLS Secret |
| TLS Secret | `cloudaiops-tls` |
| TLS namespace | `stateful-demo` |
| Certificate | `certificate.crt` |
| Private key | `private.key` |
| OpenSSL config | `openssl.cnf` |
| SAN | `cloudaiops.site` |
| SAN | `www.cloudaiops.site` |

---

## 4. Project Structure

Representative structure:

```text
Employment-Management/
├── README.md
├── Dockerfile
├── pom.xml
├── GKE-Employment-Management-Deployment-Guide.md
├── src/
├── Kubernetes-manifests/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── httproute.yaml
│   └── <PostgreSQL manifests>
└── certs/
    ├── certificate.crt
    ├── private.key
    └── openssl.cnf
```

---

# 5. Git Repository and Branch

Verify the branch:

```bash
git branch --show-current
```

Expected:

```text
feature/Employment-Management
```

Check changes:

```bash
git status
```

Add changes:

```bash
git add .
```

Verify staged files:

```bash
git status
```

Commit:

```bash
git commit -m "Document GKE deployment and update Kubernetes configuration"
```

Push:

```bash
git push origin feature/Employment-Management
```

> **Security:** Before `git add .`, make sure `certs/private.key` and files containing real secret material are ignored.

---

# 6. Docker Image

## 6.1 Final image

The final image selected for deployment was:

```text
us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
```

## 6.2 Local image investigation

Several local tags existed, including:

```text
employment-management:1.0.0
employment-management:latest
...:1.0.0
...:2.0.0
...:3.0.0
```

The local `latest` tag was older:

```text
ID=sha256:3ff8f33b92a7...
CREATED=2026-08-26T03:19:48.308673416Z
```

The qualified `1.0.0` image:

```text
sha256:4cd2ee3c19677abcf748cf6514867ddb1871c56aa7d30ff3982630a4ab018b06
CREATED=2026-08-31T09:39:28.891341003Z
```

The `3.0.0` image:

```text
sha256:9577766fbdc17649d409aad0642d52b8558f1894ccad528f526bef3afb7a3b9a
CREATED=2026-08-31T09:39:28.891341003Z
```

`1.0.0` and `3.0.0` had different image IDs despite identical creation timestamps. Therefore timestamp alone was not sufficient to choose the final image. The final deployment decision was to use `3.0.0`.

## 6.3 Verify image metadata

```bash
docker inspect   us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0   --format='TAG={{index .RepoTags 0}} ID={{.Id}} CREATED={{.Created}} ARCH={{.Architecture}} OS={{.Os}}'
```

Observed:

```text
ARCH=amd64
OS=linux
```

## 6.4 List local images

```bash
docker images | grep employment
```

---

# 7. Google Artifact Registry

Artifact Registry repository:

```text
employment-management
```

Location:

```text
us-central1
```

Authenticate Docker:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

Push final image:

```bash
docker push   us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
```

Verify:

```bash
gcloud artifacts docker images list   us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management   --include-tags
```

Final image:

```text
us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
```

---

# 8. GKE Cluster

Cluster:

```text
k8s-postgres-lab
```

Region:

```text
us-central1
```

Project:

```text
gcp-dev-july-2026
```

Namespace:

```text
stateful-demo
```

Verify nodes:

```bash
kubectl get nodes
```

Verify namespace:

```bash
kubectl get namespace stateful-demo
```

---

# 9. PostgreSQL Deployment

PostgreSQL was deployed as a StatefulSet and exposed internally through the `postgres` Service.

## 9.1 PostgreSQL Service

Observed:

```text
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)
postgres   ClusterIP   None         <none>        5432/TCP
```

The application connects using:

```text
postgres:5432
```

## 9.2 PostgreSQL Pod

Verify:

```bash
kubectl get pods -n stateful-demo
```

Observed:

```text
postgres-0   1/1   Running   0
```

## 9.3 Connect to PostgreSQL

```bash
kubectl exec -it postgres-0 -n stateful-demo --   psql -U postgres -d employee-managementdb
```

Expected prompt:

```text
employee-managementdb=#
```

## 9.4 List tables

```sql
\dt
```

The employee table was:

```text
employees
```

## 9.5 Query employee records

```sql
SELECT * FROM employees;
```

Verified three records:

| ID | Name | Occupation | Experience |
|---:|---|---|---:|
| 1 | Manjunath V | Software Engineer | 14 |
| 2 | Gayathri D | Software Engineer | 5 |
| 3 | Manohar V | Salesforce CRM Manager | 17 |

Email addresses are intentionally omitted from this documentation.

Count:

```sql
SELECT COUNT(*) FROM employees;
```

Expected:

```text
3
```

---

# 10. Application Deployment

## 10.1 Final image

```yaml
image: us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
```

## 10.2 Deployment manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: employment-management
  namespace: stateful-demo
  labels:
    app: employment-management
spec:
  replicas: 1
  selector:
    matchLabels:
      app: employment-management
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      labels:
        app: employment-management
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 100
        fsGroup: 101
        fsGroupChangePolicy: OnRootMismatch
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: employment-management
          image: us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          env:
            - name: POSTGRES_HOST
              value: postgres
            - name: POSTGRES_DB
              valueFrom:
                configMapKeyRef:
                  name: postgres-config
                  key: POSTGRES_DB
            - name: POSTGRES_USER
              valueFrom:
                configMapKeyRef:
                  name: postgres-config
                  key: POSTGRES_USER
            - name: POSTGRES_PORT
              valueFrom:
                configMapKeyRef:
                  name: postgres-config
                  key: POSTGRES_PORT
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: POSTGRES_PASSWORD
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            capabilities:
              drop:
                - ALL
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          startupProbe:
            httpGet:
              path: /api/employees
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 12
          readinessProbe:
            httpGet:
              path: /api/employees
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /api/employees
              port: http
            initialDelaySeconds: 30
            periodSeconds: 20
            timeoutSeconds: 3
            failureThreshold: 3
```

## 10.3 Client-side dry run

```bash
kubectl apply --dry-run=client   -f Kubernetes-manifests/deployment.yaml
```

Observed:

```text
deployment.apps/employment-management created (dry run)
```

This validated the manifest without creating the live Deployment.

## 10.4 Apply Deployment

```bash
kubectl apply -f Kubernetes-manifests/deployment.yaml
```

## 10.5 Rollout verification

```bash
kubectl rollout status deployment/employment-management   -n stateful-demo
```

## 10.6 Pod verification

```bash
kubectl get pods -n stateful-demo -o wide
```

Observed:

```text
employment-management-54bb54c7f5-gdkml   1/1   Running   0
postgres-0                               1/1   Running   0
```

---

# 11. Kubernetes Service

## 11.1 Service manifest

```yaml
apiVersion: v1
kind: Service
metadata:
  name: employment-management
  namespace: stateful-demo
  labels:
    app: employment-management
spec:
  type: ClusterIP
  selector:
    app: employment-management
  ports:
    - name: http
      port: 8080
      targetPort: 8080
      protocol: TCP
```

## 11.2 Apply Service

```bash
kubectl apply -f Kubernetes-manifests/service.yaml
```

Observed:

```text
service/employment-management created
```

## 11.3 Verify Service

```bash
kubectl get svc -n stateful-demo
```

Final application Service:

```text
employment-management   ClusterIP   34.118.234.149   <none>   8080/TCP
```

PostgreSQL:

```text
postgres                 ClusterIP   None             <none>   5432/TCP
```

## 11.4 Verify EndpointSlice

Because Kubernetes v1.33+ deprecates the v1 Endpoints API, EndpointSlice was used:

```bash
kubectl get endpointslice -n stateful-demo   -l kubernetes.io/service-name=employment-management
```

Observed:

```text
NAME                          ADDRESSTYPE   PORTS   ENDPOINTS
employment-management-whn9s   IPv4          8080    10.58.128.7
```

This proves that the Service routes to the application Pod at port `8080`.

---

# 12. Gateway API

## 12.1 GatewayClass

```text
gke-l7-global-external-managed
```

Controller:

```text
networking.gke.io/gateway
```

## 12.2 Global static IP

Reserved global static IP:

```text
cloudaiops-gateway-ip
```

Address:

```text
8.233.53.213
```

## 12.3 HTTPS Gateway

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: employment-management-gateway
  namespace: stateful-demo
spec:
  gatewayClassName: gke-l7-global-external-managed
  addresses:
    - type: NamedAddress
      value: cloudaiops-gateway-ip
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          - name: cloudaiops-tls
            kind: Secret
      allowedRoutes:
        namespaces:
          from: Same
```

TLS terminates at the Gateway. The backend Service remains HTTP on port `8080`.

## 12.4 Gateway verification

```bash
kubectl get gateway employment-management-gateway -n stateful-demo
```

Observed:

```text
NAME                            CLASS                            ADDRESS        PROGRAMMED
employment-management-gateway   gke-l7-global-external-managed   8.233.53.213   True
```

`PROGRAMMED=True` confirms successful Gateway programming.

---

# 13. TLS Certificate

## 13.1 Approach

The lab used:

```text
OpenSSL self-signed certificate
        +
Kubernetes TLS Secret
        +
GKE HTTPS Gateway
```

## 13.2 Certificate files

```text
certs/
├── certificate.crt
├── private.key
└── openssl.cnf
```

## 13.3 OpenSSL configuration

```ini
[req]
default_bits = 2048
prompt = no
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = IN
ST = Karnataka
L = Bangalore
O = CloudAIOps
OU = Development
CN = cloudaiops.site

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = cloudaiops.site
DNS.2 = www.cloudaiops.site
```

## 13.4 Certificate verification

The certificate was verified for:

- RSA 2048
- CN `cloudaiops.site`
- SAN `cloudaiops.site`
- SAN `www.cloudaiops.site`
- Server Authentication
- Self-signed issuer

Example:

```bash
openssl x509 -in certs/certificate.crt -text -noout
```

## 13.5 Certificate/private-key matching

The certificate and private key modulus SHA-256 values matched.

The actual key material is intentionally not documented.

## 13.6 Kubernetes TLS Secret

Secret:

```text
cloudaiops-tls
```

Namespace:

```text
stateful-demo
```

Type:

```text
kubernetes.io/tls
```

Verification:

```bash
kubectl get secret cloudaiops-tls -n stateful-demo
```

The Gateway references it through:

```yaml
certificateRefs:
  - name: cloudaiops-tls
    kind: Secret
```

## 13.7 Browser "Not secure"

The browser warning is expected because the certificate is self-signed and is not issued by a publicly trusted Certificate Authority.

The HTTPS connection itself is working.

For production, replace the self-signed certificate with a publicly trusted CA certificate.

---

# 14. DNS / Hostinger

## 14.1 Domain

```text
cloudaiops.site
```

## 14.2 A record

```text
cloudaiops.site -> 8.233.53.213
```

## 14.3 www CNAME

```text
www -> cloudaiops.site
```

## 14.4 DNS verification

```bash
nslookup cloudaiops.site 8.8.8.8
```

The public resolver returned:

```text
8.233.53.213
```

A local DNS resolver timeout does not necessarily indicate an incorrect public DNS record. A public resolver can be used to verify the externally visible record.

---

# 15. HTTPRoute

## 15.1 `httproute.yaml`

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute

metadata:
  name: employment-management
  namespace: stateful-demo
  labels:
    app: employment-management

spec:
  hostnames:
    - cloudaiops.site

  parentRefs:
    - name: employment-management-gateway
      kind: Gateway
      group: gateway.networking.k8s.io
      sectionName: https

  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /

      backendRefs:
        - name: employment-management
          port: 8080
```

## 15.2 Apply HTTPRoute

```bash
kubectl apply -f Kubernetes-manifests/httproute.yaml
```

## 15.3 Verify

```bash
kubectl get httproute -n stateful-demo
```

Observed hostname:

```text
cloudaiops.site
```

## 15.4 Route conditions

```bash
kubectl describe httproute employment-management -n stateful-demo
```

Successful conditions:

```text
ResolvedRefs=True
Accepted=True
Reconciled=True
```

Controller:

```text
networking.gke.io/gateway
```

Meaning:

- `Accepted=True` — Gateway accepted the HTTPRoute.
- `ResolvedRefs=True` — backend Service reference was resolved.
- `Reconciled=True` — GKE successfully reconciled the route.

---

# 16. End-to-End Architecture

```text
                         Internet
                            |
                            | HTTPS :443
                            v
                    +----------------+
                    | cloudaiops.site|
                    +----------------+
                            |
                            v
                    Global Static IP
                      8.233.53.213
                            |
                            v
              +-----------------------------+
              | GKE Gateway                 |
              | employment-management-      |
              | gateway                     |
              |                             |
              | HTTPS :443                  |
              | TLS termination             |
              | cloudaiops-tls              |
              +--------------+--------------+
                             |
                             v
                    +----------------+
                    | HTTPRoute      |
                    | employment-    |
                    | management     |
                    +-------+--------+
                            |
                            | / -> :8080
                            v
              +-----------------------------+
              | Service                     |
              | employment-management:8080  |
              +--------------+--------------+
                             |
                             v
              +-----------------------------+
              | Employment Management Pod   |
              | Spring Boot :8080           |
              +--------------+--------------+
                             |
                             | PostgreSQL :5432
                             v
              +-----------------------------+
              | PostgreSQL Service          |
              | postgres                    |
              +--------------+--------------+
                             |
                             v
                         postgres-0
                             |
                             v
                  employee-managementdb
                             |
                             v
                         employees
```

---

# 17. Verification and Testing

## 17.1 Pods

```bash
kubectl get pods -n stateful-demo -o wide
```

Successful application state:

```text
employment-management-54bb54c7f5-gdkml   1/1   Running   0
```

Successful PostgreSQL state:

```text
postgres-0                               1/1   Running   0
```

## 17.2 Services

```bash
kubectl get svc -n stateful-demo
```

Application Service:

```text
employment-management   ClusterIP   34.118.234.149   <none>   8080/TCP
```

## 17.3 EndpointSlice

```bash
kubectl get endpointslice -n stateful-demo   -l kubernetes.io/service-name=employment-management
```

Endpoint:

```text
10.58.128.7:8080
```

## 17.4 Gateway

```bash
kubectl get gateway employment-management-gateway -n stateful-demo
```

Successful:

```text
ADDRESS        PROGRAMMED
8.233.53.213   True
```

## 17.5 HTTPRoute

```bash
kubectl get httproute employment-management -n stateful-demo
```

Then:

```bash
kubectl describe httproute employment-management -n stateful-demo
```

Successful:

```text
Accepted=True
ResolvedRefs=True
Reconciled=True
```

## 17.6 PostgreSQL

```bash
kubectl exec -it postgres-0 -n stateful-demo --   psql -U postgres -d employee-managementdb
```

Then:

```sql
SELECT * FROM employees;
```

Three records were verified.

---

# 18. Actual Successful HTTPS Test

The public site was tested with:

```bash
curl -vk https://cloudaiops.site
```

Important output:

```text
Host cloudaiops.site:443 was resolved.
IPv4: 8.233.53.213
Trying 8.233.53.213:443...
Established connection
GET / HTTP/1.1
Host: cloudaiops.site
HTTP/1.1 200 OK
```

The response contained the actual Employment Management HTML page, including:

```html
<title>Employment Management</title>
```

Therefore the request successfully traversed:

```text
DNS
  ->
8.233.53.213
  ->
GKE HTTPS Gateway
  ->
HTTPRoute
  ->
employment-management Service
  ->
Spring Boot application
```

The browser may still display a certificate warning because the TLS certificate is self-signed.

---

# 19. PostgreSQL Data Verification

The actual table is:

```text
employees
```

Query:

```sql
SELECT * FROM employees;
```

Three records were verified:

| ID | Name | Occupation | Experience |
|---:|---|---|---:|
| 1 | Manjunath V | Software Engineer | 14 |
| 2 | Gayathri D | Software Engineer | 5 |
| 3 | Manohar V | Salesforce CRM Manager | 17 |

This confirms that employee records were persisted in PostgreSQL.

---

# 20. Troubleshooting

## 20.1 `endpoints "employment-management" not found`

**Problem**

```text
Error from server (NotFound): endpoints "employment-management" not found
```

**Root cause**

The application Service had not yet been created.

**Resolution**

```bash
kubectl apply -f Kubernetes-manifests/service.yaml
```

**Verification**

```text
service/employment-management created
```

Then the Service appeared with port `8080`.

---

## 20.2 Endpoints API deprecation warning

**Problem**

```text
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
```

**Resolution**

Use:

```bash
kubectl get endpointslice -n stateful-demo   -l kubernetes.io/service-name=employment-management
```

**Verification**

```text
10.58.128.7:8080
```

---

## 20.3 HTTPRoute status

**Verification**

```text
Accepted=True
ResolvedRefs=True
Reconciled=True
```

This confirms the route was accepted, the backend Service reference was resolved, and GKE reconciled the route.

---

## 20.4 Gateway status

**Verification**

```text
ADDRESS        PROGRAMMED
8.233.53.213   True
```

This confirms successful Gateway programming.

---

## 20.5 Browser reports "Not secure"

**Problem**

Browser certificate/security warning.

**Root cause**

The certificate is self-signed.

**Resolution**

No infrastructure correction was required for this lab.

**Verification**

```bash
curl -vk https://cloudaiops.site
```

returned:

```text
HTTP/1.1 200 OK
```

**Production resolution**

Use a publicly trusted CA certificate.

---

## 20.6 `latest` was older

The local `latest` tag pointed to:

```text
CREATED=2026-08-26T03:19:48.308673416Z
```

while the later `1.0.0` and `3.0.0` images were created on:

```text
2026-08-31T09:39:28.891341003Z
```

Therefore the `latest` tag was not treated as the latest build.

---

## 20.7 `1.0.0` and `3.0.0` had different IDs

```text
1.0.0 -> sha256:4cd2ee3c...
3.0.0 -> sha256:9577766f...
```

They had identical creation timestamps but different image IDs.

**Resolution**

Creation timestamp alone was not used to select the deployment image. The final choice was explicitly `3.0.0`.

---

# 21. Final Validation Checklist

- [x] Docker image created
- [x] Docker image inspected
- [x] Linux/AMD64 verified
- [x] Artifact Registry configured
- [x] Docker authentication configured
- [x] `3.0.0` image pushed
- [x] GKE cluster available
- [x] `stateful-demo` namespace used
- [x] PostgreSQL running
- [x] PostgreSQL Service available
- [x] PostgreSQL database verified
- [x] `employees` table verified
- [x] Three employee records verified
- [x] Application Deployment applied
- [x] Application Pod running
- [x] Application Pod ready `1/1`
- [x] Application Service created
- [x] EndpointSlice created
- [x] Endpoint points to application Pod
- [x] TLS certificate generated
- [x] Certificate/private-key matching verified
- [x] `cloudaiops-tls` Secret created
- [x] HTTPS Gateway configured
- [x] Gateway programmed
- [x] Gateway IP `8.233.53.213` assigned
- [x] DNS configured
- [x] `cloudaiops.site` resolved to `8.233.53.213`
- [x] HTTPRoute applied
- [x] HTTPRoute accepted
- [x] HTTPRoute references resolved
- [x] HTTPRoute reconciliation succeeded
- [x] HTTPS connection established
- [x] Application returned `HTTP/1.1 200 OK`
- [x] Application UI accessible
- [x] PostgreSQL persistence verified

---

# 22. Production Improvements

> The following are recommendations and should not be confused with steps actually executed in this lab.

## TLS

Replace the self-signed certificate with a publicly trusted certificate so browsers recognize the site without a certificate warning.

## Secrets

Do not store private keys, passwords, or raw secret material in Git.

Consider:

- Kubernetes Secrets
- Google Secret Manager
- Workload Identity
- Secret rotation

## Database

Do not use simple lab credentials in production.

Use:

- Strong credentials
- Credential rotation
- Restricted database access
- Backups
- Disaster recovery

## Container Images

For stronger reproducibility, consider deploying an immutable digest:

```text
image@sha256:<DIGEST>
```

rather than relying only on a mutable tag.

## Security

Consider:

- NetworkPolicies
- Least-privilege RBAC
- Non-root containers
- Dropped Linux capabilities
- Pod Security standards
- Image vulnerability scanning
- Secure secret management

## Reliability

Consider:

- Multiple application replicas
- Horizontal Pod Autoscaler
- PodDisruptionBudget
- PostgreSQL backups
- Monitoring
- Centralized logging
- Alerting

## HTTPS

Use HTTPS-only production traffic and an appropriate HTTP-to-HTTPS strategy.

---

# 23. Useful Commands Reference

## Git

```bash
git status
git branch --show-current
git add .
git commit -m "Your commit message"
git push origin feature/Employment-Management
```

## Docker

```bash
docker images | grep employment
```

```bash
docker inspect <IMAGE>
```

```bash
docker inspect <IMAGE>   --format='ID={{.Id}} CREATED={{.Created}} ARCH={{.Architecture}} OS={{.Os}}'
```

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

```bash
docker push   us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
```

## Artifact Registry

```bash
gcloud artifacts docker images list   us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management   --include-tags
```

## Kubernetes

```bash
kubectl get pods -n stateful-demo
```

```bash
kubectl get svc -n stateful-demo
```

```bash
kubectl get endpointslice -n stateful-demo   -l kubernetes.io/service-name=employment-management
```

```bash
kubectl get deployment -n stateful-demo
```

```bash
kubectl rollout status deployment/employment-management   -n stateful-demo
```

```bash
kubectl get gateway employment-management-gateway   -n stateful-demo
```

```bash
kubectl get httproute -n stateful-demo
```

```bash
kubectl describe httproute employment-management   -n stateful-demo
```

Apply manifests:

```bash
kubectl apply -f Kubernetes-manifests/deployment.yaml
kubectl apply -f Kubernetes-manifests/service.yaml
kubectl apply -f Kubernetes-manifests/httproute.yaml
```

## PostgreSQL

```bash
kubectl exec -it postgres-0 -n stateful-demo --   psql -U postgres -d employee-managementdb
```

Inside `psql`:

```sql
\dt
```

```sql
SELECT * FROM employees;
```

```sql
SELECT COUNT(*) FROM employees;
```

Exit:

```sql
\q
```

## DNS

```bash
nslookup cloudaiops.site 8.8.8.8
```

## HTTPS

```bash
curl -vk https://cloudaiops.site
```

API:

```bash
curl -vk https://cloudaiops.site/api/employees
```

---

# 24. Final Deployment Summary

The Employment Management application was successfully deployed through:

```text
Docker
  ->
Google Artifact Registry
  ->
GKE Deployment
  ->
ClusterIP Service
  ->
GKE Gateway API
  ->
HTTPRoute
  ->
HTTPS
  ->
cloudaiops.site
```

Final image:

```text
us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:3.0.0
```

Gateway:

```text
employment-management-gateway
```

HTTPRoute:

```text
employment-management
```

Application Service:

```text
employment-management:8080
```

PostgreSQL Service:

```text
postgres:5432
```

Gateway IP:

```text
8.233.53.213
```

Domain:

```text
https://cloudaiops.site
```

The final HTTPS test returned:

```text
HTTP/1.1 200 OK
```

The PostgreSQL `employees` table contained three persisted employee records.

The only known browser-level limitation is the self-signed TLS certificate, which causes a trust warning even though HTTPS connectivity is functioning correctly.

---

## Security Reminder

Never commit:

```text
certs/private.key
```

or raw TLS/Kubernetes secret values to GitHub.

Document the commands and configuration required to recreate secrets, but keep actual secret material outside source control.
