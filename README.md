# Scheduled Task Operator

A Kubernetes operator that extends the k8s API with a `ScheduledTask` custom resource, dynamically managing the full lifecycle of CronJobs through a reconciliation control loop.

Built with Python and [kopf](https://kopf.readthedocs.io/), deployed via Helm.

---

## Why This Exists

Native Kubernetes CronJobs are powerful but low-level. This operator introduces a higher-level abstraction — `ScheduledTask` — that adds:

- **Pause/resume** without deleting the underlying CronJob
- **Jitter** to distribute scheduled load and prevent thundering herd
- **Status reporting** so resources self-describe their runtime state
- **Automatic reconciliation** — drift between desired and actual state is corrected automatically

---

## Architecture

```
User applies ScheduledTask CR
        │
        ▼
  kopf watches API server
        │
        ▼
  Operator reconciles
        │
        ├── on_create → creates CronJob
        ├── on_update → patches or deletes CronJob
        └── on_delete → cleans up CronJob
        │
        ▼
  Status written back to ScheduledTask
```

---

## Custom Resource Example

```yaml
apiVersion: ops.io/v1
kind: ScheduledTask
metadata:
  name: data-pipeline
  namespace: default
spec:
  schedule: "*/5 * * * *"
  image: busybox
  command: ["echo", "running pipeline"]
  suspended: false
  jitter: 120         # up to 2 min random offset applied at creation
```

After applying, check the operator-managed status:

```bash
kubectl get scheduledtask data-pipeline -o yaml
```

```yaml
status:
  activeCronJob: true
  suspended: false
  resolvedSchedule: "2-59/5"   # jitter applied
```

---

## Features

| Feature | Description |
|---|---|
| CRD-based API | `ScheduledTask` is a first-class k8s resource |
| Full lifecycle management | Create, update, and delete CronJobs automatically |
| Pause / Resume | Set `suspended: true` to halt scheduling without losing config |
| Jitter | Random minute offset prevents thundering herd across many tasks |
| Status subresource | Runtime state written back onto the resource |
| Helm packaging | One command install with configurable values |

---

## Local Development

### Prerequisites

- Docker Desktop
- minikube
- kubectl
- Python 3.10+
- Helm

### Setup

```bash
# Start local cluster
minikube start

# Install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Apply the CRD
kubectl apply -f crd/scheduledtask.yaml

# Run the operator
kopf run operator/main.py --verbose
```

### Apply an example task

```bash
kubectl apply -f examples/example-task.yaml
kubectl get scheduledtasks
kubectl get cronjobs
```

---

## Deployment via Helm

```bash
# Install the operator into your cluster
helm install scheduled-task-operator ./chart

# Customize values
helm install scheduled-task-operator ./chart \
  --set image.repository=your-registry/scheduled-task-operator \
  --set image.tag=v1.0.0
```

---

## Project Structure

```
scheduled-task-operator/
├── chart/                        # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── crd.yaml
│       ├── deployment.yaml
│       ├── serviceaccount.yaml
│       ├── clusterrole.yaml
│       └── clusterrolebinding.yaml
├── crd/
│   └── scheduledtask.yaml        # Standalone CRD manifest
├── operator/
│   └── main.py                   # Operator logic
├── examples/
│   └── example-task.yaml         # Sample ScheduledTask resource
└── requirements.txt
```

---

## Tech Stack

- **Python** — operator logic
- **kopf** — Kubernetes operator framework
- **kubernetes-client** — k8s API interaction
- **Helm** — operator packaging and deployment
- **minikube** — local cluster for development