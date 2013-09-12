import re
import os
import sys
import logging
from subprocess import Popen, PIPE
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging

import settings
from api import Api

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
if settings.sentry:
    handler = SentryHandler(settings.sentry)
    setup_logging(handler)

# Settings
adh_bin = getattr(settings, 'apt-dater-host-binary', "/usr/bin/apt-dater-host")
api_url = getattr(settings, 'api_url', False)
nodename = getattr(settings, 'nodename', False)

if not os.path.exists(adh_bin):
    sys.stderr.write("%s not found" % adh_bin)
    logger.log(logging.WARNING, "%s not found" % adh_bin)
    exit(1)

if not api_url:
    sys.stderr.write("api_url not set")
    logger.log(logging.CRITICAL, "api_url not set")
    exit(1)

if not nodename:
    sys.stderr.write("nodename not set")
    logger.log(logging.CRITICAL, "nodename not set")
    exit(1)


def collect_data():
    try:
        with open(os.devnull, 'w') as dnull:
            rawoutput = Popen([adh_bin, 'status'],
                              stdout=PIPE,
                              stderr=dnull).communicate()
    except:
        sys.stderr.write("%s could not be executed!" % adh_bin)
        logger.log(logging.CRITICAL, "%s could not be executed!" % adh_bin)
        exit(1)

    try:
        rawoutput_lines = rawoutput[0].split("\n")
        packagelist = {}

        for line in rawoutput_lines:
            if re.match('^STATUS:', line):
                local_package = line[8:len(line)].split('|')

                temp = {}
                temp['current'] = local_package[1].strip()
                temp['latest'] = local_package[1].strip()
                temp['hasupdate'] = False

                if re.match('^u=', local_package[2].strip()):
                    temp['latest'] = local_package[2].split("=")[1].strip()
                    temp['hasupdate'] = True

                packagelist[local_package[0].strip()] = temp
    except:
        sys.stderr.write("local packagelist could not be composed")
        logger.log(logging.CRITICAL, "local packagelist could not be composed")
        exit(1)

    return packagelist


def reverse_sub(regex, string):
    ret = ""
    for letter in string:
        if re.match(regex, letter):
            ret += letter
        else:
            ret += "_"
    return ret


def main():
    api = Api(api_url)
    urls = api.get_urls()
    local_packages = collect_data()
    node = api.get_item(urls['node'] + nodename)

    if node:
        # Request package information
        remote_packages = api.get_list(urls['package']+'?packagetype=1')
        remote_packagechecks = api.get_list(node['url_packagecheck']+'&packagetype=1')

        # Check if new packages have been installed
        new_packages = []
        for local_package in local_packages:
            found = None
            slug = reverse_sub("([a-z0-9-_]+)", local_package)

            if len(remote_packages) > 0:
                for remotepackage in remote_packages:
                    if remotepackage['name'] == local_package:
                        found = remotepackage
                        break

            if found is None:
                new_package = {'name': local_package,
                               'slug': slug,
                               'packagetype': '1'}

                new_packages.append(new_package)

        # Create new packages
        created = api.create_items(urls['package'], new_packages)
        remote_packages.extend(created)

        # Update existing packagechecks
        local_packagechecks = []
        looplist_local_packages = list(local_packages)
        for local_package in looplist_local_packages:
            slug = reverse_sub("([a-z0-9-_]+)", local_package)

            if len(remote_packagechecks) > 0:
                index = 0
                for remote_packagecheck in remote_packagechecks:
                    if remote_packagecheck['package'] == urls['package'] + slug + '/':
                        local_packagecheck = remote_packagechecks.pop(index)
                        lptemp = local_packages.pop(local_package)
                        local_packagecheck['current'] = lptemp['current']
                        local_packagecheck['latest'] = lptemp['latest']
                        local_packagecheck['hasupdate'] = lptemp['hasupdate']
                        local_packagecheck['uninstalled'] = False
                        local_packagechecks.append(local_packagecheck)
                        break
                    index = index + 1

        # Set uninstalled flag on removed packages
        for remote_packagecheck in remote_packagechecks:
            uninstalled_package = remote_packagecheck
            uninstalled_package['uninstalled'] = True
            local_packagechecks.append(uninstalled_package)

        # Create new packagechecks
        new_local_packagechecks = []
        for local_package in local_packages:
            slug = reverse_sub("([a-z0-9-_]+)", local_package)
            lp = local_packages[local_package]
            lp['node'] = node['url']
            lp['package'] = urls['package'] + slug + '/'
            lp['uninstalled'] = False
            new_local_packagechecks.append(lp)

        # Execute updates and new packagechecks
        api.update_items(urls['packagecheck'], local_packagechecks)
        api.create_items(urls['packagecheck'], new_local_packagechecks)

if __name__=='__main__':
    main()
