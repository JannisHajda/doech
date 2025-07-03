import dns.rdtypes.svcbbase
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
import time
import requests
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.name
import re
from binascii import unhexlify
import csv
import json
import multiprocessing
from tqdm import tqdm
from clickhouse_connect import get_client
from datetime import datetime
import uuid

CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = "default"

GECKO_DRIVER_PATH = "/usr/local/bin/geckodriver"
EXTENSION_PATH = "/root/git/doech/extension/src"
DOMAIN_LIST = "/root/git/doech/crawler/domains.csv"
START_AT = 0
NUM_DOMAINS = 1
SLEEP_TIME = 5
NUM_PROCESSES = 4
CLICKHOUSE_BATCH_SIZE = 25
HEADLESS = True
MAIN_FRAME_ONLY = True

RUN_UUID = None
WORKER_ID = "node-0"


def init_clickhouse():
    client = get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
                        username=CLICKHOUSE_USER, password=CLICKHOUSE_PASSWORD)
    client.command("""
        CREATE TABLE IF NOT EXISTS crawling_results (
            worker_id String,
            run_uuid String, 
            domain String,
            dns_svcb_results String,
            dns_https_results String,
            doech_results String,
            start DateTime,
            end DateTime
        ) ENGINE = MergeTree()
        ORDER BY domain;
    """)
    return client


def insert_batch(client, batch):
    rows = []
    for entry in batch:
        rows.append((
            WORKER_ID,
            entry.get("run_uuid"),
            entry.get("domain"),
            json.dumps(entry.get("dns_svcb", {})),
            json.dumps(entry.get("dns_https", {})),
            json.dumps(entry.get("doech", {})),
            entry.get("start"),
            entry.get("end")
        ))
    client.insert("crawling_results", rows, column_names=[
        "worker_id", "run_uuid", "domain", "dns_svcb_results", "dns_https_results", "doech_results", "start", "end"])


def get_dns_results(domain: str, dns_type: str = "HTTPS"):
    """
    Queries Cloudflare DoH for HTTPS RR and parses binary config if present.

    Returns:
        {
            "domain": str,
            "data": dict (SVCB/HTTPS params as key-value pairs),
        }
    """
    url = "https://cloudflare-dns.com/dns-query"
    params = {
        "name": domain,
        "type": dns_type,
    }
    headers = {
        "accept": "application/dns-json"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        for answer in data.get("Answer", []):
            presentation = answer.get("data", "")
            if not presentation.startswith("\\#"):
                continue

            match = re.match(r'^\\# \d+\s+(.+)$', presentation)
            if not match:
                continue

            hex_string = match.group(1).replace(" ", "")
            raw_bytes = unhexlify(hex_string)

            if dns_type == "SVCB":
                rdata = dns.rdata.from_wire(
                    dns.rdataclass.IN,
                    dns.rdatatype.SVCB,
                    raw_bytes,
                    0,
                    len(raw_bytes),
                    origin=dns.name.from_text(domain)
                )
            elif dns_type == "HTTPS":
                rdata = dns.rdata.from_wire(
                    dns.rdataclass.IN,
                    dns.rdatatype.HTTPS,
                    raw_bytes,
                    0,
                    len(raw_bytes),
                    origin=dns.name.from_text(domain)
                )

            parsed_params = {}
            if rdata.priority == 0:
                parsed_params["alias_target"] = rdata.target.to_text().rstrip(
                    ".")
                parsed_params["priority"] = 0
            else:
                for param in rdata.params:
                    key = dns.rdtypes.svcbbase.ParamKey(param).name
                    value = rdata.params.get(param).to_text()
                    parsed_params[key] = value.strip('"')

                parsed_params["priority"] = rdata.priority
                parsed_params["target"] = rdata.target.to_text().rstrip(".")
                parsed_params["params"] = parsed_params

            return {
                "domain": domain,
                "data": parsed_params,
            }

        return {
            "domain": domain,
            "data": {},
        }

    except Exception as e:
        return {
            "domain": domain,
            "data": {},
            "error": str(e)
        }


def get_doech_results(url: str):
    """
    Uses Selenium to load a page and extracts the results generated using doech.
    If MAIN_FRAME_ONLY is True, filters out objects not related to the main frame.
    """
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
        options.add_argument("--disable-dev-shm-usage")

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
    finally:
        driver.quit()


def process_domain(args):
    """
    Processes a single domain by fetching DNS results and doech results.
    """
    domain, run_uuid = args

    result = {
        "run_uuid": run_uuid,
        "domain": domain,
        "start": datetime.now(),
        "end": None
    }

    try:
        dns_svcb_results = get_dns_results(domain, dns_type="SVCB")
        result["dns_svcb"] = dns_svcb_results
    except Exception as e:
        result["dns_svcb"] = {"error": str(e)}

    try:
        dns_https_results = get_dns_results(domain, dns_type="HTTPS")
        result["dns_https"] = dns_https_results
    except Exception as e:
        result["dns_https"] = {"error": str(e)}

    try:
        doech_results = get_doech_results(f"https://{domain}")
        result["doech"] = doech_results
    except Exception as e:
        result["doech"] = {"error": str(e)}

    result["end"] = datetime.now()

    return result


if __name__ == "__main__":
    print(f"Started worker {WORKER_ID}...")
    RUN_UUID = str(uuid.uuid4())
    print(f"Starting run with UUID: {RUN_UUID}...")

    with open(DOMAIN_LIST, "r") as f:
        reader = csv.reader(f, delimiter=',')
        domains = [row[1] for row in reader if row]

        if START_AT > 0:
            domains = domains[START_AT:]
        if NUM_DOMAINS > 0:
            domains = domains[:NUM_DOMAINS]

    client = init_clickhouse()
    buffer = []

    args = [(domain, RUN_UUID) for domain in domains]

    with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
        for result in tqdm(pool.imap(process_domain, args), total=len(domains), desc="Processing Domains"):
            buffer.append(result)
            if len(buffer) >= CLICKHOUSE_BATCH_SIZE:
                insert_batch(client, buffer)
                buffer = []

        if buffer:
            insert_batch(client, buffer)

    print(f"Run {RUN_UUID} finished.")
