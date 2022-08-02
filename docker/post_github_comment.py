#!/usr/bin/env python

import argparse
import requests
import subprocess
import os
import re
import time


def get_docker_image_size(docker_image):
    """Get the size of the image form docker hub

    Arguments:
        docker_image {string} -- the full name of hthe image
    """
    size = "failed querying size"
    for i in (1, 2, 3):
        try:
            name, tag = docker_image.split(':')
            res = requests.get(
                f'https://hub.docker.com/v2/repositories/{name}/tags/{tag}/'
            )

            res.raise_for_status()
            size_bytes = res.json()['images'][0]['size']
            size = '{0:.2f} MB'.format(float(size_bytes)/1024/1024)
        except Exception as ex:
            print(f"[{i}] failed getting image size for image: {docker_image}. Err: {ex}")
            if i != 3:
                print("Sleeping 5 seconds and trying again...")
                time.sleep(5)
    return size


def main():
    desc = """Post a message to github about the created image. Relies on environment variables:
GITHUB_KEY: api key of user to use for posting
CIRCLE_PULL_REQUEST: pull request url to use to get the pull id. Such as: https://github.com/demisto/dockerfiles/pull/9
if CIRCLE_PULL_REQUEST will try to get issue id from last commit comment
    """
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("docker_image", help="The docker image with tag version to use. For example: devdemisto/python3:1.5.0.27")
    args = parser.parse_args()
    if not os.environ.get('GITHUB_KEY'):
        print("No github key set. Will not post a message!")
        return
    post_url = ""
    if os.environ.get('CIRCLE_PULL_REQUEST'):
        # change: https://github.com/demisto/dockerfiles/pull/9
        # to: https://api.github.com/repos/demisto/dockerfiles/issues/9/comments
        post_url = os.environ['CIRCLE_PULL_REQUEST'].replace('github.com', 'api.github.com/repos').replace('pull', 'issues') + "/comments"
    else:
        # try to get from comment
        last_comment = subprocess.check_output(["git", "log", "-1", "--pretty=%B"])
        m = re.search(r"#(\d+)", last_comment, re.MULTILINE)
        if not m:
            print(
                f"No issue id found in last commit comment. Ignoring: \n------\n{last_comment}\n-------"
            )

            return
        issue_id = m[1]
        print(f"Issue id found from last commit comment: {issue_id}")
        post_url = f"https://api.github.com/repos/demisto/dockerfiles/issues/{issue_id}/comments"

    inspect_format = '''
- Image ID: `{{ .Id }}`
- Created: `{{ .Created }}`
- Arch: `{{ .Os }}`/`{{ .Architecture }}`
{{ if .Config.Entrypoint }}- Entrypoint: `{{ json .Config.Entrypoint }}`
{{ end }}{{ if .Config.Cmd }}- Command: `{{ json .Config.Cmd }}`
{{ end }}- Environment:{{ range .Config.Env }}{{ "\\n" }}  - `{{ . }}`{{ end }}
- Labels:{{ range $key, $value := .ContainerConfig.Labels }}{{ "\\n" }}  - `{{ $key }}:{{ $value }}`{{ end }}
'''
    docker_info = subprocess.check_output(["docker", "inspect", "-f", inspect_format, args.docker_image])
    base_name = args.docker_image.split(':')[0]
    mode = "Production" if base_name.startswith('demisto/') else "Dev"
    message = (
        (
            (
                (
                    (
                        (
                            (
                                (
                                    f"# Docker Image Ready - {mode}\n\n"
                                    + f"Docker automatic build at CircleCI has deployed your docker image: {args.docker_image}\n"
                                )
                                + f"It is available now on docker hub at: https://hub.docker.com/r/{base_name}/tags\n"
                            )
                            + "Get started by pulling the image:\n"
                        )
                        + "```\n"
                    )
                    + f"docker pull {args.docker_image}\n"
                )
                + "```\n\n"
            )
            + "## Docker Metadata\n"
        )
        + f"- Image Size: `{get_docker_image_size(args.docker_image)}`\n"
    ) + docker_info

    print(f"Going to post comment:\n\n{message}")
    res = requests.post(post_url, json={"body": message}, auth=(os.environ['GITHUB_KEY'], 'x-oauth-basic'))
    try:
        res.raise_for_status()
    except Exception as ex:
        print(f"Failed comment post: {ex}")    


if __name__ == "__main__":
    main()
