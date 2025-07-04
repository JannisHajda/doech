from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import time
import csv
from clickhouse_connect import get_client
import uuid
import json
from datetime import datetime
import multiprocessing
from tqdm import tqdm
from dotenv import load_dotenv
import os

load_dotenv()

WORKER_ID = os.getenv("WORKER_ID", "node-0")

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "default")
CLICKHOUSE_BATCH_SIZE = int(os.getenv("CLICKHOUSE_BATCH_SIZE", "100"))

DOMAIN_LIST = os.getenv("DOECH_DOMAIN_LIST")
GECKO_DRIVER_PATH = os.getenv("GECKO_DRIVER_PATH")
EXTENSION_PATH = os.getenv("EXTENSION_PATH")

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
SLEEP_TIME = int(os.getenv("SLEEP_TIME", "5"))
MAIN_FRAME_ONLY = os.getenv("MAIN_FRAME_ONLY", "true").lower() == "true"

START_AT = int(os.getenv("DOECH_START_AT", "0"))
NUM_DOMAINS = int(os.getenv("DOECH_NUM_DOMAINS", "250000"))
NUM_PROCESSES = int(os.getenv("DOECH_NUM_PROCESSES", "16"))


def init_clickhouse():
    client = get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )
    client.command("""
        CREATE TABLE IF NOT EXISTS doech_results (
            worker_id String,
            run_uuid String, 
            domain String,
            start DateTime,
            end DateTime,
            results String
        ) ENGINE = MergeTree()
        ORDER BY end;
    """)
    return client


def insert_batch(client, batch):
    rows = []
    for entry in batch:
        rows.append((
            entry.get("worker_id", WORKER_ID),
            entry.get("run_uuid"),
            entry.get("domain"),
            entry.get("start"),
            entry.get("end"),
            json.dumps(entry.get("results", []))
        ))
    client.insert("doech_results", rows, column_names=[
        "worker_id", "run_uuid", "domain", "start", "end",
        "results",
    ])


def get_doech_results(domain: str):
    """
    Uses Selenium to load a page and extracts the results generated using doech.
    If MAIN_FRAME_ONLY is True, filters out objects not related to the main frame.
    """
    url = f"https://{domain}"

    options = FirefoxOptions()

    # Enable DoH with Cloudflare
    options.set_preference("network.trr.mode", 2)
    options.set_preference(
        "network.trr.uri", "https://mozilla.cloudflare-dns.com/dns-query")
    options.set_preference("network.trr.bootstrapAddress", "1.1.1.1")

    if HEADLESS:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        # options.add_argument("--disable-dev-shm-usage")

    service = FirefoxService(executable_path=GECKO_DRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=options)

    # Install doech extension
    driver.install_addon(EXTENSION_PATH, temporary=True)

    try:
        driver.get(url)

        time.sleep(SLEEP_TIME)

        doech_results = driver.execute_async_script("""
            const callback = arguments[arguments.length - 1];

            const handleExport = (event) => {
                if (event?.data?.from === "doech" && event?.data?.to === "selenium" && event?.data?.action === "export") {
                    window.removeEventListener("message", handleExport);
                    callback(event.data.data);
                }
            }

            window.addEventListener("message", handleExport);

            window.postMessage({
                from: "selenium",
                to: "doech",
                action: "export",
            }, "*");
        """)

        if MAIN_FRAME_ONLY and isinstance(doech_results, list):
            # Filter: only keep entries where requestInfo.type == "main_frame"
            doech_results = [
                entry for entry in doech_results
                if entry.get("requestInfo", {}).get("type") == "main_frame"
            ]

        return doech_results
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return [{"error": str(e)}]
    finally:
        driver.quit()


def process_domain(args):
    worker_id, run_uuid, domain = args
    result = {
        "worker_id": worker_id,
        "run_uuid": run_uuid,
        "domain": domain,
        "start": datetime.now(),
        "end": None
    }

    try:
        result["results"] = get_doech_results(domain)
    except Exception as e:
        result["results"] = [{"error": str(e)}]

    result["end"] = datetime.now()
    return result


if __name__ == "__main__":
    print(f"Started worker {WORKER_ID}...")
    RUN_UUID = str(uuid.uuid4())
    print(f"Starting run with UUID: {RUN_UUID}...")

    with open(DOMAIN_LIST, "r") as f:
        reader = csv.reader(f)
        domains = [row[0] for row in reader if row]

        if START_AT > 0:
            domains = domains[START_AT:]
        if NUM_DOMAINS > 0:
            domains = domains[:NUM_DOMAINS]

    client = init_clickhouse()
    buffer = []

    args = [(WORKER_ID, RUN_UUID, domain) for domain in domains]
    NUM_PROCESSES = min(NUM_PROCESSES, len(domains))

    with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
        for result in tqdm(pool.imap(process_domain, args), total=len(domains), desc="Processing Domains"):
            buffer.append(result)
            if len(buffer) >= CLICKHOUSE_BATCH_SIZE:
                insert_batch(client, buffer)
                buffer = []

        if buffer:
            insert_batch(client, buffer)

    print(f"Run {RUN_UUID} finished.")
