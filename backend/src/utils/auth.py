import requests
import base64
from tornado.options import options

AUTH_URL = "https://account.chalmers.it/userInfo.php"
QUERY_URL = AUTH_URL + "?cid=%s"
TOKEN_CHECK_URL = AUTH_URL + "?token=%s"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


class Auth(object):

    @staticmethod
    def __query_url(uri, param):
        if not isinstance(param, str):
            return dict()

        url = uri % param
        response = requests.get(url)
        return response.json()

    @staticmethod
    def get_user_from_token(token):
        return Auth.__query_url(TOKEN_CHECK_URL, token)

    @staticmethod
    def get_user_from_cid(cid):
        return Auth.__query_url(QUERY_URL, cid)

    @staticmethod
    def get_spotify_token():

        payload = dict(grant_type='client_credentials')
        raw = options.spotify_client_id+":"+options.spotify_secret
        encoded = base64.b64encode(raw.encode('utf-8'))
        decoded = encoded.decode('utf-8')

        headers = dict(Authorization="Basic " + decoded)

        response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=payload)

        return response.json()
