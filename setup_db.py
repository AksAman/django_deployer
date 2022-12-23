#!/usr/bin/python3
try:
    import click
except ImportError:
    print("Please install click with pip3 install click")
    exit(1)

import getpass
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

VENV_ACTIVE = False


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
artifacts_dir = Path().home().joinpath(".deployment_artifacts")


class DeploymentException(Exception):
    pass


class InstallationException(Exception):
    pass


def run_command(command: List[str], use_sudo: bool = True, raise_on_error: bool = True):
    if use_sudo:
        command = ["sudo"] + command
    process = subprocess.run(command)
    if process.returncode != 0 and raise_on_error:
        raise DeploymentException(f"Failed to run command: {command}")


def get_public_ip() -> Optional[str]:
    # curl https://ipv4.icanhazip.com/
    try:
        ip = subprocess.check_output(["curl", "https://ipv4.icanhazip.com/"])
        ip = ip.decode("utf-8").strip()
        return ip
    except Exception as e:
        return None


def shell_source(script):
    """Sometime you want to emulate the action of "source" in bash,
    settings some environment variables. Here is a way to do it."""
    pipe = subprocess.Popen(". %s; env" % script, stdout=subprocess.PIPE, shell=True)
    output = pipe.communicate()[0].decode("utf-8")
    env = dict((line.split("=", 1) for line in output.splitlines()))
    os.environ.update(env)


def raise_for_deployment():
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except DeploymentException as e:
                logger.error(e)
                exit(1)

        return wrapper

    return decorator


@raise_for_deployment()
def activate_venv(venv_path):
    global VENV_ACTIVE
    if not VENV_ACTIVE:
        logger.info("Activating virtualenv")
        shell_source(f"{venv_path}/bin/activate")
        environ = os.environ.copy()
        if "VIRTUAL_ENV" not in environ:
            raise DeploymentException("Failed to activate virtualenv")
    VENV_ACTIVE = True
    if not VENV_ACTIVE:
        logger.info("Virtualenv activated")


def restart_services():
    service_manager = "systemctl"
    # daemon_reload
    run_command([service_manager, "daemon-reload"], use_sudo=True)
    logger.info("Daemon reloaded")

    # restart/start gunicorn
    run_command([service_manager, "restart", "gunicorn"], use_sudo=True)
    logger.info("Gunicorn restarted")

    # restart/start nginx
    run_command([service_manager, "restart", "nginx"], use_sudo=True)
    logger.info("Nginx restarted")


@raise_for_deployment()
def create_postgres_resources(db_name, db_user, db_password, db_host, db_port, execute_sql: bool = True):
    line = ""
    line += f"CREATE DATABASE {db_name};\n"
    line += f"CREATE USER {db_user} WITH PASSWORD '{db_password}';\n"
    line += f"ALTER ROLE {db_user} SET client_encoding TO 'utf8';\n"
    line += f"ALTER ROLE {db_user} SET default_transaction_isolation TO 'read committed';\n"
    line += f"ALTER ROLE {db_user} SET timezone TO 'Asia/Kolkata';\n"
    line += f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};\n"
    line += f"ALTER ROLE {db_user} SUPERUSER;"

    if execute_sql:
        sql_script_path = artifacts_dir.joinpath("create_db.sql")
        if sql_script_path.exists():
            sql_script_path.unlink()
        with open(sql_script_path, "w") as f:
            f.write(line)

        sql_script_path.chmod(0o777)
        sql_script_path_str = str(sql_script_path.absolute())

        run_command(["sudo", "su", "postgres", "-c", f"psql -f {sql_script_path_str}"], use_sudo=False)
        logger.info("Postgres resources created")
    else:
        logger.info("SQL Execution disabled")
        logger.info("Run the following SQL commands to create postgres resources")
        print("-" * 50)
        print(line)
        print("-" * 50)


def pull_latest_changes(project_dir: Path):
    current_dir = os.getcwd()
    logger.info("Pulling latest changes")
    os.chdir(project_dir)
    run_command(["git", "pull"], use_sudo=False)
    os.chdir(current_dir)
    return


def migrate_db(django_project_path: Path):
    logger.info("Migrating database")
    django_project_path_str = str(django_project_path.absolute())
    run_command(["python", f"{django_project_path_str}/manage.py", "migrate"], use_sudo=False)
    logger.info("Database migrated")


@click.command()
@click.option("--root-path", prompt="Root Path", help="Path to store project files")
@click.option("--project-name", prompt="Project name", help="Project name")
@click.option("--db-name", prompt="Database name", help="Database name")
@click.option("--db-user", prompt="Database user", help="Database user")
@click.option("--db-password", prompt="Database password", help="Database password")
@click.option("--db-host", prompt="Database host", help="Database host")
@click.option("--db-port", prompt="Database port", help="Database port")
@click.option("--execute-sql/--no-execute-sql", prompt="Execute SQL", help="Execute SQL", default=True)
@click.option("--migrate/--no-migrate", prompt="Migrate", help="Migrate", default=True)
def main(
    root_path: str,
    project_name: str,
    db_name: str,
    db_user: str,
    db_password: str,
    db_host: str,
    db_port: str,
    execute_sql: bool,
    migrate: bool,
):
    global PROJECT_NAME
    PROJECT_NAME = project_name
    home_dir = Path(root_path)
    project_dir = home_dir.joinpath(project_name).joinpath(project_name)

    create_postgres_resources(db_name, db_user, db_password, db_host, db_port, execute_sql)
    if migrate:
        if "VIRTUAL_ENV" not in os.environ:
            raise DeploymentException("Virtualenv not activated, please activate it first")
        migrate_db(project_dir)


if __name__ == "__main__":
    main()
