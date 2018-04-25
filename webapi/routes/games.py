from logging import getLogger
from sanic import Blueprint
from sanic.response import json
from ..middlewares import authenticate, require_fields, ClientType
from ..storage import drivers 

bp = Blueprint("games")
logger = getLogger(__name__)

@bp.route("/", methods=["POST"])
@require_fields({"name"})
@authenticate({ClientType.ADMIN})
async def create(req, name, jwt):
    await drivers.RDB.create_game(name, jwt["uid"])
    return json({})

@bp.route("/<name>", methods=["GET"])
async def retrieve(req, name):
    game = await drivers.RDB.get_game_by_name(name)
    return json(game._asdict())
