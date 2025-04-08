import connexion
import six

from swagger_server.models.visualization_list import VisualizationList  # noqa: E501
from swagger_server import util
from flask import send_file


def sites_site_id_visualization_instrument_id_product_id_aggregation_date_str_get(aggregation, site_id, instrument_id, product_id, date_str):  # noqa: E501
    """get quicklooks

    get quicklooks # noqa: E501

    :param aggregation: ID of site to return
    :type aggregation: str
    :param site_id: ID of site to return
    :type site_id: str
    :param instrument_id: ID of site to return
    :type instrument_id: str
    :param product_id: ID of site to return
    :type product_id: str
    :param date_str: ID of site to return
    :type date_str: str

    :rtype: str
    """
    return send_file('/data/obs/site/jue/chm15k/l0/2025/01/07/20250107_JOYCE_CHM120109_000.nc.png')


def visualizations_by_id_visualization_id_date_str_get(visualization_id, date_str):  # noqa: E501
    """get quicklooks

    get quicklooks # noqa: E501

    :param visualization_id: ID of site to return
    :type visualization_id: int
    :param date_str: ID of site to return
    :type date_str: str

    :rtype: str
    """
    return send_file('/data/obs/site/jue/chm15k/l0/2025/01/07/20250107_JOYCE_CHM120109_000.nc.png')


def visualizations_get():  # noqa: E501
    """list all visualizations

     # noqa: E501


    :rtype: VisualizationList
    """
    return [
        {
            "aggregation": "daily",
            "instrumentHumanReadable": "Lufft CHM15k",
            "instrumentID": "ceilo_chm15k",
            "productHumanReadable": "raw signal",
            "productID": "ceilo_chm15k_raw",
            "siteHumanReadable": "JOYCE Jülich",
            "siteID": "jue",
            "visualisationID": 4711
        }
    ]
    
