# ExtractSQLInformation

Two small Python scripts that inventory **Cloud SQL for PostgreSQL** instances on a GCP VPC network and write the results to CSV:

1. which instances are running on a given network, with their private IPs
2. for every database on those instances: the database size and the size of each table

I wrote them in 2023 alongside a Cloud SQL backup/restore project for a client, to get an inventory of databases and their sizes. Client names, network names and credentials have been removed from this copy.

## How it works

- `get_instance_name.py` calls `gcloud sql instances list`, keeps instances in the `RUNNABLE` state (optionally only those on one VPC network), and writes `instance_name, private_ip, network` to CSV.
- `list_databases_tables_sizes.py` reuses that list, calls `gcloud sql databases list` for each instance, then connects to every database over its private IP with `psycopg2` and runs `pg_database_size` and `pg_total_relation_size` per table. A database it cannot connect to is reported on stderr and skipped.

Cloud SQL private IPs are only reachable from inside the VPC, so the second script has to run on a VM (for example a small bastion) in the same network. With several networks (say dev and prod) you run it once from a VM in each.

## Requirements

- Python 3.8+
- `gcloud` CLI, authenticated (`gcloud auth login` or a VM service account) with at least the Cloud SQL Viewer role on the project
- For `list_databases_tables_sizes.py`: network access to the instances' private IPs, and `pip install -r requirements.txt`

`get_instance_name.py` uses only the standard library.

## Usage

```bash
# 1. Instances on one network (omit --network for all instances in the project)
python get_instance_name.py --network my-vpc
# -> instance_info_my-vpc.csv

# 2. From a VM inside that network: databases, database sizes and table sizes
cp .env.example .env           # fill in PGUSER / PGPASSWORD
set -a; . ./.env; set +a
python list_databases_tables_sizes.py --network my-vpc
# -> database_info_my-vpc.csv
```

Both scripts accept `--output <file>` to choose the CSV name.

### Credentials

The scripts never take a password as an argument or store one in the CSV. `psycopg2` (libpq) reads it from the standard places:

- `PGPASSWORD` (and `PGUSER`, default `postgres`; `PGPORT`, default `5432`), for one login on all instances, or
- a `~/.pgpass` file (`host:port:database:user:password`, `chmod 600`), when instances have different passwords.

### Example output

`database_info_my-vpc.csv` (values made up):

```csv
instance_name,private_ip,network,database,tables_with_size,database_size
orders-db,<private-ip>,my-vpc,postgres,"{""public.orders"": ""512 MB"", ""public.customers"": ""48 MB""}",571 MB
orders-db,<private-ip>,my-vpc,reporting,"{""public.daily_totals"": ""16 kB""}",7 MB
```

## Limits

- PostgreSQL only; MySQL and SQL Server instances are listed by step 1 but step 2 can't read them.
- Queries run one database at a time, which is fine for tens of instances, slow for hundreds.
- Only tables are counted (no views or materialized views), and sizes are the human-readable `pg_size_pretty` strings, not bytes.
- Connections use libpq's default SSL mode (`prefer`). Instances that require client certificates need extra connection settings that the scripts don't have.
- No automated tests. The original scripts ran against test instances in 2023. This cleaned-up version (CLI flags, credentials from the environment, CSV via the standard library) was checked against a stubbed `gcloud` and `psycopg2`, not against live Cloud SQL.
