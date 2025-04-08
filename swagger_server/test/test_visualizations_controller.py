# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.visualization_list import VisualizationList  # noqa: E501
from swagger_server.test import BaseTestCase


class TestVisualizationsController(BaseTestCase):
    """VisualizationsController integration test stubs"""

    def test_sites_site_id_visualization_instrument_id_product_id_aggregation_date_str_get(self):
        """Test case for sites_site_id_visualization_instrument_id_product_id_aggregation_date_str_get

        get quicklooks
        """
        response = self.client.open(
            '/visualizations/byQuery/{siteId}/{instrumentID}/{productID}/{aggregation}/{dateStr}'.format(aggregation='aggregation_example', site_id='site_id_example', instrument_id='instrument_id_example', product_id='product_id_example', date_str='date_str_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_visualizations_by_id_visualization_id_date_str_get(self):
        """Test case for visualizations_by_id_visualization_id_date_str_get

        get quicklooks
        """
        response = self.client.open(
            '/visualizations/byID/{visualizationID}/{dateStr}'.format(visualization_id=56, date_str='date_str_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_visualizations_get(self):
        """Test case for visualizations_get

        list all visualizations
        """
        response = self.client.open(
            '/visualizations',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
