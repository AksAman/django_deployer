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
  --env-file TEXT                 Path to .env file (Loads Database Variables from this file)
  --execute-sql / --no-execute-sql
                                  Execute SQL
  --migrate / --no-migrate        Migrate
  --help                          Show this message and exit
```


### Example
```
./deploy.py --project-name="base_django_app" --sudo --git-repo="https://github.com/AksAman/django-base-app" --git-branch="master" --domain-name "example
.com" --no-migrate --no-collectstatic
```

```bash
python deploy.py \
  --root-path="root-path" \
  --project-name="project-name" \
  --sudo \
  --git-repo="repo-url" \
  --sub-dir="app" \
  --domain-name "example.com" \
  --no-collectstatic
```


### Setting up Gunicorn and Nginx
There are some permission issues due to which the script is unable to write the conf files to gunicorn and nginx directories.

Instead it creates template files in the root-path specified as 
```bash
gunicorn.service.template
gunicorn.socket.template
nginx/templates/app.nginx
```

Run the following to copy the files to proper directories
```bash
sudo cp ~/gunicorn.service.template /etc/systemd/system/gunicorn.service
sudo cp ~/gunicorn.socket.template /etc/systemd/system/gunicorn.socket
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
sudo systemctl status gunicorn.socket

sudo cp ~/nginx/templates/app.nginx /etc/nginx/sites-available/app.nginx
sudo ln -s /etc/nginx/sites-available/app.nginx /etc/nginx/sites-enabled
sudo nginx -t

server_name=$(sudo cat /etc/nginx/sites-available/app.nginx | grep server_name | awk '{print $2}' | tr -d ';')
echo $server_name
```


### Certbot
Setup dns record for the server_name

```bash
server_name=$(sudo cat /etc/nginx/sites-available/app.nginx | grep server_name | awk '{print $2}' | tr -d ';')
echo $server_name

sudo ufw delete allow 8000
sudo ufw allow 'Nginx Full'
sudo apt install certbot python3-certbot-nginx -y
sudo nano /etc/nginx/sites-available/app.nginx
# add the domain

sudo certbot --nginx -d $server_name
sudo certbot renew --dry-run
```