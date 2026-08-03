from fastapi import APIRouter

from app.nodes.registry import NODE_REGISTRY

router = APIRouter(prefix="/api/node-types", tags=["node-types"])


@router.get("")
def list_node_types():
    return [spec.to_public_dict() for spec in NODE_REGISTRY.values()]
