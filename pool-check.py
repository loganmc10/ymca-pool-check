import requests
from bs4 import BeautifulSoup  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry  # type: ignore


def main() -> None:
    with requests.Session() as s:
        # This tells Python to retry HTTP requests up to 5 times if they fail
        retries = Retry(total=5, backoff_factor=0.5, status_forcelist=Retry.RETRY_AFTER_STATUS_CODES)
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            r = s.get('https://www.ymcacalgary.org/capacity/')
            if r.status_code != 200:
                print("HTTP error in GET: " + r.text)
                return
            soup = BeautifulSoup(r.content, "html.parser")
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
                data[key] = script[pos:].split('"')[1]
            print(data)
        except (requests.exceptions.RequestException, OSError) as e:
            print("HTTP error in GET: %s" % e)
            return


if __name__ == '__main__':
    main()
