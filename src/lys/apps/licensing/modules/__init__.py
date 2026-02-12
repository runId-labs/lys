"""
Licensing app modules.

Import order matters for fixture dependencies:
- application, rule must come before plan (LicensePlanDevFixtures depends on them)
- plan must come before client (ClientDevFixtures depends on LicensePlanVersionDevFixtures)
- event must come after user (extends EventService from user_auth)
"""
from . import application
from . import rule
from . import plan
from . import auth
from . import checker
from . import client
from . import event
from . import emailing
from . import notification
from . import mollie
from . import role
from . import subscription
from . import user
from . import webservice


__submodules__ = [
    application,
    rule,
    plan,
    auth,
    checker,
    client,
    mollie,
    role,
    subscription,
    user,
    event,
    emailing,
    notification,
    webservice,
]