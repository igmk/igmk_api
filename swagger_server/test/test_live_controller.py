# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.live_data import LiveData  # noqa: E501
from swagger_server.test import BaseTestCase


class TestLiveController(BaseTestCase):
    """LiveController integration test stubs"""

    def test_live_site_id_get(self):
        """Test case for live_site_id_get

        get information for visualization
        """
        response = self.client.open(
            '/live/{siteId}'.format(site_id='site_id_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
