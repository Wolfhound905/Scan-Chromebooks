import csv
import os
import io
import json
from time import sleep
from dotenv import get_key
from requests import get, put
from termcolor import colored

print(
    colored(
        "Welcome to the 2022 add-o-matic ID Assigner | copyright pending\n", "white"
    )
)  # lol

# info: cyan
# error: red
# success: green

if os.path.exists("./updated-inventory.csv"):

    continue_prompt = input(
        colored(
            "Warning there is an existing updated-inventory.csv, continuing the program will delete this file. Are you sure you want to continue? (y/n): ",
            "red",
        )
    )
    match continue_prompt.lower():
        case "y":
            os.remove("./updated-inventory.csv")
        case "n":
            print("\nok")
            exit()

inventory_url = "https://fleet-api.goguardian.com/v1/chromeos-devices/export"
session_string = get_key(".env", "SESSION_STRING")
user_id = get_key(".env", "USER_ID")
if session_string and user_id:
    print(colored("\n\nFetching inventory from GoGuardian...", "cyan"))
    headers = {"cookie": f"sessionString={session_string};userID={user_id};"}
    resp = get(inventory_url, headers=headers)
    if (
        resp.headers.get("Content-Disposition")
        and resp.headers.get("Content-Disposition")
        == 'attachment; filename="inventory-export.csv"'
    ):  # Check that the request gave back csv
        with open("inventory.csv", "wb") as f:
            f.write(resp.content)
            print(colored("\nInventory was successfully downloaded...", "green"))
    else:
        print(colored("\n\nCould not fetch inventory from GoGuardian!", "red"))
        exit()


header = ["Serial Number", "Asset ID", "OU", "Location", "Student (email)", "Loaner"]
data = []
scanned_in_session = []

inventory_rows = []
with open("inventory.csv", "r") as file:
    inventory_csvreader = csv.reader(file)
    inventory_header = next(inventory_csvreader)
    for row in inventory_csvreader:
        inventory_rows.append(row)
    print(colored(f"\nLoaded {len(inventory_rows)} rows from inventory.csv", "green"))


def lookup_asset_id(asset_id: str):
    asset_id_header_index = inventory_header.index("Asset ID")
    for entry in inventory_rows:
        if entry[asset_id_header_index] == asset_id:
            return entry


def lookup_serial_number(serial_number: str):
    serial_number_header_index = inventory_header.index("Serial Number")
    for entry in inventory_rows:
        if entry[serial_number_header_index] == serial_number:
            return entry


def upload_go_guardian(headers, data):
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    writer.writerows(data)
    new_data = json.dumps({"csv": output.getvalue()})
    req_headers = {
        "cookie": f"sessionString={session_string};userID={user_id};",
        "content-type": "application/json",
    }
    print(colored("\nUplaoding to GoGuardian...", "cyan"))
    resp = put(
        "https://fleet-api.goguardian.com/v1/chromeos-devices/import",
        new_data,
        headers=req_headers,
    )
    if resp.status_code != 200:
        print(colored("\n\nPlease upload manually!", "red"))
        print(colored(f"\nError: ({resp.status_code}) {resp.text}", "red"))
    else:
        print(colored("\nUploaded new data.", "green"))
    print(colored("\nValidating upload...", "cyan"))
    sleep(2)
    check = get(
        f"https://fleet-api.goguardian.com/v1/chromeos-devices/matches?query={data[0][1]}",
        headers=req_headers,
    )
    if check.status_code != 200:
        print(colored("\n\nSomething went wrong, please upload manually!", "red"))

    else:
        results = check.json()
        if annotatedIds := results.get("gAnnotatedAssetIds"):
            if len(annotatedIds) == 1:
                print(
                    colored(
                        f"\n\nThe data was uploaded successfully!",
                        "green",
                    )
                )
            else:
                print(
                    colored("\n\nSomething went wrong, please upload manually!", "red")
                )


try:
    while True:
        inventory_email_header_index = inventory_header.index("Student (email)")
        inventory_update_date_header_index = inventory_header.index("Updated At")
        inventory_asset_id = inventory_header.index("Asset ID")
        inventory_serial_header_index = inventory_header.index("Serial Number")
        print(
            colored("-----------------------------------------------------\n", "white")
        )
        qr_url = input(colored(f"Scan a Chromebook QR (on back): ", "yellow"))
        serial_id = qr_url.split("/")[-1]
        if serial_id in scanned_in_session:
            print(
                colored(
                    "\nThis Chromebook has already been scanned in this session.", "red"
                )
            )
            continue
        if not lookup_serial_number(serial_id):
            print(colored("\nThis Chromebook is not in the inventory.", "red"))
            continue
        else:
            entry = lookup_serial_number(serial_id)
            if entry[inventory_asset_id] != "":
                print(
                    colored(
                        "\nThis Chromebook is already assigned to Asset ID: "
                        + entry[inventory_asset_id],
                        "red",
                    )
                )
                continue
        asset_id = input(colored(f"Scan a Chromebook Barcode: ", "magenta"))
        if lookup_asset_id(asset_id):
            print(colored("\nThis Asset ID is already assigned.", "red"))
            continue

        data.append(
            [
                serial_id,
                asset_id,
                "/",
                "",
                "None",
                "",
                "",
            ]
        )
        scanned_in_session.append(serial_id)
        print(
            colored(
                f"{asset_id} has been assigned to Chromebook: {serial_id}\n", "green"
            )
        )

except KeyboardInterrupt:
    print(colored("\n\nGenerating new csv for upload!", "cyan"))
    with open("updated-inventory.csv", "w", encoding="UTF8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)

    if session_string and user_id and len(data) > 0:
        upload = input(
            colored("\nWould you like to upload this to GoGuardian? (y/n): ", "yellow")
        )
        match upload.lower():
            case "y":
                upload_go_guardian(header, data)
            case "n":
                print("\nok")
                exit()
            case _:
                print("Invalid response, closing.")


except Exception as e:
    print(f"An error orrcured: {e}")
    with open("updated-inventory.csv", "w", encoding="UTF8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)

    if session_string and user_id and len(data) > 0:
        upload = input(
            colored("\nWould you like to upload this to GoGuardian? (y/n): ", "yellow")
        )
        match upload.lower():
            case "y":
                upload_go_guardian(header, data)
            case "n":
                print("\nok")
                exit()
            case _:
                print("Invalid response, closing.")
