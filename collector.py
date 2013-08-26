import re
import os
import requests
import json
from subprocess import Popen, PIPE


api_url = "http://localhost:8081/farm/api/"
api_headers = {'content-type': 'application/json'}
nodename = "luna"


def reverse_sub(regex, string):
    ret = ""
    for letter in string:
        if re.match(regex, letter):
            ret += letter
        else:
            ret += "_"
    return ret


def collect_data():

    try:
        with open(os.devnull, 'w') as dnull:
            rawoutput = Popen(['apt-dater-host', 'status'],
                              stdout=PIPE,
                              stderr=dnull).communicate()
    except:
        print "apt-dater-host could not be executed."
        exit(1)

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
    return packagelist


def get_urls(api_url):
    response = requests.get(api_url, headers=api_headers)
    if response.status_code == 200:
        return json.loads(response.text)
    else:
        return response.status_code


def get_item(url):
    response = requests.get(url, headers=api_headers)
    if response.status_code == 200:
        queryset = json.loads(response.text)
        return queryset
    else:
        return response.status_code


def get_list(url):
    result = {}
    response = requests.get(url, headers=api_headers)
    if response.status_code == 200:
        queryset = json.loads(response.text)
        if queryset['count'] > 0:
            result = queryset['results']
            while queryset['next'] != None:
                response = requests.get(queryset['next'], headers=api_headers)
                if response.status_code == 200:
                    queryset = json.loads(response.text)
                    result = result + queryset['results']
            return result
        else:
            return []
    else:
        return response.status_code


def create_items(url, items):
    data = json.dumps(items)
    response = requests.post(url, data, headers=api_headers)
    if response.status_code == 201:
        queryset = json.loads(response.text)
        return queryset
    else:
        return response.status_code


def update_items(url, items):
    data = json.dumps(items)
    response = requests.put(url, data, headers=api_headers)
    if response.status_code == 201:
        queryset = json.loads(response.text)
        return queryset
    else:
        return response.status_code


def find_key(dictionary, key):
    for keys in dictionary:
        if key in keys:
            return True
    return False


def do_checks():
    urls = get_urls(api_url)
    local_packages = collect_data()
    node = get_item(urls['node'] + nodename)

    if node:
        remote_packages = get_list(urls['package']+'?packagetype=1')
        remote_packagechecks = get_list(node['url_packagecheck']+'&packagetype=1')
        
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

        created = create_items(urls['package'], new_packages)
        remote_packages.extend(created)

        local_packagechecks = []
        looplist_local_packages = list(local_packages)

        for local_package in looplist_local_packages:
            slug = reverse_sub("([a-z0-9-_]+)", local_package)

            if len(remote_packagechecks) > 0:
                index=0
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

        for remote_packagecheck in remote_packagechecks:
            uninstalled_package = remote_packagecheck
            uninstalled_package['uninstalled'] = True
            local_packagechecks.append(uninstalled_package)

        new_local_packagechecks = []
        for local_package in local_packages:
            slug = reverse_sub("([a-z0-9-_]+)", local_package)
            lp = local_packages[local_package]
            lp['node'] = node['url']
            lp['package'] = urls['package'] + slug + '/'
            lp['uninstalled'] = False
            new_local_packagechecks.append(lp)


        update_items(urls['packagecheck'], local_packagechecks)
        create_items(urls['packagecheck'], new_local_packagechecks)


do_checks()
