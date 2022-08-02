#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys

import requests
import urllib3

if(sys.version_info[0] < 3 or sys.version_info[1] < 6):
    print("This script requires python version 3.6 and above. Please make sure to run with the proper version. Aborting...")
    sys.exit(1)

req_session = requests.Session()

if os.getenv('TRUST_ANY_CERT'):
    req_session.verify = False
    urllib3.disable_warnings()


def is_pkg_ignored(name: str, docker_image: str, ignore_packages: dict):
    return (name in ignore_packages and
            ((not ignore_packages[name].get("docker_images")) or
             [x for x in ignore_packages[name].get("docker_images") if x in docker_image]))


def check_pwsh_license(docker_image: str, licenses: dict, ignore_packages: dict, known_licenses: dict):
    try:
        subprocess.check_call(
            ["docker", "run", "--rm", docker_image, "which", "pwsh"], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as err:
        if err.returncode != 1:
            raise
        print(
            f"Skipping Powershell license verification for [{docker_image}] as this is not a powershell image."
        )

        return
    pwsh_modules_out = subprocess.check_output(
        ["docker", "run", "--rm", docker_image, "pwsh", "-c",
         "Get-InstalledModule | Select-Object -Property Name,Author,LicenseUri | ConvertTo-Json"], universal_newlines=True
    )
    if not pwsh_modules_out.strip():
        print("No installed pwsh modules found.")
        return
    pwsh_modules = json.loads(pwsh_modules_out)
    if not isinstance(pwsh_modules, list):
        pwsh_modules = [pwsh_modules]
    for m in pwsh_modules:
        name = m.get("Name")
        if name in known_licenses:
            lic = known_licenses[name]
            print(f'{name}: has a known license. license uri: {lic["url"]} approved as license: {lic["license"]}')
            continue
        license_uri = m.get('LicenseUri')
        if not license_uri:
            print(f'{name} has no license URI (default MIT applies)')
            continue
        print(f'{name}: verifying license URI: {license_uri}..')
        if is_pkg_ignored(name, docker_image, ignore_packages):
            print(f'Ignoring package: {name}')
            continue
        found_license = False
        for lic in licenses:
            if license_uri == lic.get('url') or (lic.get('additional_urls') and license_uri in lic.get('additional_urls')):
                print(
                    f'{name}: license uri: {license_uri} approved as license: {lic["name"]}')
                found_license = True
                break
        if found_license:
            continue
        # we couldn't find an approved license try getting the license and check if the first line matches the regex
        res = req_session.get(license_uri)
        res.raise_for_status()
        lic_line = res.text.splitlines()[0]
        for lic in licenses:
            if re.search(lic["regex"], lic_line):
                print(f'{name}: found license: [{lic["name"]}] matches license first line: "{lic_line}"')
                found_license = True
                break
        if not found_license:
            msg = f'{name} (author: {m.get("Author")}): no approved license found for uri: {license_uri}'
            print(f"FAILURE: {msg}")
            raise Exception(msg)


def check_python_license(docker_image: str, licenses: dict, ignore_packages: dict, known_licenses: dict):
    try:
        subprocess.check_call(
            ["docker", "run", "--rm", docker_image, "which", "python"], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as err:
        if err.returncode != 1:
            raise
        print(
            f"Skipping python license verification for [{docker_image}] as this is not a python image."
        )

        return
    pip_list_json = subprocess.check_output(
        ["docker", "run", "--rm", docker_image, "pip", "list", "--format", "json"])
    pip_list = json.loads(pip_list_json)
    for pkg in pip_list:
        name = pkg["name"]
        if is_pkg_ignored(name, docker_image, ignore_packages):
            print(f"Ignoring package: {name}")
            continue
        print(f"Checking license for package: {name} ...")
        classifiers = []
        found_licenses = []
        if name in known_licenses:
            classifiers = [known_licenses[name]['license']]
        else:
            try:
                res = req_session.get(f"https://pypi.org/pypi/{name}/json")
                res.raise_for_status()
                pip_info = res.json()
                classifiers = pip_info["info"].get("classifiers")
            except Exception as ex:
                print(f"Failed getting info from pypi (will try pip): {str(ex)}")
        for classifier in classifiers:
            # check that we have license and not just the OSI Approved string
            if (
                classifier.startswith("License ::")
                and classifier != "License :: OSI Approved"
            ):
                print(f"{name}: found license classifier: {classifier}")
                found_licenses.append(classifier)
        if not found_licenses:  # try getting via pip show
            docker_cmd_arr = ["docker", "run", "--rm",
                              docker_image, "pip", "show", name]
            pip_show = subprocess.check_output(
                docker_cmd_arr, universal_newlines=True)
            homepage = ''
            for line in pip_show.splitlines():
                if line.startswith("Home-page:"):
                    homepage = line.split(' ')[1].strip()
                if line.startswith("License:"):
                    if 'UNKNOWN' in line:
                        print(
                            f"Got UNKNOWN license from pip show, trying to query package GitHub homepage {homepage} to get license details."
                        )

                        owner_and_repo = homepage.split('https://github.com/')[1]
                        repo_license = req_session.get(
                            f"https://api.github.com/repos/{owner_and_repo}/license",
                            headers={
                                "Accept": "application/vnd.github.v3+json"
                            },
                            verify=True,
                        ).json()

                        license_name = repo_license.get('license', {}).get('name', 'NOT_FOUND_IN_GITHUB')
                        print(f"{name}: found license from GitHub API: {license_name}")
                        found_licenses.append(license_name)
                    else:
                        print(f"{name}: found license from pip show: {line}")
                        found_licenses.append(line)
        for found_lic in found_licenses:
            found = False
            for lic in licenses:
                if re.search(lic["regex"], found_lic):
                    print(f'{name}: found license: {found_lic} matches license: {lic["name"]}')
                    found = True
                    break
            if not found:
                msg = f"{name}: no approved license found for license: {found_lic}"
                print(f"FAILURE: {msg}")
                raise Exception(msg)


def main():
    print(f"Python version: {sys.version}")
    parser = argparse.ArgumentParser(description='Verify licenses used in a docker image',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "docker_image", help="The docker image with tag version to use. For example: demisto/python3:1.5.0.27")
    args = parser.parse_args()
    with open(f'{sys.path[0]}/approved_licenses.json') as f:
        licenses = json.load(f)["licenses"]
    with open(f"{sys.path[0]}/packages_license_check_exclude.json") as f:
        ignore_packages = json.load(f)["packages"]
    with open(f"{sys.path[0]}/known_licenses.json") as f:
        known_licenses = json.load(f)["packages"]
    print("================= Checking Python packages =================")
    check_python_license(args.docker_image, licenses,
                         ignore_packages, known_licenses)
    print("================= Checking PowerShell packages =================")
    check_pwsh_license(args.docker_image, licenses,
                       ignore_packages, known_licenses)
    print(
        f"SUCCESS: completed checking all licenses for docker image: {args.docker_image}"
    )


if __name__ == "__main__":
    main()
