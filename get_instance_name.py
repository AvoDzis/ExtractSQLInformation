import argparse
import csv
import json
import subprocess


def get_private_ip(instance):
    ip_addresses = instance.get("ipAddresses", [])
    for address in ip_addresses:
        if address.get("type") == "PRIVATE":
            return address["ipAddress"]
    # Fall back to the first address if the instance has no private IP
    return ip_addresses[0]["ipAddress"] if ip_addresses else "N/A"


def get_instance_info(network_filter=None):
    instance_output = subprocess.check_output(
        ["gcloud", "sql", "instances", "list", "--format=json"]
    ).decode("utf-8")
    instances = json.loads(instance_output)
    if not instances:
        print("No instances found.")
        return []

    instance_data = []
    for instance in instances:
        instance_name = instance["name"]
        instance_status = instance["state"]
        private_network = instance["settings"]["ipConfiguration"].get("privateNetwork", "")
        network_name = private_network.split("/")[-1]

        # Check if the instance is in a running state and if it matches the network filter (if provided)
        if instance_status == "RUNNABLE" and (network_filter is None or network_name == network_filter):
            instance_data.append({
                "instance_name": instance_name,
                "private_ip": get_private_ip(instance),
                "network": network_name,
            })

    return instance_data


def create_csv(data, file_name):
    with open(file_name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"CSV file '{file_name}' has been created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List running Cloud SQL instances and their private IPs.")
    parser.add_argument("--network", help="only include instances on this VPC network (default: all)")
    parser.add_argument("--output", help="CSV file to write (default: instance_info_<network>.csv)")
    args = parser.parse_args()

    instance_info = get_instance_info(args.network)

    if instance_info:
        create_csv(instance_info, args.output or f"instance_info_{args.network or 'all'}.csv")
