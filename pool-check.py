import requests
import datetime
import dateutil.parser
import time
from dateutil.tz import gettz
from bs4 import BeautifulSoup  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry  # type: ignore


def main() -> None:
    with requests.Session() as s:
        # This tells Python to retry HTTP requests up to 5 times if they fail
        retries = Retry(total=5, backoff_factor=0.5, status_forcelist=Retry.RETRY_AFTER_STATUS_CODES)
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            capacity = s.get('https://www.ymcacalgary.org/capacity/')
            if capacity.status_code != 200:
                print("HTTP error in GET capacity: " + capacity.text)
                return
            soup = BeautifulSoup(capacity.content, "html.parser")
            data = {}
            table = soup.find_all('table')[0]
            table_body = table.find('tbody')
            rows = table_body.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    divs = cols[1].find_all('div')
                    if len(divs) > 0:
                        data[cols[0].text] = divs[0]['id']
                    else:
                        data[cols[0].text] = cols[1]['id']
            script = soup.find_all('script')[3]
            script = str(script)
            for key, value in data.items():
                pos = script.find("#" + value)
                pos = script.find("addClass(", pos)
                data[key] = {}
                data[key]['status'] = script[pos:].split('"')[1]

            hours = s.get('https://www.ymcacalgary.org/faqs/')
            if hours.status_code != 200:
                print("HTTP error in GET hours: " + hours.text)
                return
            soup = BeautifulSoup(hours.content, "html.parser")
            tzinfos = {"MST": gettz("America/Edmonton")}
            table = soup.find_all('table')[1]
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    for key, value in data.items():
                        if key[:8] in cols[0].text:
                            mf = cols[1].text.split(' - ')
                            sat = cols[2].text.split(' - ')
                            if "Closed Sunday" in sat[1]:
                                sat[1] = sat[1].split('\r\n')[0]
                                sun = ["12:00am", "12:00am"]
                            else:
                                sun = sat
                            weekday = datetime.datetime.today().weekday()
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
                                data[key]["open"] = True
                            else:
                                data[key]["status"] = "red"
                                data[key]["open"] = False
            for key, value in data.items():
                if data[key]['status'] == 'green':
                    data[key]['value'] = 0
                elif data[key]['status'] == 'yellow':
                    data[key]['value'] = 1
                elif data[key]['status'] == 'red':
                    data[key]['value'] = 2
            print(data)
        except (requests.exceptions.RequestException, OSError) as e:
            print("HTTP error in GET: %s" % e)
            return


if __name__ == '__main__':
    main()
