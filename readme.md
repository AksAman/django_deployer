### Django Deployer

This project automates the deployment of Django projects to a server using gunicorn, nginx and systemd.

### Installation
1. Python 3.6 or higher is required.
2. Clone this repository.
3. Create a virtual environment: `python -m venv venv` or `virtualenv venv`
4. Activate the virtual environment: `source venv/bin/activate` or `venv\Scripts\activate.bat`
4. Install the requirements: `pip install -r requirements.txt`
5. Run the deployer: `python deployer.py`

### Usage
```
Options:
  --project-name TEXT             Project name
  --sudo / --no-sudo              Use sudo
  --git-repo TEXT                 Git repo
  --git-branch TEXT               Git branch
  --domain-name TEXT              Domain
  --migrate / --no-migrate        Migrate
  --collectstatic / --no-collectstatic
                                  Collect static
  --help                          Show this message and exit.
```

### Example
```
./deploy.py --project-name="base_django_app" --sudo --git-repo="https://github.com/AksAman/django-base-app" --git-branch="master" --domain-name "example
.com" --no-migrate --no-collectstatic
```
