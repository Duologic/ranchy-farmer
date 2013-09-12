import requests
import json

class Api(object):
    api_headers = {'content-type': 'application/json'}
    api_url = None
    last_response = None

    class RequestError(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def __init__(self, api_url):
        self.api_url = api_url

    def get_urls(self):
        response = requests.get(self.api_url, headers=self.api_headers)
        self.last_response = response
        if response.status_code == 200:
            return json.loads(response.text)
        else:
            raise self.RequestError("Request returned HTTP status %s" % response.status_code)

    def get_item(self, url):
        response = requests.get(url, headers=self.api_headers)
        self.last_response = response
        if response.status_code == 200:
            queryset = json.loads(response.text)
            return queryset
        else:
            raise self.RequestError("Request returned HTTP status %s" % response.status_code)


    def get_list(self, url):
        result = {}
        response = requests.get(url, headers=self.api_headers)
        self.last_response = response
        if response.status_code == 200:
            queryset = json.loads(response.text)
            if queryset['count'] > 0:
                result = queryset['results']
                while queryset['next'] is not None:
                    response = requests.get(queryset['next'],
                                            headers=self.api_headers)
                    self.last_response = response
                    if response.status_code == 200:
                        queryset = json.loads(response.text)
                        result = result + queryset['results']
                return result
            else:
                return []
        else:
            raise self.RequestError("Request returned HTTP status %s" % response.status_code)

    def create_items(self, url, items):
        data = json.dumps(items)
        response = requests.post(url, data, headers=self.api_headers)
        self.last_response = response
        if response.status_code == 201:
            queryset = json.loads(response.text)
            return queryset
        else:
            raise self.RequestError("Request returned HTTP status %s" % response.status_code)


    def update_items(self, url, items):
        data = json.dumps(items)
        response = requests.put(url, data, headers=self.api_headers)
        self.last_response = response
        if response.status_code == 201:
            queryset = json.loads(response.text)
            return queryset
        else:
            raise self.RequestError("Request returned HTTP status %s" % response.status_code)
