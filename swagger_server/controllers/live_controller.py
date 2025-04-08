import connexion
import six

from swagger_server.models.live_data import LiveData  # noqa: E501
from swagger_server import util


def live_site_id_get(site_id):  # noqa: E501
    """get information for visualization

     # noqa: E501

    :param site_id: ID of visualisation
    :type site_id: str

    :rtype: LiveData
    """
    return {
        "siteID": "jue",
        "siteHumanReadable": "JOYCE Jülich",
        "datetime": "2024-11-19 10:03:00",
        "data": {
            "temperature": {
            "value": 12.7,
            "unit": "°C"
            },
            "dewpoint": {
            "value": 9.6,
            "unit": "°C"
            }
        }
        }
