import csv
import os
from datetime import datetime
import io
import json
from dotenv import get_key
from requests import get, put

print(
    "Welcome to the 2022 add-o-matic Chromebook Un-Assigner | copyright pending\n"
)  # lol

if os.path.exists("./updated-inventory.csv"):
    continue_prompt = input(
        "Warning there is an existing updated-inventory.csv, continuing the program will delete this file. Are you sure you want to continue? (y/n): "
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
    print("\n\nFetching inventory from GoGuardian...")
    headers = {"cookie": f"sessionString={session_string};userID={user_id};"}
    resp = get(inventory_url, headers=headers)
    if (
        resp.headers.get("Content-Disposition")
        and resp.headers.get("Content-Disposition")
        == 'attachment; filename="inventory-export.csv"'
    ):  # Check that the request gave back csv
        with open("inventory.csv", "wb") as f:
            f.write(resp.content)
        print("\nInventory was successfully downloaded...")


header = ["Serial Number", "Asset ID", "OU", "Location", "Student (email)", "Loaner"]
data = []
scanned_in_session = []

inventory_rows = []
with open("inventory.csv", "r") as file:
    inventory_csvreader = csv.reader(file)
    inventory_header = next(inventory_csvreader)
    for row in inventory_csvreader:
        inventory_rows.append(row)
    print("Loaded the inventory\n")


def lookup_asset_id(asset_id: str):
    asset_id_header_index = inventory_header.index("Asset ID")
    for entry in inventory_rows:
        if entry[asset_id_header_index] == asset_id:
            return entry

def lookup_email(email: str):
    email_entries = []
    email_header_index = inventory_header.index("Student (email)")
    for entry in inventory_rows:
        if entry[email_header_index] == email:
            email_entries.append(entry)

    return email_entries


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
    print("\nUploading new chromebook assignees...")
    resp = put(
        "https://fleet-api.goguardian.com/v1/chromeos-devices/import",
        new_data,
        headers=req_headers,
    )
    if resp.status_code != 200:
        print("\nSomething went wrong, please upload manually.")
    else:
        print("\nDone!")


try:
    while True:
        inventory_email_header_index = inventory_header.index("Student (email)")
        inventory_update_date_header_index = inventory_header.index("Updated At")
        inventory_serial_header_index = inventory_header.index("Serial Number")
        asset_id = input(f"\nScan a Chromebook: ")
        if inventory_entry := lookup_asset_id(asset_id):
            if existing := [scan for scan in scanned_in_session if scan[0] == asset_id]:
                print(f"\nYou already scanned this chromebook for: {existing[0][1]}")
            else:
                data.append(
                    [
                        inventory_entry[inventory_serial_header_index],
                        asset_id,
                        "/",
                        "",
                        "None",
                        "",
                        "",
                    ]
                )
                scanned_in_session.append([asset_id])
                print(
                    f"Unassigned {inventory_entry[inventory_email_header_index]} from {inventory_entry[inventory_serial_header_index]}"
                )
        else:
            print("\nThat id is not in the inventory.")

except KeyboardInterrupt:
    print("\n\nGenerating new csv for upload!")
    with open("updated-inventory.csv", "w", encoding="UTF8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)

    if session_string and user_id:
        upload = input("\nWould you like to upload this to GoGuardian? (y/n): ")
        match upload.lower():
            case "y":
                upload_go_guardian(header, data)
            case "n":
                print("\nok")
                exit()
            case _:
                print("Invalid response, closing.")


except Exception as e:
    print(f"An error orrcured", e)
    with open("updated-inventory.csv", "w", encoding="UTF8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)

    if session_string and user_id:
        upload = input("\nWould you like to upload this to GoGuardian? (y/n): ")
        match upload.lower():
            case "y":
                upload_go_guardian(header, data)
            case "n":
                print("\nok")
                exit()
            case _:
                print("Invalid response, closing.")
