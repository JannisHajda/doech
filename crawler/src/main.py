import dns.rdtypes.svcbbase
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

DOMAIN_LIST = "/root/git/doech/crawler/domains.csv"
START_AT = 0
NUM_DOMAINS = 250000
SLEEP_TIME = 5
NUM_PROCESSES = 16
CLICKHOUSE_BATCH_SIZE = 100

RUN_UUID = None
WORKER_ID = "node-0"


def init_clickhouse():
    client = get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )
    client.command("""
        CREATE TABLE IF NOT EXISTS dns_results (
            worker_id String,
            run_uuid String, 
            domain String,
            start DateTime,
            end DateTime,
            dns_a_results String,
            dns_aaaa_results String,
            dns_svcb_results String,
            dns_https_results String
        ) ENGINE = MergeTree()
        ORDER BY end;
    """)
    return client


def insert_batch(client, batch):
    rows = []
    for entry in batch:
        rows.append((
            WORKER_ID,
            entry.get("run_uuid"),
            entry.get("domain"),
            entry.get("start"),
            entry.get("end"),
            json.dumps(entry.get("dns_a", [])),
            json.dumps(entry.get("dns_aaaa", [])),
            json.dumps(entry.get("dns_svcb", [])),
            json.dumps(entry.get("dns_https", []))
        ))
    client.insert("dns_results", rows, column_names=[
        "worker_id", "run_uuid", "domain", "start", "end",
        "dns_a_results", "dns_aaaa_results", "dns_svcb_results", "dns_https_results"
    ])


def get_dns_results(domain: str, dns_type: str = "HTTPS"):
    url = "https://cloudflare-dns.com/dns-query"
    params = {"name": domain, "type": dns_type}
    headers = {"accept": "application/dns-json"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        results = []

        for answer in data.get("Answer", []):
            if dns_type in ("A", "AAAA"):
                ip = answer.get("data", "")
                if ip:
                    results.append({"ip": ip})

            elif dns_type in ("SVCB", "HTTPS"):
                presentation = answer.get("data", "")
                if not presentation.startswith("\\#"):
                    continue

                match = re.match(r'^\\# \d+\s+(.+)$', presentation)
                if not match:
                    continue

                hex_string = match.group(1).replace(" ", "")
                raw_bytes = unhexlify(hex_string)

                rdatatype = dns.rdatatype.SVCB if dns_type == "SVCB" else dns.rdatatype.HTTPS
                rdata = dns.rdata.from_wire(
                    dns.rdataclass.IN,
                    rdatatype,
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
                    parsed_params["target"] = rdata.target.to_text().rstrip(
                        ".")

                results.append(parsed_params)

        return results

    except Exception as e:
        return [{"error": str(e)}]


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
        result["dns_a"] = get_dns_results(domain, dns_type="A")
    except Exception as e:
        result["dns_a"] = [{"error": str(e)}]

    try:
        result["dns_aaaa"] = get_dns_results(domain, dns_type="AAAA")
    except Exception as e:
        result["dns_aaaa"] = [{"error": str(e)}]

    try:
        result["dns_svcb"] = get_dns_results(domain, dns_type="SVCB")
    except Exception as e:
        result["dns_svcb"] = [{"error": str(e)}]

    try:
        result["dns_https"] = get_dns_results(domain, dns_type="HTTPS")
    except Exception as e:
        result["dns_https"] = [{"error": str(e)}]

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
