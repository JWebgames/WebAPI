from sanic import Blueprint
from sanic.response import json
from ..middlewares import decode_jwt
from ..databases import KVS

bp = Blueprint("auth")
@bp.route("/register", methods=["POST"])
async def register(req):
    pass

@bp.route("/login", methods=["POST"])
async def login(req):
    pass

@decode_jwt
@bp.route("/logout", methods=["GET"])
async def logout(req, token_id):
    KVS.remoke_token(token_id)