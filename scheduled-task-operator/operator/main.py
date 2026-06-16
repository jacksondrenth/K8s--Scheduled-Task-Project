import kopf
import kubernetes
import random

# Load k8s config (uses minikube's kubeconfig automatically)
kubernetes.config.load_kube_config()

batch_v1 = kubernetes.client.BatchV1Api()

def apply_jitter(schedule, jitter_seconds):
    """
    Adds a random minute offset to a cron schedule.
    jitter_seconds is the max offset — we pick randomly between 0 and it.
    """
    if not jitter_seconds:
        return schedule

    jitter_minutes = random.randint(0, max(1, jitter_seconds // 60))

    if jitter_minutes == 0:
        return schedule

    parts = schedule.split()
    if len(parts) != 5:
        return schedule  # don't touch malformed expressions

    minute_field = parts[0]

    # Only handle simple cases — exact minutes or */n patterns
    if minute_field.isdigit():
        new_minute = (int(minute_field) + jitter_minutes) % 60
        parts[0] = str(new_minute)
    elif minute_field.startswith('*/'):
        # Can't shift */n cleanly, so prepend a fixed offset minute instead
        # e.g. */5 with 2 min jitter -> 2-59/5
        offset = jitter_minutes % int(minute_field[2:])
        parts[0] = f"{offset}-59/{minute_field[2:]}"

    jittered = ' '.join(parts)
    return jittered

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
            "activeCronJob": True,
            "suspended": False,
            "lastScheduledTime": None,
            "resolvedSchedule": apply_jitter(schedule, jitter)
        })
        return

    jitter = spec.get('jitter', 0)
    cronjob = build_cronjob(name, namespace, schedule, image, command, jitter)
    batch_v1.create_namespaced_cron_job(namespace=namespace, body=cronjob)
    logger.info(f"CronJob created for '{name}'")

    patch_status(name, namespace, {
        "activeCronJob": True,
        "suspended": False,
        "lastScheduledTime": None,
        "resolvedSchedule": apply_jitter(schedule, jitter)
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
                "activeCronJob": True,
                "suspended": False,
                "resolvedSchedule": apply_jitter(schedule, jitter)
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
            "resolvedSchedule": apply_jitter(schedule, jitter)
        })

    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404 and not suspended:
            jitter = spec.get('jitter', 0)
            cronjob = build_cronjob(name, namespace, schedule, image, command, jitter)
            batch_v1.create_namespaced_cron_job(namespace=namespace, body=cronjob)
            logger.info(f"CronJob created for '{name}'")
            patch_status(name, namespace, {
                "activeCronJob": True,
                "suspended": False,
                "resolvedSchedule": apply_jitter(schedule, jitter)
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


def build_cronjob(name, namespace, schedule, image, command, jitter=0):
    final_schedule = apply_jitter(schedule, jitter)
    return {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "schedule": final_schedule,
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

