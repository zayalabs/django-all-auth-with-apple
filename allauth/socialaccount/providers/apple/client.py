import requests
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from django.utils.http import urlencode

import jwt

from allauth.socialaccount.providers.oauth2.client import (
    OAuth2Client,
    OAuth2Error,
)


class Scope(object):
    EMAIL = 'email'
    NAME = 'name'


class AppleOAuth2Client(OAuth2Client):
    """
    Custom client because `Sign In With Apple`:
        * requires `response_mode` field in redirect_url
        * requires special `client_secret` as JWT
    """

    def generate_client_secret(self):
        """Create a JWT signed with an apple provided private key"""
        now = datetime.utcnow()
        claims = {
            'iss': self.key,
            'aud': 'https://appleid.apple.com',
            'sub': self.get_client_id(),
            'iat': now,
            'exp': now + timedelta(hours=1),
        }
        headers = {'kid': self.consumer_secret, 'alg': 'ES256'}
        client_secret = jwt.encode(
            payload=claims, key=self.cert, algorithm='ES256', headers=headers
        ).decode('utf-8')
        return client_secret

    def get_client_id(self):
        """ We support multiple client_ids, but use the first one for api calls """
        return self.consumer_key.split(',')[0]

    def get_access_token(self, code):
        url = self.access_token_url
        client_secret = self.generate_client_secret()
        data = {
            'client_id': self.get_client_id(),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.callback_url,
            'client_secret': client_secret,
        }
        self._strip_empty_keys(data)
        resp = requests.request(
            self.access_token_method, url, data=data, headers=self.headers
        )
        access_token = None
        if resp.status_code in [200, 201]:
            try:
                access_token = resp.json()
            except ValueError:
                access_token = dict(parse_qsl(resp.text))
        if not access_token or 'access_token' not in access_token:
            raise OAuth2Error(
                'Error retrieving access token: %s' % resp.content
            )
        return access_token

    def get_redirect_url(self, authorization_url, extra_params):
        params = {
            'client_id': self.get_client_id(),
            'redirect_uri': self.callback_url,
            'response_mode': 'form_post',
            'scope': self.scope,
            'response_type': "code id_token",
        }
        if self.state:
            params['state'] = self.state
        params.update(extra_params)
        return '%s?%s' % (authorization_url, urlencode(params))
