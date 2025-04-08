# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.site_details import SiteDetails  # noqa: E501
from swagger_server.models.site_list import SiteList  # noqa: E501
from swagger_server.test import BaseTestCase


class TestSitesController(BaseTestCase):
    """SitesController integration test stubs"""

    def test_sites_get(self):
        """Test case for sites_get

        list all sites
        """
        response = self.client.open(
            '/sites',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_sites_site_id_get(self):
        """Test case for sites_site_id_get

        get details for site
        """
        response = self.client.open(
            '/sites/{siteId}'.format(site_id='site_id_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
