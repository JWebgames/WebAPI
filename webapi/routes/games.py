from logging import getLogger
from operator import methodcaller
from sanic import Blueprint
from sanic.response import json
from sanic.exceptions import NotFound
from ..middlewares import authenticate, require_fields
from ..storage import drivers 
from ..storage.models import ClientType

bp = Blueprint("games")
logger = getLogger(__name__)

@bp.route("/create", methods=["POST"])
@require_fields({"name", "capacity"})
@authenticate({ClientType.ADMIN})
async def create(req, name, capacity, jwt):
    gameid = await drivers.RDB.create_game(name, jwt["uid"], capacity)
    logger.info("Game created: %d-%s", gameid, name)
    return json({"gameid": gameid})

@bp.route("/<name>", methods=["GET"])
async def retrieve(req, name):
    game = await drivers.RDB.get_game_by_name(name)
    if not game:
        raise NotFound("{} doesn't exist")
    d = game._asdict()
    d["ownerid"] = str(d["ownerid"])
    return json(d)

@bp.route("/", methods=["GET"])
async def get_all(req):
    games = await drivers.RDB.get_all_games()
    logger.debug(games)
    if not games:
        return json([])
    return json(list(map(methodcaller("_asdict"), games)))
