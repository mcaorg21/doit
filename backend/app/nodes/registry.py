from app.nodes.base import NodeSpec

NODE_REGISTRY: dict[str, NodeSpec] = {}


def register(spec: NodeSpec) -> NodeSpec:
    NODE_REGISTRY[spec.type] = spec
    return spec
