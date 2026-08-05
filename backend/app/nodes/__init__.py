from app.nodes.registry import NODE_REGISTRY, register  # noqa: F401

from app.nodes import (  # noqa: F401,E402
    schedule_trigger,
    webhook_trigger,
    http_request,
    loop,
    open_browser,
    close_browser,
    switch_frame,
    goto,
    fill,
    select_option,
    click,
    hover,
    multi_input,
    wait,
    element_present,
    get_text,
    if_node,
    pause,
)
