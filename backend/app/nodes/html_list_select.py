from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import SELECTOR_TYPE_OPTIONS
from app.nodes.registry import register


def codegen_html_list_select(ctx: CodegenContext) -> str:
    params = ctx.params
    trigger_selector = resolve_selector(ctx, "triggerSelector", "triggerSelectorType")
    mode = params.get("mode") or "single"
    match_exact = (params.get("matchType") or "exact") == "exact"
    bypass = bool(params.get("bypassOnFailure"))
    clear_checked = params.get("clearCheckedBeforeSelect") is not False

    clear_raw = (params.get("clearSelector") or "").strip()
    container_raw = (params.get("listContainerSelector") or "").strip()
    # get_by_text (not a `<li>`-specific search) deliberately: the visible text of a
    # menu item is usually wrapped in a child <span>/<div>, and clicking that more
    # specific element still triggers the <li>'s own click handler via event bubbling
    # — no need to climb back up to the ancestor <li> ourselves. Ambiguity (more than
    # one match) and "not found" both surface as Playwright's own clear native errors
    # (strict-mode violation / timeout waiting to be visible) — nothing extra to
    # implement for that.
    base_expr = (
        f"{ctx.target_var}.locator({resolve_selector(ctx, 'listContainerSelector', 'listContainerSelectorType')})"
        if container_raw
        else ctx.target_var
    )

    lines = [f"{ctx.target_var}.locator({trigger_selector}).click()"]
    if clear_raw:
        clear_selector = resolve_selector(ctx, "clearSelector", "clearSelectorType")
        lines.append(f"{ctx.target_var}.locator({clear_selector}).click()")

    if mode == "multiple" and clear_checked:
        # Reset only controls inside the configured list container. Custom UI
        # libraries (notably PrimeFaces) often prevent Playwright's uncheck() from
        # changing the hidden native input. A DOM click still toggles the input and
        # dispatches the component's own click/change handlers. Re-query after every
        # click because a master checkbox may clear the whole container at once.
        lines += [
            f"_checked_native = {base_expr}.locator(\"input[type='checkbox']:checked\")",
            "_clear_guard = 0",
            "while _checked_native.count() and _clear_guard < 1000:",
            "    _checked_native.first.evaluate(\"element => element.click()\")",
            "    _clear_guard += 1",
            "if _checked_native.count():",
            f"    raise RuntimeError(\"[{ctx.node_label}] could not clear all checked options inside the list container\")",
            f"_checked_aria = {base_expr}.locator(\"[role='checkbox'][aria-checked='true']:not(input)\")",
            "_clear_guard = 0",
            "while _checked_aria.count() and _clear_guard < 1000:",
            "    _checked_aria.first.click(force=True)",
            "    _clear_guard += 1",
            "if _checked_aria.count():",
            f"    raise RuntimeError(\"[{ctx.node_label}] could not clear all ARIA checked options inside the list container\")",
            f'print(f"[{ctx.node_label}] cleared existing checkbox selections")',
        ]

    result_var_raw = (params.get("resultVar") or "").strip()
    var = validate_identifier(result_var_raw, ctx, "Result Variable") if result_var_raw else None

    def click_lines_for(text_expr: str, on_success_extra: list[str]) -> list[str]:
        # Custom dropdown libraries commonly keep a second, hidden copy of the
        # option list mounted in the DOM. Playwright strict mode counts hidden
        # matches too, so filter them out before enforcing uniqueness/clicking.
        # If two *visible* options still match, click() correctly keeps raising a
        # strict-mode violation instead of choosing one arbitrarily.
        click_stmt = f"{base_expr}.get_by_text({text_expr}, exact={match_exact}).filter(visible=True).click()"
        if not bypass:
            return [click_stmt, f'print(f"[{ctx.node_label}] clicked " + {text_expr})', *on_success_extra]
        return [
            "try:",
            f"    {click_stmt}",
            f'    print(f"[{ctx.node_label}] clicked " + {text_expr})',
            *(f"    {line}" for line in on_success_extra),
            "except Exception as _e:",
            f'    print(f"[{ctx.node_label}] option not found, continuing (bypass on) — " + {text_expr} + ": " + str(_e))',
            *([f"    {var}['failed'].append({text_expr})"] if var else []),
        ]

    if mode == "multiple":
        rows = params.get("optionTexts") or []
        if not isinstance(rows, list) or not rows:
            raise CodegenError(f"Node '{ctx.node_label}': add at least one option text")
        if var:
            lines.append(f"{var} = {{'clicked': [], 'failed': []}}")
        for i, raw in enumerate(rows):
            text_raw = (raw or "").strip() if isinstance(raw, str) else ""
            if not text_raw:
                raise CodegenError(f"Node '{ctx.node_label}': option #{i + 1} is empty")
            text_expr = render_template_expr(text_raw, ctx)
            extra = [f"{var}['clicked'].append({text_expr})"] if var else []
            lines += click_lines_for(text_expr, extra)
    else:
        text_raw = (params.get("optionText") or "").strip()
        if not text_raw:
            raise CodegenError(f"Node '{ctx.node_label}': 'Option Text' is required")
        text_expr = render_template_expr(text_raw, ctx)
        # Recorded unconditionally (before the attempt, not on success) so `var` is
        # always defined even when bypassOnFailure lets a failed click fall through —
        # a later node referencing it would otherwise hit a NameError instead of just
        # seeing which text was targeted.
        if var:
            lines.append(f"{var} = {text_expr}")
        lines += click_lines_for(text_expr, [])

    return "\n".join(lines)


register(
    NodeSpec(
        type="html_list_select",
        label="Select List HTML",
        category="action",
        description=(
            "For custom HTML menus that aren't a real <select> — a trigger element you click to reveal a "
            "panel of <li> items, picked by their visible TEXT rather than a fragile position/index selector. "
            "Dropdown mode clicks one option (the menu closes itself, same as the site's own behavior); "
            "Checkbox mode can first clear every checked native or ARIA checkbox inside the configured panel, "
            "then clicks several options in sequence without reopening the menu between them. An ambiguous "
            "text match (more than one element on the page contains it) fails with Playwright's own clear "
            "error instead of guessing — use 'List Container Selector' to scope the search to just the "
            "menu's own panel when that happens."
        ),
        icon="list-select",
        params=[
            ParamField(key="triggerSelector", label="Trigger Selector (opens the menu)", type="text", required=True, placeholder="#status-dropdown"),
            ParamField(key="triggerSelectorType", label="Trigger Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(
                key="clearSelector",
                label="Clear Selector (optional — clicked before selecting)",
                type="text",
                placeholder="e.g. .clear-selection",
            ),
            ParamField(key="clearSelectorType", label="Clear Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(
                key="mode",
                label="Mode",
                type="select",
                default="single",
                options=[
                    {"value": "single", "label": "Dropdown (one option, menu closes)"},
                    {"value": "multiple", "label": "Checkbox (several options, stays open)"},
                ],
            ),
            ParamField(
                key="optionText",
                label="Option Text",
                type="text",
                supportsTemplate=True,
                placeholder="Aprovado",
                visibleWhen={"key": "mode", "equals": "single"},
            ),
            ParamField(
                key="optionTexts",
                label="Option Texts",
                type="textList",
                default=[],
                visibleWhen={"key": "mode", "equals": "multiple"},
            ),
            ParamField(
                key="clearCheckedBeforeSelect",
                label="Clear all checked options inside the list container before selecting",
                type="boolean",
                default=True,
                visibleWhen={"key": "mode", "equals": "multiple"},
            ),
            ParamField(
                key="matchType",
                label="Text Match",
                type="select",
                default="exact",
                options=[
                    {"value": "exact", "label": "Exact"},
                    {"value": "contains", "label": "Contains"},
                ],
            ),
            ParamField(
                key="listContainerSelector",
                label="List Container Selector (optional — scopes the search)",
                type="text",
                placeholder="e.g. .dropdown-panel",
            ),
            ParamField(key="listContainerSelectorType", label="List Container Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(
                key="bypassOnFailure",
                label="Bypass — continue the run even if an option isn't found",
                type="boolean",
                default=False,
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="selected",
                producesVariable=True,
            ),
        ],
        codegen=codegen_html_list_select,
    )
)
