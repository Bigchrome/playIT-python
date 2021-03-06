import requests

QUERY_URL = "https://account.chalmers.it/userInfo.php?cid=%s"


class Auth(object):

    @staticmethod
    def get_user(cid):

        if not isinstance(cid, str):
            return dict()

        response = requests.get(QUERY_URL % cid)
        dump = response.json()

        return response.json()
