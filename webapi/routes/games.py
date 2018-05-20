from logging import getLogger
from operator import methodcaller
from sanic import Blueprint
from sanic.response import json
from sanic.exceptions import NotFound
from ..middlewares import authenticate, require_fields
from ..storage import drivers 
from ..storage.models import ClientType
from ..exceptions import NotFoundError

bp = Blueprint("games")
logger = getLogger(__name__)

@bp.route("/create", methods=["POST"])
@require_fields({"name", "capacity"})
@authenticate({ClientType.ADMIN})
async def create(req, name, capacity, jwt):
    gameid = await drivers.RDB.create_game(name, jwt["uid"], capacity)
    logger.info("Game created: %d-%s", gameid, name)
    return json({"gameid": gameid})

@bp.route("/byid/<id_:int>", methods=["GET"])
async def retrieve(req, id_):
    try:
        game = await drivers.RDB.get_game_by_id(id_)
    except NotFoundError as exc:
        raise NotFound("Game ID {} doesn't exist".format(id_)) from exc
    return json(game.asdict())

@bp.route("/byname/<name>", methods=["GET"])
async def retrieve(req, name):
    try:
        game = await drivers.RDB.get_game_by_name(name)
    except NotFoundError as exc:
        raise NotFound("Game {} doesn't exist".format(name)) from exc
    return json(game.asdict())

@bp.route("/", methods=["GET"])
async def get_all(req):
    games = await drivers.RDB.get_all_games()
    return json(list(map(methodcaller("asdict"), games)))
