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
import logging

load_dotenv(override=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "doech_test.log")

numeric_level = getattr(logging, LOG_LEVEL, None)
if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log level: {LOG_LEVEL}")

logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(process)d - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
    try:
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
        logger.info(
            "ClickHouse table 'doech_results' checked/created successfully.")
    except Exception as e:
        logger.exception(f"Error initializing ClickHouse: {e}")
        raise
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
    try:
        client.insert("doech_results", rows, column_names=[
            "worker_id", "run_uuid", "domain", "start", "end",
            "results",
        ])
        logger.debug(f"Inserted batch of {len(rows)} rows into ClickHouse.")
    except Exception as e:
        logger.exception(f"Error inserting batch into ClickHouse: {e}")


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

    driver = None

    try:
        service = FirefoxService(executable_path=GECKO_DRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)
        logger.debug(f"Successfully launched Firefox for {domain}")

        driver.install_addon(EXTENSION_PATH, temporary=True)
        logger.debug(f"Installed extension for {domain}")

        driver.get(url)
        logger.debug(f"Navigated to {url}")

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
        logger.debug(f"Received doech results for {domain}")

        if MAIN_FRAME_ONLY and isinstance(doech_results, list):
            filtered_results = [
                entry for entry in doech_results
                if entry.get("requestInfo", {}).get("type") == "main_frame"
            ]
            logger.debug(
                f"Filtered doech results for {domain}. Original: {len(doech_results)}, Filtered: {len(filtered_results)}")
            doech_results = filtered_results

        return doech_results
    except Exception as e:
        logger.exception(f"Error processing {url}: {e}")
        return [{"error": str(e), "domain": domain, "timestamp": datetime.now().isoformat()}]
    finally:
        if driver:
            try:
                driver.quit()
                logger.debug(f"Driver quit successfully for {domain}")
            except Exception as e:
                logger.error(f"Error quitting driver for {domain}: {e}")


def process_domain(args):
    worker_id, run_uuid, domain = args
    result = {
        "worker_id": worker_id,
        "run_uuid": run_uuid,
        "domain": domain,
        "start": datetime.now(),
        "end": None
    }

    result["results"] = get_doech_results(domain)

    result["end"] = datetime.now()
    return result


if __name__ == "__main__":
    logger.info(f"Started worker {WORKER_ID}...")
    logger.info("Using following configuration:")
    logger.info(f" HEADLESS: {HEADLESS}")
    logger.info(f" SLEEP_TIME: {SLEEP_TIME}")
    logger.info(f" MAIN_FRAME_ONLY: {MAIN_FRAME_ONLY}")
    logger.info(f" START_AT: {START_AT}")
    logger.info(f" NUM_DOMAINS: {NUM_DOMAINS}")
    logger.info(f" NUM_PROCESSES: {NUM_PROCESSES}")
    logger.info(f" DOMAIN_LIST: {DOMAIN_LIST}")
    logger.info(f" GECKO_DRIVER_PATH: {GECKO_DRIVER_PATH}")
    logger.info(f" EXTENSION_PATH: {EXTENSION_PATH}")
    logger.info(f" CLICKHOUSE_HOST: {CLICKHOUSE_HOST}")
    logger.info(f" CLICKHOUSE_PORT: {CLICKHOUSE_PORT}")
    logger.info(f" CLICKHOUSE_USER: {CLICKHOUSE_USER}")
    logger.info(f" CLICKHOUSE_BATCH_SIZE: {CLICKHOUSE_BATCH_SIZE}")

    RUN_UUID = str(uuid.uuid4())
    logger.info(f"Starting run with UUID: {RUN_UUID}...")

    try:
        if not DOMAIN_LIST or not os.path.exists(DOMAIN_LIST):
            logger.critical(
                f"DOMAIN_LIST not found or not specified: {DOMAIN_LIST}. Exiting.")
            exit(1)

        with open(DOMAIN_LIST, "r") as f:
            reader = csv.reader(f)
            domains = [row[0] for row in reader if row]

            initial_domains_count = len(domains)
            logger.info(
                f"Loaded {initial_domains_count} domains from {DOMAIN_LIST}.")

            if START_AT > 0:
                domains = domains[START_AT:]
                logger.info(
                    f"Adjusted domain list to start at index {START_AT}.")
            if NUM_DOMAINS > 0:
                domains = domains[:NUM_DOMAINS]
                logger.info(f"Limited domain list to {NUM_DOMAINS} domains.")

            logger.info(
                f"Total domains to process after filtering: {len(domains)}")
            if not domains:
                logger.warning(
                    "No domains left to process after applying START_AT and NUM_DOMAINS filters. Exiting.")
                exit(0)

        client = init_clickhouse()
        buffer = []

        args = [(WORKER_ID, RUN_UUID, domain) for domain in domains]
        NUM_PROCESSES = min(NUM_PROCESSES, len(domains))
        logger.info(f"Using {NUM_PROCESSES} worker processes.")

        with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
            for result in tqdm(pool.imap(process_domain, args), total=len(domains), desc="Processing Domains"):
                buffer.append(result)
                if len(buffer) >= CLICKHOUSE_BATCH_SIZE:
                    insert_batch(client, buffer)
                    buffer = []

            if buffer:
                insert_batch(client, buffer)

        logger.info(
            f"Run {RUN_UUID} finished. All domains processed and results saved.")

    except FileNotFoundError:
        logger.critical(
            f"Error: The DOMAIN_LIST file '{DOMAIN_LIST}' was not found. Please check your .env configuration.")
        exit(1)
    except Exception as main_e:
        logger.exception(
            f"An unhandled error occurred in the main execution block: {main_e}")
        exit(1)
