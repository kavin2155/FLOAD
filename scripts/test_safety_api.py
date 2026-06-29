#!/usr/bin/env python3
import json
import os
from pathlib import Path
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> None:
    load_dotenv(Path(".env"))
    
    api_key = os.environ.get("SAFETY_DATA_API_KEY")
    if not api_key:
        print("Error: SAFETY_DATA_API_KEY not found in .env file.")
        return

    url = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00117"
    payloads = {
        "serviceKey": api_key,
        "returnType": "json",
        "pageNo": "1",
        "numOfRows": "5",
    }

    print(f"Requesting URL: {url} with parameters...")
    try:
        response = requests.get(url, params=payloads, verify=False, timeout=30)
        print(f"Response Status Code: {response.status_code}")
        
        try:
            data = response.json()
            print("\n--- API JSON Response ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print("Failed to decode JSON. Raw Response:")
            print(response.text[:2000])

    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    main()
