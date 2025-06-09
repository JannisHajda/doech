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


TRANCO_LIST = "/Users/jannis/Git/doech/crawler/top-1m.csv"
EXTENSION_PATH = "/Users/jannis/Git/doech/extension/src"
SLEEP_TIME = 5
NUM_PROCESSES = 4
OUTPUT_FILE = "results.json"


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
    """

    options = Options()
    options.headless = True

    # Enable DoH with Cloudflare
    options.set_preference("network.trr.mode", 2)
    options.set_preference(
        "network.trr.uri", "https://mozilla.cloudflare-dns.com/dns-query")
    options.set_preference("network.trr.bootstrapAddress", "1.1.1.1")

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

        return doech_results
    finally:
        driver.quit()


def process_domain(domain: str):
    """
    Processes a single domain by fetching DNS results and doech results.
    """
    try:
        dns_results = get_dns_results(domain)
        doech_results = get_doech_results(domain)

        return {
            "domain": domain,
            "dns": dns_results,
            "doech": doech_results
        }

    except Exception as e:
        return {
            "domain": domain,
            "error": str(e)
        }


if __name__ == "__main__":
    with open(TRANCO_LIST, "r") as f:
        reader = csv.reader(f, delimiter=',')
        domains = [row[1] for row in reader if len(row) > 1]

    with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
        results = list(tqdm(pool.imap(process_domain, domains),
                       total=len(domains), desc="Processing Domains"))

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
