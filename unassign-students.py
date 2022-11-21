import csv
import os
from datetime import datetime
import io
import json
from types import NoneType
from dotenv import get_key
import asyncio
import aiohttp
from termcolor import colored


print(
    "Welcome to the 2022 add-o-matic Chromebook Un-Assigner | copyright pending\n"
)  # lol


async def graceful_exit(session: aiohttp.ClientSession):
    await session.close()
    exit()


async def login(session: aiohttp.ClientSession) -> NoneType:
    login_data = {
        "email": get_key(".env", "EMAIL"),
        "password": get_key(".env", "PASSWORD"),
    }
    resp = await session.post(
        "https://gandalf.goguardian.com/v1/login", json=login_data
    )
    data = await resp.json()
    if data.get("success") is False:
        print(colored("Login failed:", "red"), data.get("message"))
        await graceful_exit(session)


async def load_inventory() -> NoneType:
    inventory_rows = []
    with open("inventory.csv", "r") as file:
        inventory_csvreader = csv.reader(file)
        inventory_header = next(inventory_csvreader)
        for row in inventory_csvreader:
            inventory_rows.append(row)
        print("Loaded the inventory\n")

    return inventory_rows, inventory_header


async def fetch_inventory(session: aiohttp.ClientSession) -> NoneType:
    if get_key(".env", "FETCH_INVENTORY") == "false":
        print("Using inventory.csv")
        return
    async with session.get(
        "https://fleet-api.goguardian.com/v1/chromeos-devices/export"
    ) as resp:
        if resp.status != 200:
            raise Exception("Failed to fetch inventory", resp.status)
        with open("inventory.csv", "wb") as f:
            f.write(await resp.read())
        print("Fetched inventory")


async def upload_go_guardian(session: aiohttp.ClientSession, headers, data) -> NoneType:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    writer.writerows(data)
    new_data = json.dumps({"csv": output.getvalue()})
    req_headers = {"content-type": "application/json"}
    print("\nUploading new chromebook changes...")
    async with session.put(
        "https://fleet-api.goguardian.com/v1/chromeos-devices/import",
        data=new_data,
        headers=req_headers,
    ) as resp:
        if resp.status != 200:
            print("\nSomething went wrong, please upload manually.")
        else:
            print("\nDone!")


def lookup_asset_or_serial(
    identifier: str, inventory_rows: list, inventory_header: list
) -> list:
    identifier = identifier.split("/")[-1].strip()
    asset_id_header_index = inventory_header.index("Asset ID")
    serial_header_index = inventory_header.index("Serial Number")
    for row in inventory_rows:
        if (
            row[asset_id_header_index] == identifier
            or row[serial_header_index] == identifier
        ):
            return row


async def unassign_with_txt(session: aiohttp.ClientSession) -> NoneType:
    try:
        with open("unassign.txt", "r") as file:
            serial_n_asset_numbers = file.readlines()
    except FileNotFoundError:
        print(
            colored("Error: ", "red"),
            "unassign.txt not found. The file should contain a list of serial numbers or asset ids to unassign. One per line.",
        )
        await graceful_exit(session)
    inventory_rows, inventory_header = await load_inventory()
    inventory_serial_header_index = inventory_header.index("Serial Number")
    inventory_asset_id_header_index = inventory_header.index("Asset ID")
    rows_to_unassign = []

    for serial_n_asset_number in serial_n_asset_numbers:
        row = lookup_asset_or_serial(
            serial_n_asset_number,
            serial_n_asset_number,
            inventory_rows,
            inventory_header,
        )
        if row:
            rows_to_unassign.append(
                [
                    row[inventory_serial_header_index],
                    row[inventory_asset_id_header_index],
                    row[inventory_header.index("OU")],
                    row[inventory_header.index("Location")],
                    "None",
                    "",
                    "",
                ]
            )
        else:
            print(
                colored("Warning: ", "yellow"),
                f"skipping {serial_n_asset_number}, not found in inventory",
            )

    header = [
        "Serial Number",
        "Asset ID",
        "OU",
        "Location",
        "Student (email)",
        "Loaner",
    ]
    await upload_go_guardian(session, header, rows_to_unassign)


async def unassign_with_scanner(session: aiohttp.ClientSession) -> NoneType:
    inventory_rows, inventory_header = await load_inventory()
    inventory_serial_header_index = inventory_header.index("Serial Number")
    inventory_asset_id_header_index = inventory_header.index("Asset ID")
    rows_to_unassign = []

    try:
        while True:
            serial_n_asset_number = input(
                "Scan"
                + colored(" asset id ", "green")
                + "or"
                + colored(" serial number", "green")
                + ": "
            )
            if serial_n_asset_number == "":
                print(colored("Tip: ", "yellow"), "press Ctrl+C to exit")
                continue
            row = lookup_asset_or_serial(
                serial_n_asset_number,
                inventory_rows,
                inventory_header,
            )
            if row:
                rows_to_unassign.append(
                    [
                        row[inventory_serial_header_index],
                        row[inventory_asset_id_header_index],
                        row[inventory_header.index("OU")],
                        row[inventory_header.index("Location")],
                        "None",
                        "",
                        "",
                    ]
                )
            else:
                print(
                    colored("Warning: ", "yellow"),
                    f"skipping {serial_n_asset_number}, not found in inventory",
                )
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(colored("A critical error has occured:", "red"), e)
        pass

    header = [
        "Serial Number",
        "Asset ID",
        "OU",
        "Location",
        "Student (email)",
        "Loaner",
    ]
    if len(rows_to_unassign) > 0:
        print(rows_to_unassign)
        await upload_go_guardian(session, header, rows_to_unassign)
    else:
        print("\nBye!\n")


async def main():
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(cookie_jar=cookie_jar)
    await login(session)

    try:
        await fetch_inventory(session)
    except Exception as e:
        print(e)
        await graceful_exit(session)

    mode = None
    while mode not in ["scan", "txt"]:
        mode = input(
            "Would you like to scan or use a txt? (scan/txt): "
            + colored("[scan] ", "green"),
        )
        if mode == "":
            mode = "scan"
    if mode == "scan":
        await unassign_with_scanner(session)
    elif mode == "txt":
        await unassign_with_txt(session)

    await graceful_exit(session)


asyncio.run(main())
