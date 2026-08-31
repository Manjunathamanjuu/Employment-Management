I want you to create or completely update the file:

Kubernetes-manifests/PVC.md

Create ONE comprehensive, production-quality Markdown document that documents the complete PersistentVolume (PV) and PersistentVolumeClaim (PVC) implementation, configuration, troubleshooting, and persistence validation for my Employment Management application running on Google Kubernetes Engine (GKE).

IMPORTANT:
- This is documentation only.
- Do NOT create or modify Kubernetes YAML files as part of this task.
- Do NOT create a separate PV YAML because this setup uses dynamic PV provisioning through the GKE StorageClass.
- Use the actual configuration and commands provided below.
- Keep the documentation technically accurate and practical.
- Do not invent resources, names, values, commands, or test results.
- Use clear headings, tables, YAML snippets, command examples, expected outputs, and explanations.
- Explain what each important command does.
- The final PVC.md should be usable as project documentation for another developer/DevOps engineer.

============================================================
1. APPLICATION / GKE ENVIRONMENT
============================================================

Application:
Employment Management

GKE Cluster:
employment-management-gke

Region:
us-central1

Namespace:
default

Deployment:
employment-management

Application container port:
8080

Persistent storage mount path:
/app/data

============================================================
2. STORAGE ARCHITECTURE
============================================================

Document the following architecture:

Employment Management Deployment
        |
        +---- Pod 1
        |
        +---- Pod 2
        |
        +---- /app/data
                  |
                  v
        PersistentVolumeClaim
        employment-management-pvc
                  |
                  v
        Dynamically Provisioned
        PersistentVolume
                  |
                  v
        GKE Persistent Disk
                  |
                  v
        StorageClass: standard-rwo

Clearly explain:

- The application uses a PVC.
- The PVC requests persistent storage.
- The StorageClass dynamically provisions the PV.
- GKE creates the underlying persistent storage.
- The application accesses the storage through /app/data.
- The PV does not need to be manually created for this configuration.

============================================================
3. VERIFY GKE CLUSTER
============================================================

Document this command:

gcloud container clusters list

Mention that the relevant cluster is:

employment-management-gke

Region:

us-central1

Also document that the cluster was running successfully.

============================================================
4. CHECK AVAILABLE STORAGECLASSES
============================================================

Document:

kubectl get storageclass

The observed StorageClasses were:

dynamic-rwo
premium-rwo
standard
standard-rwo

The default StorageClass was:

standard-rwo

Document that:

standard-rwo

uses:

pd.csi.storage.gke.io

Explain that this is the GKE Persistent Disk CSI provisioner.

Also document:

kubectl get storageclass standard-rwo -o yaml

Explain that the StorageClass configuration should be checked before creating the PVC.

============================================================
5. STORAGECLASS BINDING MODE
============================================================

Document that the cluster showed:

standard-rwo

with:

WaitForFirstConsumer

Explain what this means:

- The PVC may initially remain Pending.
- The PV may be dynamically provisioned when a Pod using the PVC is scheduled.
- Therefore, seeing PVC status Pending immediately after creation is not necessarily an error.
- Once the application Pod is scheduled and the storage is provisioned, the PVC should become Bound.

============================================================
6. PVC MANIFEST
============================================================

Document the file:

Kubernetes-manifests/persistentvolumeclaim.yaml

Use this PVC configuration:

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: employment-management-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard-rwo
  resources:
    requests:
      storage: 10Gi

Explain every important field:

apiVersion
kind
metadata.name
accessModes
storageClassName
resources.requests.storage

Clearly explain:

ReadWriteOnce (RWO)

and what it means in this GKE setup.

============================================================
7. APPLY PVC
============================================================

Document:

kubectl apply -f Kubernetes-manifests/persistentvolumeclaim.yaml

Then:

kubectl get pvc -n default

Explain that the PVC may initially show:

Pending

because the StorageClass uses:

WaitForFirstConsumer

After the Pod is scheduled and storage is provisioned, it should become:

Bound

============================================================
8. ACTUAL PVC RESULT
============================================================

The PVC successfully became:

NAME:
employment-management-pvc

STATUS:
Bound

VOLUME:
pvc-d4c95ece-b57d-4e4c-bfb0-968a2804a7df

CAPACITY:
10Gi

ACCESS MODE:
RWO

STORAGECLASS:
standard-rwo

Document the example command:

kubectl get pvc -n default

Show the expected structure of the result.

============================================================
9. DYNAMIC PV PROVISIONING
============================================================

Document:

kubectl get pv

The dynamically created PV was:

pvc-d4c95ece-b57d-4e4c-bfb0-968a2804a7df

It had:

Capacity: 10Gi
Access Mode: RWO
Reclaim Policy: Delete
Status: Bound
Claim: default/employment-management-pvc
StorageClass: standard-rwo

Explain clearly:

There is no manually created pv.yaml in this setup.

The flow is:

PVC
  |
  v
StorageClass
  |
  v
GKE CSI Driver
  |
  v
Persistent Disk
  |
  v
Dynamic PV

============================================================
10. PVC DESCRIPTION
============================================================

Document:

kubectl describe pvc employment-management-pvc -n default

Explain that this command is useful for:

- Checking PVC status
- Checking volume binding
- Checking StorageClass
- Checking events
- Troubleshooting Pending PVCs

============================================================
11. PV DESCRIPTION
============================================================

Document:

kubectl describe pv pvc-d4c95ece-b57d-4e4c-bfb0-968a2804a7df

Explain that this can be used to inspect:

- Capacity
- Access mode
- Claim
- StorageClass
- Reclaim policy
- CSI configuration
- Events

============================================================
12. DEPLOYMENT PVC MOUNT
============================================================

Document that the Deployment must mount the PVC.

The container contains:

volumeMounts:
  - name: application-data
    mountPath: /app/data

The Pod specification contains:

volumes:
  - name: application-data
    persistentVolumeClaim:
      claimName: employment-management-pvc

Explain that:

volumeMounts

belongs inside the container definition.

While:

volumes

belongs inside the Pod spec, at the same level as:

containers

Explain the relationship:

volume name:
application-data

PVC:
employment-management-pvc

mount path:
/app/data

============================================================
13. DEPLOYMENT CONFIGURATION
============================================================

The application Deployment has:

replicas: 2

Deployment name:

employment-management

Container name:

employment-management

Image:

us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management/employment-management:1.0.0

Port:

8080

Explain that both application Pods mount the PVC.

Also document the existing rolling update strategy:

strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1

Do not change the Deployment configuration. This section is documentation only.

============================================================
14. SECURITY CONTEXT
============================================================

The application runs as a non-root user.

Document:

securityContext:
  runAsNonRoot: true
  runAsUser: 100
  fsGroup: 101
  fsGroupChangePolicy: OnRootMismatch
  seccompProfile:
    type: RuntimeDefault

Also document the container security configuration:

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop:
      - ALL

Explain why fsGroup is important for mounted persistent storage when the application does not run as root.

============================================================
15. PERMISSION PROBLEM ENCOUNTERED
============================================================

Document the actual issue that occurred.

Inside the container:

id

returned:

uid=100(app) gid=101(app) groups=101(app)

The mounted directory initially showed:

drwxr-xr-x 3 root root /app/data

When attempting to write:

echo "Persistence Test" > /app/data/test.txt

the result was:

Permission denied

Explain that the container was running as a non-root user while the mounted directory was owned by root.

============================================================
16. PERMISSION FIX
============================================================

Document that the Pod security context was updated with:

fsGroup: 101

and:

fsGroupChangePolicy: OnRootMismatch

Explain how this allows the application group to access the mounted persistent storage.

Do not claim that permissions were changed manually if they were not.

Show how to verify:

kubectl exec -it <pod-name> -n default -- id

and:

kubectl exec -it <pod-name> -n default -- ls -ld /app/data

============================================================
17. APPLY UPDATED DEPLOYMENT
============================================================

Document:

kubectl apply -f Kubernetes-manifests/deployment.yaml

Then:

kubectl rollout status deployment/employment-management -n default

Then:

kubectl get pods -n default

Then:

kubectl get pods -n default -o wide

Explain that after a Deployment update, Kubernetes creates replacement Pods according to the RollingUpdate strategy.

============================================================
18. ENTER THE POD
============================================================

Document:

kubectl exec -it <pod-name> -n default -- sh

Then:

cd /app/data

Then:

pwd

Expected:

/app/data

Then:

ls -lh

Explain that /app/data is the mounted persistent volume.

============================================================
19. WINDOWS GIT BASH PATH CONVERSION ISSUE
============================================================

This project is being operated from Windows Git Bash.

Document the problem encountered:

kubectl exec ... -- ls -lh /app/data/

could be converted by Git Bash into something similar to:

C:/Program Files/Git/app/data/

This causes:

No such file or directory

Explain that Git Bash performs MSYS path conversion.

Document the solution:

MSYS_NO_PATHCONV=1

Example:

MSYS_NO_PATHCONV=1 kubectl exec <pod-name> -n default -- ls -lh /app/data/

For reading a file:

MSYS_NO_PATHCONV=1 kubectl exec <pod-name> -n default -- cat /app/data/<file>

Explain when this workaround is required.

============================================================
20. CREATE USEFUL PERSISTENCE TEST DATA
============================================================

Document that a meaningful JSON file was created instead of a simple text message.

File:

/app/data/employment-management-test.json

The JSON contained application, infrastructure, employee, and persistence test information.

Use the following representative content:

{
  "application": "Employment Management",
  "environment": "GKE",
  "cluster": "employment-management-gke",
  "namespace": "default",
  "storage": {
    "pvc": "employment-management-pvc",
    "storageClass": "standard-rwo",
    "capacity": "10Gi",
    "mountPath": "/app/data"
  },
  "employees": [
    {
      "employeeId": "EMP-1001",
      "name": "Manjunath V",
      "department": "Cloud Operations",
      "designation": "Cloud Engineer",
      "employmentType": "Full-Time",
      "status": "ACTIVE",
      "location": "Bengaluru",
      "joiningDate": "2024-01-15"
    },
    {
      "employeeId": "EMP-1002",
      "name": "Harsha Kumar",
      "department": "Engineering",
      "designation": "Senior Software Engineer",
      "employmentType": "Full-Time",
      "status": "ACTIVE",
      "location": "Bengaluru",
      "joiningDate": "2023-08-21"
    },
    {
      "employeeId": "EMP-1003",
      "name": "Deeksha Rao",
      "department": "Human Resources",
      "designation": "HR Executive",
      "employmentType": "Full-Time",
      "status": "ACTIVE",
      "location": "Hyderabad",
      "joiningDate": "2025-02-10"
    }
  ],
  "persistenceTest": {
    "purpose": "Validate Kubernetes PersistentVolume persistence",
    "createdAt": "2026-08-28",
    "expectedBehavior": "Employee data must remain available after Pod recreation",
    "testStatus": "PASSED",
    "verifiedAfterPodRecreation": true
  }
}

============================================================
21. VERIFY TEST JSON
============================================================

Document:

MSYS_NO_PATHCONV=1 kubectl exec <pod-name> -n default -- ls -lh /app/data/

Then:

MSYS_NO_PATHCONV=1 kubectl exec <pod-name> -n default -- cat /app/data/employment-management-test.json

Explain that this confirms the application can write and read data from the mounted PVC.

============================================================
22. FIRST PERSISTENCE TEST
============================================================

Document the complete test:

1. Create employment-management-test.json.
2. Store it under /app/data.
3. Confirm the file exists.
4. Delete the Pod.
5. Kubernetes creates a replacement Pod.
6. The replacement Pod mounts the same PVC.
7. Verify the JSON file still exists.
8. Read the JSON file from the replacement Pod.

Commands:

kubectl delete pod <pod-name> -n default

Then:

kubectl get pods -n default -w

Wait until the replacement Pod becomes:

1/1 Running

Then:

MSYS_NO_PATHCONV=1 kubectl exec <new-pod-name> -n default -- cat /app/data/employment-management-test.json

Result:

PVC Persistence Test #1: PASSED

============================================================
23. SECOND PERSISTENCE TEST
============================================================

Document that a second test was performed to verify the PVC again.

Create:

/app/data/pvc-second-test.txt

With useful content such as:

PVC Persistence Test - Run 2
Application: Employment Management
Cluster: employment-management-gke
PVC: employment-management-pvc
Storage Class: standard-rwo
Storage Capacity: 10Gi
Purpose: Verify data survives Pod deletion and recreation
Status: TEST_CREATED

Verify:

MSYS_NO_PATHCONV=1 kubectl exec <pod-name> -n default -- cat /app/data/pvc-second-test.txt

============================================================
24. DELETE POD FOR SECOND TEST
============================================================

Document:

kubectl delete pod <pod-name> -n default

Important:

DO NOT delete the PVC.

The Deployment automatically creates a replacement Pod.

Watch:

kubectl get pods -n default -w

Wait for:

1/1 Running

============================================================
25. VERIFY SECOND TEST
============================================================

Get the new Pod:

kubectl get pods -n default

Then:

MSYS_NO_PATHCONV=1 kubectl exec <new-pod-name> -n default -- cat /app/data/pvc-second-test.txt

Expected result:

The file created before Pod deletion is still available.

Result:

PVC Persistence Test #2: PASSED

============================================================
26. IMPORTANT DISTINCTION: POD vs PVC
============================================================

Clearly explain:

Deleting a Pod:

kubectl delete pod <pod-name>

does NOT delete the PVC.

Therefore:

Pod deletion
    |
    v
New Pod
    |
    v
Same PVC
    |
    v
Same persistent data

But deleting the PVC is different.

Do NOT execute:

kubectl delete pvc employment-management-pvc

during a persistence test.

============================================================
27. RECLAIM POLICY
============================================================

The dynamically created PV showed:

Reclaim Policy: Delete

Explain what this means.

Important:

If the PVC is deleted, the dynamically provisioned storage may also be deleted according to the reclaim policy.

Therefore, for persistence testing:

Delete Pod:
SAFE for testing persistence

Delete PVC:
DO NOT do this unless intentionally deleting the storage

============================================================
28. FINAL VALIDATION COMMANDS
============================================================

Document all of these commands:

kubectl get storageclass

kubectl get pvc -n default

kubectl get pv

kubectl get pods -n default

kubectl get pods -n default -o wide

kubectl get deployment employment-management -n default

kubectl describe pvc employment-management-pvc -n default

kubectl describe pv pvc-d4c95ece-b57d-4e4c-bfb0-968a2804a7df

============================================================
29. EXPECTED FINAL STATE
============================================================

Document the final expected state:

PVC:

employment-management-pvc
STATUS: Bound
CAPACITY: 10Gi
ACCESS MODE: RWO
STORAGECLASS: standard-rwo

PV:

pvc-d4c95ece-b57d-4e4c-bfb0-968a2804a7df
STATUS: Bound
CAPACITY: 10Gi

Deployment:

employment-management
READY: 2/2
UP-TO-DATE: 2
AVAILABLE: 2

Pods:

2 Pods
STATUS: Running

Mount:

/app/data

============================================================
30. FINAL STORAGE FLOW
============================================================

Include this diagram:

Application
    |
    v
Deployment
    |
    v
Pod
    |
    | mountPath: /app/data
    v
PersistentVolumeClaim
employment-management-pvc
    |
    | storageClassName: standard-rwo
    v
GKE CSI Driver
pd.csi.storage.gke.io
    |
    v
Persistent Disk
    |
    v
PersistentVolume
    |
    v
Persistent Data

============================================================
31. PVC/PV SUMMARY TABLE
============================================================

Create a final table with:

Application:
Employment Management

Cluster:
employment-management-gke

Region:
us-central1

Namespace:
default

Deployment:
employment-management

PVC:
employment-management-pvc

PV:
pvc-d4c95ece-b57d-4e4c-bfb0-968a2804a7df

Capacity:
10Gi

Access Mode:
ReadWriteOnce

StorageClass:
standard-rwo

Provisioner:
pd.csi.storage.gke.io

Mount Path:
/app/data

PVC Status:
Bound

PV Status:
Bound

Replica Count:
2

Persistence Test:
PASSED

============================================================
32. TROUBLESHOOTING SECTION
============================================================

Include troubleshooting for:

A. PVC Pending

Commands:

kubectl get pvc -n default

kubectl describe pvc employment-management-pvc -n default

kubectl get storageclass

Explain WaitForFirstConsumer.

B. Permission denied

Commands:

kubectl exec -it <pod-name> -n default -- id

kubectl exec -it <pod-name> -n default -- ls -ld /app/data

Explain runAsUser and fsGroup.

C. Git Bash converts /app/data

Use:

MSYS_NO_PATHCONV=1

D. Pod is not starting

Commands:

kubectl get pods -n default

kubectl describe pod <pod-name> -n default

kubectl get events -n default --sort-by=.lastTimestamp

E. PVC is not Bound

Commands:

kubectl describe pvc employment-management-pvc -n default

kubectl get pv

kubectl get storageclass

============================================================
33. DO NOT MANUALLY CREATE PV
============================================================

Add a clear section:

"For this GKE configuration, do not create a static PV YAML."

Explain:

The PVC specifies:

storageClassName: standard-rwo

GKE dynamically provisions the PV.

Therefore the repository needs:

Kubernetes-manifests/persistentvolumeclaim.yaml

but does not need:

Kubernetes-manifests/persistentvolume.yaml

for this particular configuration.

============================================================
34. DOCUMENTATION BEST PRACTICES
============================================================

Make the final PVC.md:

- Easy to read
- Suitable for GitHub
- Suitable for a DevOps/Kubernetes project
- Beginner-friendly but technically accurate
- Command-driven
- Include expected output where useful
- Include warnings for destructive commands
- Clearly distinguish PVC, PV, StorageClass, Persistent Disk, Pod, and Deployment
- Avoid unnecessary repetition
- Do not claim that a static PV was created
- Do not claim that the PVC itself is the physical disk
- Clearly explain dynamic provisioning
- Clearly explain Pod recreation versus PVC deletion

============================================================
35. FINAL CHECK
============================================================

After generating PVC.md:

1. Make sure ALL the above steps are included.
2. Make sure the commands are syntactically correct.
3. Make sure YAML indentation is correct.
4. Make sure the document refers to the actual resource names.
5. Make sure the persistence tests are documented.
6. Make sure the permission issue and fsGroup solution are documented.
7. Make sure the Windows Git Bash MSYS_NO_PATHCONV issue is documented.
8. Make sure the dynamic PV provisioning explanation is included.
9. Make sure there is no unnecessary pv.yaml recommendation.
10. Keep everything in ONE file:

Kubernetes-manifests/PVC.md

Do not modify any other project files.