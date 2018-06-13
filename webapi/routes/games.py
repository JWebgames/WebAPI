"""Games routes, get/create/update games"""

from logging import getLogger
from operator import methodcaller
from sanic import Blueprint
from sanic.response import json
from sanic.exceptions import NotFound
from ..middlewares import authenticate, require_fields
from ..server import RDB
from ..storage.models import ClientType
from ..exceptions import NotFoundError

bp = Blueprint("games")
logger = getLogger(__name__)

@bp.route("/create", methods=["POST"])
@require_fields({"name", "capacity"})
@authenticate({ClientType.ADMIN})
async def create(_req, name, capacity, jwt):
    """Create a game"""
    gameid = await RDB.create_game(name, jwt["uid"], capacity)
    logger.info("Game created: %d-%s", gameid, name)
    return json({"gameid": gameid})

@bp.route("/byid/<id_:int>", methods=["GET"])
async def retrieve_by_id(_req, id_):
    """Get a game given its id"""
    try:
        game = await RDB.get_game_by_id(id_)
    except NotFoundError as exc:
        raise NotFound("Game ID {} doesn't exist".format(id_)) from exc
    return json(game.asdict())

@bp.route("/byname/<name>", methods=["GET"])
async def retrieve_by_name(_req, name):
    """Get a game given its name"""
    try:
        game = await RDB.get_game_by_name(name)
    except NotFoundError as exc:
        raise NotFound("Game {} doesn't exist".format(name)) from exc
    return json(game.asdict())

@bp.route("/", methods=["GET"])
async def get_all(_req):
    """Get all games"""
    games = await RDB.get_all_games()
    return json(list(map(methodcaller("asdict"), games)))
