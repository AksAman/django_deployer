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
PROJECT_NAME = None
gunicorn_service_path = f"/etc/systemd/system/gunicorn.service"
gunicorn_socket_path = f"/etc/systemd/system/gunicorn.socket"
nginx_root_path = "/etc/nginx/sites-available"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
artifacts_dir = Path().home().joinpath(".deployment_artifacts")
stage_file = artifacts_dir.joinpath("stage.json")
previous_stages = {}
if not artifacts_dir.exists():
    artifacts_dir.mkdir(parents=True, exist_ok=True)


def load_artifacts(root_path):
    global previous_stages
    global artifacts_dir
    global stage_file

    artifacts_dir = root_path.joinpath(".deployment_artifacts")
    logger.info(f"Artifacts directory: {artifacts_dir.absolute()}")
    stage_file = artifacts_dir.joinpath("stage.json")
    if not stage_file.exists():
        stage_file.touch()
        stage_file.write_text("{}")

    try:
        with open(stage_file, "r") as f:
            previous_stages = json.load(f)
    except Exception:
        pass


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


def update_stage(stage_name: str):
    def update_stage_file(stage_name: str):
        global previous_stages
        global PROJECT_NAME
        project_stages: dict = previous_stages.setdefault(PROJECT_NAME, {})
        project_stages[stage_name] = True
        with open(stage_file, "w") as f:
            json.dump(previous_stages, f, indent=4)

    def decorator(func):
        def wrapper(*args, **kwargs):
            project_stages: dict = previous_stages.setdefault(PROJECT_NAME, {})
            if project_stages.get(stage_name):
                logger.info(f"Stage {stage_name} already completed")
                return
            func(*args, **kwargs)
            update_stage_file(stage_name)

        return wrapper

    return decorator


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


# def get_service_manager():
#     which_service = subprocess.run(["which", "service"])
#     which_systemctl = subprocess.run(["which", "systemctl"])
#     if which_systemctl.returncode == 0:
#         return "systemctl"
#     if which_service.returncode == 0:
#         return "service"

#     raise DeploymentException("Failed to find service or systemctl")


def restart_services():
    service_manager = "systemctl"
    # daemon_reload
    run_command([service_manager, "daemon-reload"], use_sudo=True)

    # restart/start gunicorn
    run_command([service_manager, "restart", "gunicorn"], use_sudo=True)
    logger.info("Gunicorn restarted")

    # restart/start nginx
    run_command([service_manager, "restart", "nginx"], use_sudo=True)
    logger.info("Nginx restarted")


@raise_for_deployment()
@update_stage("update_system")
def update_system(use_sudo: bool = True):
    logger.info("Updating system")
    run_command(["sudo", "apt", "update", "-y"], use_sudo=use_sudo)
    logger.info("System updated")


@raise_for_deployment()
@update_stage("install_apt_packages")
def install_apt_packages(use_sudo: bool = True):
    logger.info("Installing apt packages")
    package_list = [
        "python3-pip",
        "python3-dev",
        "libpq-dev",
        "nginx",
        "curl",
        "postgresql",
        "postgresql-contrib",
        "zsh",
        "git",
        "systemd",
        "python3-venv",
    ]
    # run apt install without any user input
    run_command(["sudo", "apt", "install", "-y"] + package_list, use_sudo=use_sudo)
    logger.info(f"{len(package_list)} Apt packages installed")


@raise_for_deployment()
@update_stage("install_python_packages")
def install_python_packages():
    packages = [
        "pyperclip",
    ]

    logger.info("Installing python packages")
    run_command(["pip3", "install"] + packages, use_sudo=False)


@raise_for_deployment()
@update_stage("create_postgres_resources")
def create_postgres_resources(db_name, db_user, db_password, db_host, db_port):
    # try:
    #     import psycopg2
    # except ImportError:
    #     logger.info("Installing psycopg2")
    #     run_command(["pip3", "install", "psycopg2"])

    # logger.info("Creating postgres resources")
    # # create database
    # connection = psycopg2.connect(
    #     host=db_host,
    #     port=db_port,
    #     user=db_user,
    #     password=db_password,
    # )
    line = ""
    line += f"CREATE DATABASE {db_name};\n"
    line += f"CREATE USER {db_user} WITH PASSWORD '{db_password}';\n"
    line += f"ALTER ROLE {db_user} SET client_encoding TO 'utf8';\n"
    line += f"ALTER ROLE {db_user} SET default_transaction_isolation TO 'read committed';\n"
    line += f"ALTER ROLE {db_user} SET timezone TO 'Asia/Kolkata';\n"
    line += f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};\n"
    line += f"ALTER ROLE {db_user} SUPERUSER;"

    sql_script_path = artifacts_dir.joinpath("create_db.sql")
    if sql_script_path.exists():
        sql_script_path.unlink()
    with open(sql_script_path, "w") as f:
        f.write(line)

    sql_script_path.chmod(0o777)
    sql_script_path_str = str(sql_script_path.absolute())

    run_command(["sudo", "su", "postgres", "-c", f"psql -f {sql_script_path_str}"], use_sudo=False)
    logger.info("Postgres resources created")


@raise_for_deployment()
@update_stage("create_project_dir")
def create_project_dir(project_dir: Path):
    logger.info("Creating project dir")
    project_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Project dir created")


@raise_for_deployment()
@update_stage("clone_git_repo")
def clone_git_repo(repo_url: str, branch: str = "master", destination_dir: Path = Path(".")):
    """
    Clones the git repo in the destination directory
    :param repo_url: The url of the git repo
    :param branch: The branch to clone
    :param destination_dir: The directory to clone the repo in
    :return: The path to the cloned repo
    """
    logger.info(f"Cloning git repo to {destination_dir}")
    if destination_dir.exists() and len(os.listdir(destination_dir)) > 0:
        logger.info("Git repo already cloned")
        return
    destination_dir_str = str(destination_dir.absolute())
    run_command(["git", "clone", "-b", branch, repo_url, destination_dir_str], use_sudo=False)
    logger.info("Git repo cloned")


def pull_latest_changes(project_dir: Path):
    current_dir = os.getcwd()
    logger.info("Pulling latest changes")
    os.chdir(project_dir)
    run_command(["git", "pull"], use_sudo=False)
    os.chdir(current_dir)
    return


@raise_for_deployment()
@update_stage("install_create_activate_virtualenv")
def install_create_activate_virtualenv(project_dir: Path, venv_path: Path):
    """
    Installs virtualenv and creates a virtualenv in the project directory
    Returns the path to the virtualenv
    """
    # upgrade pip
    logger.info("Upgrading pip")
    run_command(["pip3", "install", "--upgrade", "pip"], use_sudo=False)
    logger.info("Pip upgraded")

    # install virtualenv
    logger.info("Installing virtualenv")
    run_command(["pip3", "install", "virtualenv"], use_sudo=False)
    logger.info("Virtualenv installed")

    venv_path_str = str(venv_path.absolute())

    # create virtualenv
    logger.info("Creating virtualenv")
    # run_command(["virtualenv", "-p", "python3", venv_path_str], use_sudo=False)
    run_command(["python3", "-m", "venv", venv_path_str], use_sudo=False)

    logger.info("Virtualenv created")

    # activate virtualenv
    activate_venv(venv_path)


@raise_for_deployment()
@update_stage("install_project_dependencies")
def install_project_dependencies(venv_path: str, project_dir: Path):
    activate_venv(venv_path)
    logger.info("Installing project dependencies")
    project_dir_str = str(project_dir.absolute())
    requirements_file = project_dir.joinpath("requirements.txt")
    if not requirements_file.exists():
        requirements_file = project_dir.joinpath("chill.requirements.txt")
    if not requirements_file.exists():
        logger.warn("No requirements.txt file found")
        return

    requirements_file_str = str(requirements_file.absolute())
    run_command(["pip3", "install", "-r", requirements_file_str], use_sudo=False)
    logger.info("Project dependencies installed")


@update_stage("migrate_db")
def migrate_db(venv_path: str, django_project_path: Path):
    activate_venv(venv_path)
    logger.info("Migrating database")
    django_project_path_str = str(django_project_path.absolute())
    run_command(["python3", f"{django_project_path_str}/manage.py", "migrate"], use_sudo=False)
    logger.info("Database migrated")


@raise_for_deployment()
@update_stage("collect_static")
def collect_static(venv_path: str, django_project_path: Path):
    activate_venv(venv_path)
    logger.info("Collecting static")
    django_project_path_str = str(django_project_path.absolute())
    run_command(["python3", f"{django_project_path_str}/manage.py", "collectstatic", "--no-input"], use_sudo=False)
    logger.info("Static collected")


@raise_for_deployment()
@update_stage("install_gunicorn")
def install_gunicorn(venv_path: str):
    activate_venv(venv_path)
    logger.info("Setting up gunicorn")
    # install gunicorn
    run_command(["pip3", "install", "gunicorn"], use_sudo=False)
    logger.info("Gunicorn installed")


def get_gunicorn_path(venv_path: str):
    activate_venv(venv_path)
    gunicorn_path = subprocess.check_output(["which", "gunicorn"]).decode("utf-8").strip()
    logger.info(f"Gunicorn path: {gunicorn_path}")
    return gunicorn_path


@raise_for_deployment()
@update_stage("write_gunicorn_config_files")
def write_gunicorn_config_files(gunicorn_path: str, django_project_path: Path):
    def write_gunicorn_socket():
        try:
            src = Path(".").joinpath("templates/gunicorn.socket")
            with open(src, "r") as f:
                content = f.read()

            with open(gunicorn_socket_path, "w") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error creating gunicorn.socket file: {e}")
            raise DeploymentException("Error creating gunicorn.socket file")

    def write_gunicorn_service():
        try:
            src = Path(".").joinpath("templates/gunicorn.service")
            with open(src, "r") as f:
                content = f.read()

            # vars = {{USER}}, {{GROUP}}, {{APP_NAME}}, {{PROJECT_PATH}}, {{GUNICORN_PATH}}
            current_user = getpass.getuser()
            content = content.replace("{{USER}}", current_user)
            content = content.replace("{{GROUP}}", "www-data")
            content = content.replace("{{APP_NAME}}", django_project_path.name)
            content = content.replace("{{PROJECT_PATH}}", django_project_path_str)
            content = content.replace("{{GUNICORN_PATH}}", gunicorn_path)

            # TODO: add workers as a parameter

            with open(gunicorn_service_path, "w") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error creating gunicorn.service file: {e}")
            raise DeploymentException("Error creating gunicorn.service file")

    logger.info("Writing gunicorn config files")
    django_project_path_str = str(django_project_path.absolute())

    logger.info(f"Creating gunicorn.socket file")
    write_gunicorn_socket()
    write_gunicorn_service()


@raise_for_deployment()
@update_stage("setup_nginx")
def setup_nginx(django_project_path: Path, domain_name: Optional[str]):
    if not domain_name:
        domain_name = get_public_ip()
        if not domain_name:
            domain_name = "localhost"
            logger.warning(f"Could not get public IP, using {domain_name} instead")
    logger.info("Setting up nginx")

    # create nginx config file
    project_name = django_project_path.name
    django_project_path_str = str(django_project_path.absolute())
    try:
        src = Path(".").joinpath("templates/nginx.conf")
        with open(src, "r") as f:
            content = f.read()

        # vars = {{DOMAIN}}, {{PROJECT_PATH}}
        content = content.replace("{{DOMAIN_NAME}}", domain_name)
        content = content.replace("{{PROJECT_PATH}}", django_project_path_str)

        nginx_config_path = f"{nginx_root_path}/{project_name}"
        with open(nginx_config_path, "w") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Error creating nginx config file: {e}")
        raise DeploymentException("Error creating nginx config file")

    # enable nginx config file
    run_command(["ln", "-s", nginx_config_path, f"/etc/nginx/sites-enabled"], use_sudo=True, raise_on_error=False)

    # remove default nginx config file
    # run_command(["rm", f"/etc/nginx/sites-enabled/default"], use_sudo=True)


@click.command()
@click.option("--root-path", prompt="Root Path", help="Path to store project files")
@click.option("--project-name", prompt="Project name", help="Project name")
@click.option("--sudo/--no-sudo", prompt="Use sudo", help="Use sudo", default=True)
# @click.option("--db-name", prompt="Database name", help="Database name")
# @click.option("--db-user", prompt="Database user", help="Database user")
# @click.option("--db-password", prompt="Database password", help="Database password")
# @click.option("--db-host", prompt="Database host", help="Database host")
# @click.option("--db-port", prompt="Database port", help="Database port")
@click.option("--git-repo", prompt="Git repo", help="Git repo")
@click.option("--git-branch", prompt="Git branch", help="Git branch", default="master")
@click.option("--domain-name", prompt="Domain", help="Domain", default=None)
@click.option("--migrate/--no-migrate", prompt="Migrate", help="Migrate", default=True)
@click.option("--collectstatic/--no-collectstatic", prompt="Collect static", help="Collect static", default=True)
def main(
    root_path: str,
    project_name: str,
    sudo: bool,
    # db_name: str,
    # db_user: str,
    # db_password: str,
    # db_host: str,
    # db_port: str,
    git_repo: str,
    git_branch: str,
    domain_name: Optional[str] = None,
    migrate: bool = True,
    collectstatic: bool = True,
):
    # print(f"{sudo=} {db_name=} {db_user=} {db_password=} {db_host=} {db_port=} {git_repo=}")
    # print all cli options
    global PROJECT_NAME
    PROJECT_NAME = project_name
    home_dir = Path(root_path)
    load_artifacts(root_path=home_dir)

    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    update_system(use_sudo=sudo)
    install_apt_packages(use_sudo=sudo)
    install_python_packages()
    # create_postgres_resources(db_name, db_user, db_password, db_host, db_port)
    # get home dir
    project_dir = home_dir.joinpath(project_name).joinpath(project_name)
    logger.info(f"Project dir: {project_dir}")

    create_project_dir(project_dir=project_dir)
    clone_git_repo(repo_url=git_repo, branch=git_branch, destination_dir=project_dir)
    pull_latest_changes(project_dir=project_dir)

    venv_path = project_dir.parent.joinpath("venv")
    venv_path_str = str(venv_path.absolute())

    install_create_activate_virtualenv(project_dir=project_dir, venv_path=venv_path)
    install_project_dependencies(venv_path=venv_path_str, project_dir=project_dir)

    if migrate:
        migrate_db(venv_path=venv_path_str, django_project_path=project_dir)

    if collectstatic:
        collect_static(venv_path=venv_path_str, django_project_path=project_dir)

    install_gunicorn(venv_path=venv_path_str)
    gunicorn_path = get_gunicorn_path(venv_path=venv_path_str)
    write_gunicorn_config_files(gunicorn_path=gunicorn_path, django_project_path=project_dir)

    # setup nginx
    setup_nginx(django_project_path=project_dir, domain_name=domain_name)

    restart_services()


if __name__ == "__main__":
    main()
