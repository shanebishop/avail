#!/usr/bin/env python3


import shlex
from sys import exit

try:
    import requests
    from bs4 import BeautifulSoup
except ModuleNotFoundError as e:
    print(e)
    print('Install dependencies for this script by running "python3 -m pip install requirements.txt".')
    exit(1)


LINUX_MAN_PAGES = 'https://www.man7.org/linux/man-pages/man1/{}.1.html'
FREEBSD_MAN_PAGES = 'https://bsd-unix.com/man.cgi?query={}&sektion=1&manpath=FreeBSD+9.3-stable&format=html'
# Man pages for Solaris user commands
SOLARIS_USER_MAN_PAGES = 'https://docs.oracle.com/cd/E23824_01/html/821-1461/{}-1.html'
# Man pages for Solaris admin commands
SOLARIS_ADMIN_MAN_PAGES = 'https://docs.oracle.com/cd/E23824_01/html/821-1462/{}-1m.html'
PLAN_9_MAN_PAGES = 'http://man.cat-v.org/plan_9/1/{}'
POSIX7_PAGES = 'https://pubs.opengroup.org/onlinepubs/9699919799/utilities/{}.html'
GNU_HTML_MANUALS = 'https://www.gnu.org/software/{}/manual/html_chapter/index.html'

NON_OPTS_CHARS = '.,;)]}!'


def main():
    print('Disclaimer: Even if an option is available on another OS, there')
    print('            may be subtle differences between implementations.')
    print()

    try:
        input_loop()
    except KeyboardInterrupt:
        exit(0)


def input_loop():
    while True:
        user_input = input('Enter command or ^C: ')

        command = shlex.split(user_input)
        if command == []:
            continue
        command_name = command[0]

        user_opts = {x for x in command if x and x[0] == '-' and x != '-'}

        linux_opts, description = get_linux_opts(command_name)
        freebsd_opts = get_freebsd_opts(command_name)
        solaris_opts = get_solaris_opts(command_name)

        if linux_opts is None and freebsd_opts is None and solaris_opts is None:
            print(f'Failed to find result for "{command_name}".')
            continue

        plan_9_opts = get_plan_9_opts(command_name)
        posix_7_opts = get_posix_7_opts(command_name)

        if description:
            print()
            print(description)
        print()

        if freebsd_opts is None:
            print(f'{command_name} is not available on FreeBSD.')
        if plan_9_opts is None:
            print(f'{command_name} does not have a Plan 9 implementation.')
        if posix_7_opts is None:
            print(f'{command_name} is not a POSIX 7 utility.')
        if solaris_opts is None:
            print(f'{command_name} is not available on Solaris.')

        for opt in user_opts:
            not_present_list = []

            if linux_opts and opt not in linux_opts:
                not_present_list.append('GNU/Linux')
            if freebsd_opts and opt not in freebsd_opts:
                not_present_list.append('FreeBSD')
            if plan_9_opts and opt not in plan_9_opts:
                not_present_list.append('Plan 9')
            if solaris_opts and opt not in solaris_opts:
                not_present_list.append('Solaris')

            print(f'{opt} not available on the following: {not_present_list}')

        print()
        print('Linux man page:', LINUX_MAN_PAGES.format(command_name))
        print('GNU HTML manual:', GNU_HTML_MANUALS.format(command_name))
        if freebsd_opts is not None:
            print('FreeBSD man page:', FREEBSD_MAN_PAGES.format(command_name))
        if plan_9_opts is not None:
            print('Plan 9 man page:', PLAN_9_MAN_PAGES.format(command_name))
        if posix_7_opts is not None:
            print('POSIX 7 reference page:', POSIX7_PAGES.format(command_name))
        print()


def get_soup(pages_string, command_name):
    """Get soup for any OS based on command name.
    Returns (soup, page_found)."""

    # TODO Implement caching up to 5MB worth of searches

    soup = None

    # Some of the pages will be unhappy if they do not appear
    # to be visited by a browser, so emulate Google Chrome on
    # Windows
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.106 Safari/537.36',
    }

    res = requests.get(pages_string.format(command_name), headers=headers)

    if res.status_code < 200 or res.status_code > 299:
        return soup, False

    # For the FreeBSD site, it will still return 200 status code even if utility
    # is not found, so we need to check if the utility was found
    if pages_string == FREEBSD_MAN_PAGES and 'Sorry, no data found' in res.text:
        return soup, False

    soup = BeautifulSoup(res.text, 'html.parser')

    return soup, True


def get_linux_opts(command_name):
    """Get options for GNU/Linux"""

    opts = None
    description = None

    soup, page_found = get_soup(LINUX_MAN_PAGES, command_name)

    if not page_found:
        return opts, description

    # The description is always the second pre on the page
    description = soup.find_all('pre')[1].text.strip()

    search_sections = [
        'OPTIONS',
        'EXPRESSION',  # The GNU find man page has more options under this heading
    ]

    opts = set()
    for section in search_sections:
        opts.update(find_opts_linux(soup, section))

    return opts, description


def find_opts_linux(soup, header):
    """Returns options in a section of a Linux man page.
    The section searched is identified by the header."""

    # Get the source line of the header
    header_el = soup.find(id=header)
    if header_el is None:
        return set()
    header_source_line = soup.find(id=header).sourceline

    # Get the element where the options are described
    opts_el = [pre for pre in soup.find_all('pre') if pre.sourceline == header_source_line][0]

    opts_lines = opts_el.text.split('\n')
    opts_lines = [line.lstrip().split(maxsplit=1)[0] for line in opts_lines if line]
    opts = [line for line in opts_lines if line[0] == '-' and line != '-']

    # Remove false positives
    opts = {o for o in opts if not o[-1] in NON_OPTS_CHARS}

    return opts


def get_freebsd_opts(command_name):
    soup, page_found = get_soup(FREEBSD_MAN_PAGES, command_name)

    if not page_found:
        return None

    opts = find_opts_freebsd(soup)
    return opts


def find_opts_freebsd(soup):
    lines = soup.text.split('\n')
    opts_lines = [line.lstrip().split(maxsplit=1)[0] for line in lines if line.strip()]
    opts = [line for line in opts_lines if line[0] == '-' and line != '-']

    # Remove false positives
    opts = {o for o in opts if not o[-1] in NON_OPTS_CHARS}

    return opts


def get_plan_9_opts(command_name):
    # Some of the plan 9 man pages don't contain the options
    # on lines by themselves, so we hardcode the options instead
    if command_name == 'cp':
        return {'-g', '-u', '-x'}
    elif command_name == 'fcp':
        return {'-g', '-u', '-x'}
    elif command_name == 'mv':
        return set()

    soup, page_found = get_soup(PLAN_9_MAN_PAGES, command_name)

    if not page_found:
        return None

    opts = find_opts_plan_9(soup)
    return opts


def find_opts_plan_9(soup):
    lines = soup.text.split('\n')
    opts_lines = [line.lstrip().split(maxsplit=1)[0] for line in lines if line.strip()]
    opts = [line for line in opts_lines if line[0] == '-' and line != '-']

    # Remove false positives
    opts = {o for o in opts if not o[-1] in NON_OPTS_CHARS}

    return opts


def get_posix_7_opts(command_name):
    soup, page_found = get_soup(POSIX7_PAGES, command_name)

    if not page_found:
        return None

    opts = find_opts_posix_7(soup)
    return opts


def find_opts_posix_7(soup):
    opts_candidates = soup.find_all('dt')
    opts = [o.text for o in opts_candidates if o.text and o.text[0] == '-' and o.text != '-']

    # Remove false positives
    opts = {o for o in opts if not o[-1] in NON_OPTS_CHARS}

    return opts


def get_solaris_opts(command_name):
    soup, page_found = get_soup(SOLARIS_USER_MAN_PAGES, command_name)

    if not page_found:
        soup, page_found = get_soup(SOLARIS_ADMIN_MAN_PAGES, command_name)
        if not page_found:
            return None

    opts = find_opts_solaris(soup)

    return opts


def find_opts_solaris(soup):
    opts_candidates = soup.find_all('tt')
    opts = [o.text for o in opts_candidates if o.text and o.text[0] == '-' and o.text != '-']

    # Remove false positives
    opts = {o for o in opts if not o[-1] in NON_OPTS_CHARS}

    return opts


if __name__ == '__main__':
    main()
