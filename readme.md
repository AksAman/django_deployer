### Django Deployer

This project automates the deployment of Django projects to a server using gunicorn, nginx and systemd.

### Installation
1. Python 3.6 or higher is required.
2. Clone this repository.
3. Create a virtual environment: `python -m venv venv` or `virtualenv venv`
4. Activate the virtual environment: `source venv/bin/activate` or `venv\Scripts\activate.bat`
4. Install the requirements: `pip install -r requirements.txt`
5. Run the deployer: `python deployer.py`

### Assumptions
1. The project is a Django project.
2. The project is hosted on a git repository.
3. Thr project has following structure on the server:
```
project_name # just a parent folder to hold all the files which should not be included in the git repo
  |-- project_name # project folder, here the project will be cloned without any subdirectory as the git repo name
  |-- venv
```


### Usage
```
Usage: deploy.py [OPTIONS]

Options:
  --root-path TEXT                Path to store project files
  --project-name TEXT             Project name
  --sudo / --no-sudo              Use sudo
  --git-repo TEXT                 Git repo
  --git-branch TEXT               Git branch
  --domain-name TEXT              Domain
  --collectstatic / --no-collectstatic
                                  Collect static
  --help                          Show this message and exit.                         Show this message and exit.
```

```
Usage: setup_db.py [OPTIONS]

Options:
  --root-path TEXT                Path to store project files
  --project-name TEXT             Project name
  --db-name TEXT                  Database name
  --db-user TEXT                  Database user
  --db-password TEXT              Database password
  --db-host TEXT                  Database host
  --db-port TEXT                  Database port
  --execute-sql / --no-execute-sql
                                  Execute SQL
  --migrate / --no-migrate        Migrate
  --help                          Show this message and exit.
```


### Example
```
./deploy.py --project-name="base_django_app" --sudo --git-repo="https://github.com/AksAman/django-base-app" --git-branch="master" --domain-name "example
.com" --no-migrate --no-collectstatic
```
