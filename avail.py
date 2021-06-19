#!/usr/bin/env python3


import shlex
from sys import exit

import requests
from bs4 import BeautifulSoup


LINUX_MAN_PAGES = 'https://www.man7.org/linux/man-pages/man1/{}.1.html'
BSD_MAN_PAGES = 'https://bsd-unix.com/man.cgi?query={}&sektion=1&manpath=2.10+BSD&format=html'
# Man pages for Solaris user commands
SOLARIS_USER_MAN_PAGES = 'https://docs.oracle.com/cd/E23824_01/html/821-1461/{}-1.html'
# Man pages for Solaris admin commands
SOLARIS_ADMIN_MAN_PAGES = 'https://docs.oracle.com/cd/E23824_01/html/821-1462/{}-1m.html'
PLAN_9_MAN_PAGES = 'http://man.cat-v.org/plan_9/1/{}'
POSIX7_PAGES = 'https://pubs.opengroup.org/onlinepubs/9699919799/utilities/{}.html'
GNU_HTML_MANUALS = 'https://www.gnu.org/software/{}/manual/html_chapter/index.html'


def main():
    try:
        input_loop()
    except KeyboardInterrupt:
        exit(0)


def input_loop():
    while True:
        user_input = input('Command: ')

        command = shlex.split(user_input)
        command_name = command[0]

        user_opts = {x for x in command if x[0] == '-'}

        linux_opts, description = get_linux_opts(command_name)

        if linux_opts is None:
            print(f'Failed to find result for "{command_name}".')
            continue

        print()
        print(description)
        print()

        for opt in (user_opts - linux_opts):
            print(f'{opt} not available on Linux.')

        exit(0)


def get_linux_opts(command_name):
    """Get options for GNU/Linux"""

    opts = None
    description = None

    soup = get_soup(LINUX_MAN_PAGES, command_name)

    if soup is None:
        return opts, description

    # The description is always the second pre on the page
    description = soup.find_all('pre')[1].text.strip()

    opts = set()

    opts.update(find_opts(soup, 'OPTIONS'))
    # The GNU find man page has more options under the EXPRESSION header
    opts.update(find_opts(soup, 'EXPRESSION'))

    return opts, description


def find_opts(soup, header):
    # Get the source line of the header
    options_source_line = soup.find(id=header).sourceline

    # Get the element where the options are described
    opts_el = [pre for pre in soup.find_all('pre') if pre.sourceline == options_source_line][0]

    opts_lines = opts_el.text.split('\n')
    opts_lines = [line.lstrip().split(maxsplit=1)[0] for line in opts_lines if line]
    opts = [line for line in opts_lines if line[0] == '-']

    # Remove false positives
    opts = {o for o in opts if not o[-1] in '.,;)]}!'}

    return opts


def get_soup(pages_string, command_name):
    """Get soup for any OS based on command name"""

    # TODO Implement caching up to 5MB worth of searches

    res = requests.get(pages_string.format(command_name))

    if res.status_code < 200 or res.status_code > 299:
        return None

    soup = BeautifulSoup(res.text, 'html.parser')
    return soup


if __name__ == '__main__':
    main()
