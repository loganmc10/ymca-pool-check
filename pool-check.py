import requests
import dateutil.parser
import dateutil.utils
import time
import os
import json
from datetime import datetime
from typing import Dict, Union, List, TypedDict
from dateutil.tz import gettz
from bs4 import BeautifulSoup  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry  # type: ignore


class ItemOutput(TypedDict):
    stream: Dict[str, str]
    values: List[List[str]]


class LokiOutput(TypedDict):
    streams: List[ItemOutput]


def get_metrics() -> List[Dict[str, Union[str, bool, int]]]:
    metrics = []
    with requests.Session() as s:
        retries = Retry(total=5, backoff_factor=0.5, status_forcelist=Retry.RETRY_AFTER_STATUS_CODES)
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            capacity = s.get('https://www.ymcacalgary.org/capacity/')
            if capacity.status_code != 200:
                print("HTTP error in GET capacity: " + capacity.text)
                return []
            soup = BeautifulSoup(capacity.content, "html.parser")
            table = soup.find_all('table')[0]
            table_body = table.find('tbody')
            rows = table_body.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    ymca: Dict[str, Union[str, bool, int]] = {}
                    metrics.append(ymca)
                    divs = cols[1].find_all('div')
                    ymca["name"] = cols[0].text
                    if len(divs) > 0:
                        ymca['status'] = divs[0]['id']
                    else:
                        ymca['status'] = cols[1]['id']
            script = soup.find_all('script')[3]
            script = str(script)
            for ymca in metrics:
                pos = script.find("#" + str(ymca['status']))
                pos = script.find("addClass(", pos)
                ymca['status'] = script[pos:].split('"')[1]

            hours = s.get('https://www.ymcacalgary.org/faqs/')
            if hours.status_code != 200:
                print("HTTP error in GET hours: " + hours.text)
                return []
            soup = BeautifulSoup(hours.content, "html.parser")
            tzinfos = {"MST": gettz("America/Edmonton")}
            table = soup.find_all('table')[1]
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    for ymca in metrics:
                        if str(ymca['name'])[:8] in cols[0].text:
                            mf = cols[1].text.split(' - ')
                            sat = cols[2].text.split(' - ')
                            if "Closed Sunday" in sat[1]:
                                sat[1] = sat[1].split('\r\n')[0]
                                sun = ["12:00am", "12:00am"]
                            else:
                                sun = sat
                            weekday = dateutil.utils.today(tzinfo=gettz("America/Edmonton")).weekday()
                            if weekday < 5:
                                open = dateutil.parser.parse(mf[0] + " MST", tzinfos=tzinfos)
                                close = dateutil.parser.parse(mf[1] + " MST", tzinfos=tzinfos)
                            elif weekday == 5:
                                open = dateutil.parser.parse(sat[0] + " MST", tzinfos=tzinfos)
                                close = dateutil.parser.parse(sat[1] + " MST", tzinfos=tzinfos)
                            else:
                                open = dateutil.parser.parse(sun[0] + " MST", tzinfos=tzinfos)
                                close = dateutil.parser.parse(sun[1] + " MST", tzinfos=tzinfos)
                            if time.time() < close.timestamp() and time.time() > open.timestamp():
                                ymca["open"] = True
                            else:
                                ymca["status"] = "red"
                                ymca["open"] = False
            for ymca in metrics:
                if ymca['status'] == 'green':
                    ymca['capacity'] = 0
                elif ymca['status'] == 'yellow':
                    ymca['capacity'] = 1
                elif ymca['status'] == 'red':
                    ymca['capacity'] = 2
        except (requests.exceptions.RequestException, OSError) as e:
            print("HTTP error in GET: %s" % e)
            return []
    return metrics


if __name__ == '__main__':
    with requests.Session() as s_loki:
        retries = Retry(total=5, backoff_factor=0.5, status_forcelist=Retry.RETRY_AFTER_STATUS_CODES)
        s_loki.mount('https://', HTTPAdapter(max_retries=retries))
        s_loki.auth = (os.environ['LOKI_USER'], os.environ['LOKI_PASS'])
        loki_output: LokiOutput = {'streams': []}
        item_output: ItemOutput = {'stream': {}, 'values': []}
        item_output['stream']['job'] = 'ymca_pools'
        metrics = get_metrics()
        for ymca in metrics:
            item_output['values'].append([str(time.time_ns()), json.dumps(ymca)])
        loki_output['streams'].append(item_output)
        if item_output['values']:
            try:
                r = s_loki.post('https://logs-prod-us-central2.grafana.net/loki/api/v1/push', json=loki_output, timeout=20)
                if r.status_code != 200 and r.status_code != 204:
                    print(str(datetime.now()) + " Loki error: " + r.text)
            except (requests.exceptions.RequestException, OSError) as e:
                print(str(datetime.now()) + " Error contacting Loki: %s" % e)
