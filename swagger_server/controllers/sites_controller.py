import connexion
import six

from swagger_server.models.site_details import SiteDetails  # noqa: E501
from swagger_server.models.site_list import SiteList  # noqa: E501
from swagger_server import util


def sites_get():  # noqa: E501
    """list all sites

    Returns a list of all sites # noqa: E501


    :rtype: SiteList
    """
    return [
        {
            "siteID": "jue",
            "siteHumanReadable": "JOYCE Jülich"
        },
        {
            "siteID": "nya",
            "siteHumanReadable": "Ny-Ålesund"
        },
    ]


def sites_site_id_get(site_id):  # noqa: E501
    """get details for site

    Returns information on a single site # noqa: E501

    :param site_id: ID of site to return
    :type site_id: str

    :rtype: SiteDetails
    """
    return {
        "siteID": "jue",
        "siteHumanReadable": "JOYCE Jülich",
        "description": "The Jülich ObservatorY for Cloud Evolution (JOYCE) is operated jointly by the University of Cologne, the Research Centre Jülich. JOYCE was originally operated in the frame of the Transregional Collaborative Research Centre “Patterns in Soil-Vegetation-Atmosphere-Systems: Monitoring, Modelling and Data Assimilation” (TR32). Today, JOYCE is part of the Cloud and Precipitation Exploration Laboratory (CPEX-LAB), a competence centre within the Geoverbund ABC/J.",
        }
