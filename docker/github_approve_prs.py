#!/usr/bin/env python3

import argparse
import requests
import os


def main():
    parser = argparse.ArgumentParser(description='Approve Github PRs. Used to mass approve dependabot prs.'
                                     ' SET GITHUB_USER and GITHUB_TOKEN env vars for authentication',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-t", "--title", help="Title prefix for prs to approve.",
                        required=False, default="Bump demisto/")
    parser.add_argument("-a", "--author", help="Author of prs to approve.",
                        required=False, default="dependabot-preview[bot]")
    parser.add_argument("-c", "--comment", help="Comment to add to the PR",
                        required=False, default="@dependabot squash and merge")
    args = parser.parse_args()
    auth = (os.environ["GITHUB_USER"], os.environ["GITHUB_TOKEN"])
    res = requests.get(
        "https://api.github.com/search/issues?q=is:pr+repo:demisto/dockerfiles+state:open+review:required&per_page", auth=auth)
    res.raise_for_status()
    open_prs = res.json().get('items')
    print(f"Found [{len(open_prs)}] prs")
    for pr in open_prs:
        title = pr.get('title')
        user = pr.get('user')
        author = user.get('login') if user else ""
        pr_num = pr['number']
        if title and title.startswith(args.title) and author == args.author:
            # print("Checking review status for pr [{}]: [{}]".format(pr_num, title))
            print(f"Approving PR [{pr_num}]: [{title}]")
            requests.post(
                f"https://api.github.com/repos/demisto/dockerfiles/pulls/{pr_num}/reviews",
                json={"event": "APPROVE"},
                auth=auth,
            ).raise_for_status()

            requests.post(
                f"https://api.github.com/repos/demisto/dockerfiles/issues/{pr_num}/comments",
                json={"body": args.comment},
                auth=auth,
            ).raise_for_status()

        else:
            print(
                f"Skiping [{pr_num}] pr as title [{title}] and author [{author}] don't match"
            )


if __name__ == "__main__":
    main()
