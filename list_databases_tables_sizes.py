import argparse
import csv
import json
import os
import subprocess
import sys

import psycopg2

from get_instance_name import get_instance_info

# The password is never passed in code: libpq reads it from PGPASSWORD or ~/.pgpass
DB_USER = os.environ.get("PGUSER", "postgres")
DB_PORT = int(os.environ.get("PGPORT", "5432"))


# Function to get databases for an instance
def get_databases(instance_name):
    command = ["gcloud", "sql", "databases", "list", "--instance", instance_name, "--format=json"]
    output = subprocess.check_output(command).decode("utf-8")
    databases = json.loads(output)
    return databases


# Function to get the size of each table and of the whole database
def get_database_and_table_sizes(database_name, host):
    conn = psycopg2.connect(dbname=database_name, user=DB_USER, host=host, port=DB_PORT, connect_timeout=10)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT table_schema || '.' || table_name, "
                "pg_size_pretty(pg_total_relation_size(format('%I.%I', table_schema, table_name)::regclass)) "
                "FROM information_schema.tables "
                "WHERE table_schema NOT LIKE 'pg_%' AND table_schema != 'information_schema' "
                "AND table_type = 'BASE TABLE';"
            )
            table_dict = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT pg_size_pretty(pg_database_size(%s));", (database_name,))
            database_size = cursor.fetchone()[0]
    finally:
        conn.close()

    return table_dict, database_size


# Function to add database and table information to each instance row
def add_database_and_table_info(instance_info):
    updated_instance_info = []

    for info in instance_info:
        instance_name = info["instance_name"]
        databases = get_databases(instance_name)

        for db in databases:
            db_name = db["name"]
            try:
                tables_with_size, database_size = get_database_and_table_sizes(db_name, info["private_ip"])
            except psycopg2.Error as e:
                print(f"Skipping {instance_name}/{db_name}: {e}".strip(), file=sys.stderr)
                continue

            updated_info = info.copy()
            updated_info["database"] = db_name
            updated_info["tables_with_size"] = json.dumps(tables_with_size)
            updated_info["database_size"] = database_size

            updated_instance_info.append(updated_info)

    return updated_instance_info


def create_csv(data, file_name):
    with open(file_name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"CSV file '{file_name}' has been created with database and table information.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List databases, table sizes and database sizes of Cloud SQL for PostgreSQL instances.")
    parser.add_argument("--network", help="only include instances on this VPC network (default: all)")
    parser.add_argument("--output", help="CSV file to write (default: database_info_<network>.csv)")
    args = parser.parse_args()

    instance_info = get_instance_info(args.network)

    # Add database and table information to each instance
    instance_info = add_database_and_table_info(instance_info)

    if instance_info:
        create_csv(instance_info, args.output or f"database_info_{args.network or 'all'}.csv")
