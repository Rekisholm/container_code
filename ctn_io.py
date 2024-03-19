import time
import threading
import docker
from loguru import logger

key = "range_worker"
key2 = "range_bugfix"
max_io_limit = 1 * 1024 * 1024 * 1024  # 1GB

def check_env_var(container, key):
    env_vars = container.attrs["Config"]["Env"]
    for var in env_vars:
        if var.startswith(key + "="):
            return True
    return False

counter = 0

def check_and_kill_container(container):
    if not check_env_var(container, key) and not check_env_var(container, key2):
        return
    stats_obj = container.stats(stream=False)
    io_stats = stats_obj["blkio_stats"]["io_service_bytes_recursive"]
    read_bytes = next((x["value"] for x in io_stats if x["op"] == "Read"), 0)
    write_bytes = next((x["value"] for x in io_stats if x["op"] == "Write"), 0)
    if read_bytes > max_io_limit or write_bytes > max_io_limit:
        logger.info(
            f"Killing container {container.name} due to high block IO: I:{read_bytes / 1024 / 1024}MB O:{write_bytes / 1024 / 1024}MB "
        )
        container.kill()
        container.remove()

def worker(container):
    global counter
    try:
        counter += 1
        check_and_kill_container(container)
        counter -= 1
        logger.info(counter)
    except Exception as msg:
        logger.exception(msg)

def run_watcher():
    client = docker.from_env()
    while True:
        logger.info("Checking...")
        try:
            container_list = client.containers.list()
            threads = []
            for container in container_list:
                thread = threading.Thread(target=worker, args=(container,))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
        except Exception as msg:
            logger.exception(msg)
        logger.info("Checked.")
        time.sleep(1)

if __name__ == "__main__":
    run_watcher()