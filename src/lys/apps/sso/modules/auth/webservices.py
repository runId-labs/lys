import logging

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from lys.apps.sso.consts import SSO_MODE_LOGIN, SSO_MODE_SIGNUP, SSO_MODE_LINK, VALID_SSO_MODES
from lys.apps.sso.errors import SSO_INVALID_MODE
from lys.apps.user_auth.consts import ACCESS_COOKIE_KEY
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.managers.app import LysAppManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["sso"])


@router.get("/{provider}/login")
async def sso_login(provider: str, request: Request, mode: str = SSO_MODE_LOGIN):
    """
    Initiate SSO OAuth2 flow.

    Redirects user to the SSO provider's authorization page.

    Query params:
        mode: "login" (default), "signup", or "link"
    """
    if mode not in VALID_SSO_MODES:
        raise LysError(SSO_INVALID_MODE, f"Invalid SSO mode '{mode}'. Must be one of: {VALID_SSO_MODES}")

    app_manager = LysAppManager()
    sso_auth_service = app_manager.get_service("sso_auth")
    front_url = app_manager.settings.front_url

    try:
        # Build callback URL from current request
        callback_url = str(request.url_for("sso_callback", provider=provider))

        authorize_url = await sso_auth_service.generate_authorize_url(
            provider=provider,
            mode=mode,
            callback_url=callback_url,
        )

        return RedirectResponse(url=authorize_url, status_code=302)

    except LysError as e:
        logger.warning(f"SSO login error: {e.debug_message}")
        error_code = e.detail if e.detail else "SSO_CALLBACK_ERROR"
        return RedirectResponse(url=f"{front_url}?error={error_code}", status_code=302)
    except Exception as e:
        logger.exception(f"SSO login unexpected error: {e}")
        return RedirectResponse(url=f"{front_url}?error=SSO_CALLBACK_ERROR", status_code=302)


@router.get("/{provider}/callback")
async def sso_callback(provider: str, request: Request, code: str = "", state: str = "", error: str = ""):
    """
    Handle SSO OAuth2 callback from provider.

    Exchanges authorization code for tokens, then redirects to frontend
    based on the SSO mode (login, signup, link).
    """
    app_manager = LysAppManager()
    front_url = app_manager.settings.front_url

    # Handle provider-side errors (e.g. user cancelled authorization)
    if error:
        error_description = request.query_params.get("error_description", "")
        logger.info(f"SSO callback denied: provider={provider}, error={error}, description={error_description}")
        return RedirectResponse(url=f"{front_url}?error=SSO_CALLBACK_ERROR", status_code=302)

    sso_auth_service = app_manager.get_service("sso_auth")

    try:
        # Build callback URL (same as the one used in login)
        callback_url = str(request.url_for("sso_callback", provider=provider))

        # Exchange code for tokens and get user info
        user_info = await sso_auth_service.handle_callback(
            provider=provider,
            code=code,
            state=state,
            callback_url=callback_url,
        )

        mode = user_info["mode"]
        response = RedirectResponse(url=front_url, status_code=302)

        if mode == SSO_MODE_LOGIN:
            async with app_manager.database.get_session() as session:
                redirect_url = await sso_auth_service.handle_login(user_info, response, session)
                await session.commit()
            if redirect_url != front_url:
                # User not found — redirect to error URL without cookies
                response = RedirectResponse(url=redirect_url, status_code=302)

        elif mode == SSO_MODE_SIGNUP:
            redirect_url = await sso_auth_service.handle_signup(user_info)
            response = RedirectResponse(url=redirect_url, status_code=302)

        elif mode == SSO_MODE_LINK:
            # For link mode, user must be authenticated
            access_token = request.cookies.get(ACCESS_COOKIE_KEY)
            if not access_token:
                response = RedirectResponse(url=f"{front_url}?error=SSO_NOT_AUTHENTICATED", status_code=302)
            else:
                auth_utils = AuthUtils()
                claims = await auth_utils.decode(access_token)
                connected_user_id = claims.get("sub")

                async with app_manager.database.get_session() as session:
                    redirect_url = await sso_auth_service.handle_link(user_info, connected_user_id, session)
                    await session.commit()
                response = RedirectResponse(url=redirect_url, status_code=302)

        return response

    except LysError as e:
        logger.warning(f"SSO callback error: {e.debug_message}")
        error_code = e.detail if e.detail else "SSO_CALLBACK_ERROR"
        return RedirectResponse(url=f"{front_url}?error={error_code}", status_code=302)
    except Exception as e:
        logger.exception(f"SSO callback unexpected error: {e}")
        return RedirectResponse(url=f"{front_url}?error=SSO_CALLBACK_ERROR", status_code=302)