import kopf
import kubernetes

# Load k8s config (uses minikube's kubeconfig automatically)
kubernetes.config.load_kube_config()

batch_v1 = kubernetes.client.BatchV1Api()


@kopf.on.create('ops.io', 'v1', 'scheduledtasks')
def on_create(spec, name, namespace, logger, **kwargs):
    schedule = spec['schedule']
    image = spec['image']
    command = spec['command']
    suspended = spec.get('suspended', False)

    logger.info(f"ScheduledTask '{name}' created. Schedule: {schedule}")

    if suspended:
        logger.info(f"ScheduledTask '{name}' is suspended, skipping CronJob creation")
        patch_status(name, namespace, {
            "activeCronJob": False,
            "suspended": True,
            "lastScheduledTime": None
        })
        return

    cronjob = build_cronjob(name, namespace, schedule, image, command)
    batch_v1.create_namespaced_cron_job(namespace=namespace, body=cronjob)
    logger.info(f"CronJob created for '{name}'")

    patch_status(name, namespace, {
        "activeCronJob": True,
        "suspended": False,
        "lastScheduledTime": None
    })


@kopf.on.update('ops.io', 'v1', 'scheduledtasks')
def on_update(spec, name, namespace, logger, **kwargs):
    schedule = spec['schedule']
    image = spec['image']
    command = spec['command']
    suspended = spec.get('suspended', False)

    logger.info(f"ScheduledTask '{name}' updated")

    try:
        existing = batch_v1.read_namespaced_cron_job(name=name, namespace=namespace)

        if suspended:
            logger.info(f"ScheduledTask '{name}' suspended, deleting CronJob")
            batch_v1.delete_namespaced_cron_job(name=name, namespace=namespace)
            patch_status(name, namespace, {
                "activeCronJob": False,
                "suspended": True,
            })
            return

        existing.spec.schedule = schedule
        existing.spec.job_template.spec.template.spec.containers[0].image = image
        existing.spec.job_template.spec.template.spec.containers[0].command = command
        batch_v1.replace_namespaced_cron_job(name=name, namespace=namespace, body=existing)
        logger.info(f"CronJob updated for '{name}'")
        patch_status(name, namespace, {
            "activeCronJob": True,
            "suspended": False,
        })

    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404 and not suspended:
            cronjob = build_cronjob(name, namespace, schedule, image, command)
            batch_v1.create_namespaced_cron_job(namespace=namespace, body=cronjob)
            logger.info(f"CronJob created for '{name}'")
            patch_status(name, namespace, {
                "activeCronJob": True,
                "suspended": False,
            })


@kopf.on.delete('ops.io', 'v1', 'scheduledtasks')
def on_delete(name, namespace, logger, **kwargs):
    logger.info(f"ScheduledTask '{name}' deleted, cleaning up CronJob")
    try:
        batch_v1.delete_namespaced_cron_job(name=name, namespace=namespace)
        logger.info(f"CronJob deleted for '{name}'")
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"CronJob '{name}' already gone, nothing to delete")
        else:
            raise


def build_cronjob(name, namespace, schedule, image, command):
    return {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "schedule": schedule,
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "restartPolicy": "OnFailure",
                            "containers": [
                                {
                                    "name": name,
                                    "image": image,
                                    "command": command,
                                }
                            ],
                        }
                    }
                }
            },
        },
    }

def patch_status(name, namespace, status_patch):
    custom_api = kubernetes.client.CustomObjectsApi()
    custom_api.patch_namespaced_custom_object_status(
        group="ops.io",
        version="v1",
        namespace=namespace,
        plural="scheduledtasks",
        name=name,
        body={"status": status_patch}
    )