import dns.rdtypes.svcbbase
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
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


DOMAIN_LIST = "/Users/jannis/Git/doech/crawler/domains.csv"
EXTENSION_PATH = "/Users/jannis/Git/doech/extension/src"
SLEEP_TIME = 5
NUM_PROCESSES = 4
CLICKHOUSE_BATCH_SIZE = 100
OUTPUT_FILE = "results.json"
HEADLESS = True
MAIN_FRAME_ONLY = True


def init_clickhouse():
    client = get_client(host="localhost", port=8123,
                        username="default", password="default")
    client.command("""
        CREATE TABLE IF NOT EXISTS crawling_results (
            domain String,
            dns_result String,
            doech_result String,
            timestamp DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY domain;
    """)
    return client


def insert_batch(client, batch):
    rows = []
    for entry in batch:
        rows.append((
            entry.get("domain"),
            json.dumps(entry.get("dns", {})),
            json.dumps(entry.get("doech", {})),
            datetime.utcnow()
        ))
    client.insert("crawling_results", rows, column_names=[
                  "domain", "dns_result", "doech_result", "timestamp"])


def get_dns_results(domain: str):
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
        "type": "HTTPS"
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

            rdata = dns.rdata.from_wire(
                dns.rdataclass.IN,
                dns.rdatatype.HTTPS,
                raw_bytes,
                0,
                len(raw_bytes),
                origin=dns.name.from_text(domain)
            )

            parsed_params = {}
            for param in rdata.params:
                key = dns.rdtypes.svcbbase.ParamKey(param).name
                value = rdata.params.get(param).to_text()
                parsed_params[key] = value.strip('"')

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
    options = Options()

    # Enable DoH with Cloudflare
    options.set_preference("network.trr.mode", 2)
    options.set_preference(
        "network.trr.uri", "https://mozilla.cloudflare-dns.com/dns-query")
    options.set_preference("network.trr.bootstrapAddress", "1.1.1.1")
    if HEADLESS:
        options.add_argument("--headless")

    driver = webdriver.Firefox(options=options)

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


def process_domain(domain: str):
    """
    Processes a single domain by fetching DNS results and doech results.
    """

    result = {
        "domain": domain
    }

    try:
        dns_results = get_dns_results(domain)
        result["dns"] = dns_results
    except Exception as e:
        result["dns"] = {"error": str(e)}

    try:
        doech_results = get_doech_results(f"https://{domain}")
        result["doech"] = doech_results
    except Exception as e:
        result["doech"] = {"error": str(e)}

    return result


if __name__ == "__main__":
    with open(DOMAIN_LIST, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header row: "domain"
        domains = [row[0] for row in reader if row]  # take the domain string

    client = init_clickhouse()
    buffer = []

    with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
        for result in tqdm(pool.imap(process_domain, domains), total=len(domains), desc="Processing Domains"):
            buffer.append(result)
            if len(buffer) >= CLICKHOUSE_BATCH_SIZE:
                insert_batch(client, buffer)
                buffer = []

        if buffer:
            insert_batch(client, buffer)
