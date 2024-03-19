import threading
import time

import docker  # type: ignore
from loguru import logger

cpu_limit = 0.5  # 核心


def set_cpu_limit(cpu_limit, cgroup_path):
    logger.info(f"set limit: CPU 0.1 {cgroup_path} sleep 15s")
    time.sleep(60)
    logger.info(f"set limit: CPU 0.1 {cgroup_path} wake!")

    with open(f"{cgroup_path}/cpu.cfs_period_us", "w") as f:
        f.write("100000")

    with open(f"{cgroup_path}/cpu.cfs_quota_us", "w") as f:
        f.write(str(int(cpu_limit * 100000)))


def build_limiter():
    # # Check if the device is a logical volume
    def set_limit(container_id: str):
        cgroup_path = f"/sys/fs/cgroup/cpu/docker/{container_id}"
        threading.Thread(
            target=set_cpu_limit,
            args=(
                cpu_limit,
                cgroup_path,
            ),
        ).start()

    return set_limit


def check_env_var(container_id, key):
    client = docker.from_env()
    container = client.containers.get(container_id)
    env_vars = container.attrs["Config"]["Env"]

    for var in env_vars:
        if var.startswith(key + "="):
            return True
    return False


def run_watcher(limiter):
    client = docker.from_env()
    for event in client.events(decode=True):
        try:
            if event["Type"] == "container" and event["Action"] in ["start", "restart"]:
                container_id = event["id"]
                key = "range_worker"
                if not check_env_var(container_id, key):
                    continue
                logger.info(f"容器启动：{container_id}")
                limiter(container_id)
        except Exception as msg:
            logger.exception(msg)


if __name__ == "__main__":
    limiter = build_limiter()
    run_watcher(limiter)
