from logging import getLogger
from sanic import Blueprint
from sanic.response import json
from ..middlewares import authenticate, require_fields, ClientType
from ..storage import drivers 

bp = Blueprint("groups")
logger = getLogger(__name__)

@bp.route("/<game>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def create(req, jwt):
    pass

@bp.route("/invite/<uuid>", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite(req, name, jwt):
    pass

@bp.route("/leave", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def leave(req, jwt):
    pass
