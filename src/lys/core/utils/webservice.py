from typing import Any, Dict, Literal, List, Optional, Set, Union

from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE, \
    DISCONNECTED_WEBSERVICE_PUBLIC_TYPE
from lys.core.models.webservices import WebserviceFixturesModel

PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_1 = "a public webservice cannot be configured with any access level"
PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_2 = "a public webservice cannot be licenced"
CONNECTED_ACCESS_LEVEL_WEBSERVICE_CONFIG_ERROR_MESSAGE = ("connected access level cannot be associated with another "
                                                          "access level")

WebserviceIsPublicType = bool | Literal["disconnected"]


def check_webservice_config(
    is_public: WebserviceIsPublicType,
    access_levels: Set[str],
    is_licenced: bool,
):
    """
    Check webservice configuration
    :param is_public:
    :param access_levels:
    :param is_licenced:
    :return: error message if there is an error in configuration
    """
    error_message = None

    if is_public:
        if len(access_levels) > 0:
            error_message = PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_1
        elif is_licenced:
            error_message = PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_2

    elif CONNECTED_ACCESS_LEVEL in access_levels and len(access_levels) > 1:
        error_message = CONNECTED_ACCESS_LEVEL_WEBSERVICE_CONFIG_ERROR_MESSAGE

    return error_message


def generate_webservice_fixture(
        webservice_name: str,
        enabled: bool,
        is_public: WebserviceIsPublicType,
        access_levels: Union[List[str], None],
        is_licenced: bool,
        operation_type: Optional[str] = None,
        # TODO: Move ai_tool to AI app only (currently in core for testing)
        ai_tool: Optional[Dict[str, Any]] = None,
):
    if access_levels is None:
        _access_levels = set()
    else:
        # each string is unique in the list
        _access_levels = set(access_levels)

    error_message = check_webservice_config(is_public, _access_levels, is_licenced)

    # return an exception if there is an error
    if error_message:
        raise Exception("Wrong configuration for webservice '%s' : %s" % (
            webservice_name,
            error_message
        ))
    if is_public is True:
        is_public_ = NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE
    elif is_public is False:
        is_public_ = None
    else:
        is_public_ = is_public.upper()

    attributes = WebserviceFixturesModel.AttributesModel(
        public_type=is_public_,
        enabled=enabled,
        access_levels=list(_access_levels),
        is_licenced=is_licenced,
        operation_type=operation_type,
        ai_tool=ai_tool,
    )

    return WebserviceFixturesModel(
        id=webservice_name,
        attributes=attributes
    )

def format_filed_description(description: Optional[str], is_public: WebserviceIsPublicType, access_levels: List[str], is_licenced: bool):
    return (description if description is not None else "") + "\n" + (
        "PUBLIC"
        if is_public
        else (
            f"ACCESS LEVELS: {", ".join([access_level for access_level in access_levels])}"
            if (access_levels is not None and len(access_levels) > 0)
            else "ONLY FOR SUPER USER"
        ) + (" (Disconnected)" if is_public == DISCONNECTED_WEBSERVICE_PUBLIC_TYPE else "")
    ) + "\n" + ("UNDER LICENCE" if is_licenced else "LICENCE FREE")
