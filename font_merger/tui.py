from __future__ import annotations

import argparse
import locale
from dataclasses import dataclass
from pathlib import Path

from .detect import describe_source, detect_source
from .naming import default_blend_family


class TuiCancelled(Exception):
    pass


@dataclass
class TuiState:
    language: str = ""
    primary: str = ""
    secondary: str = ""
    family_name: str = ""
    output: str = "auto"
    instances: str = "auto"
    out_dir: str = "./out"
    detected_primary: str = ""
    detected_secondary: str = ""
    default_family_name: str = ""
    error: str = ""


TEXT = {
    "zh": {
        "subtitle": "Primary 保持不变，Secondary 只补 Primary 缺失的 Unicode glyph。",
        "footer": "方向键切换焦点，直接输入会编辑当前输入框，Enter 保存，Tab 路径补全，Esc 返回",
        "switch_language": "English",
        "inputs": "输入字体",
        "primary": "Primary 母字体",
        "secondary": "Secondary 并入字体",
        "settings": "命名与输出",
        "family": "输出 Family Name",
        "output": "输出模式",
        "instances": "实例模式",
        "out_dir": "输出目录",
        "summary": "确认运行",
        "back": "上一步",
        "next": "下一步",
        "run": "开始融合",
        "cancel": "取消",
        "choose_paths": "输入字体文件或 family 目录路径。长路径会在预览中省略显示，Tab 可补全。",
        "detected_primary": "Primary",
        "detected_secondary": "Secondary",
        "empty_paths": "Primary 和 Secondary 都不能为空。",
        "detect_failed": "检测失败",
        "no_detection": "请先完成字体检测。",
        "ready": "准备运行",
    },
    "en": {
        "subtitle": "Primary is preserved. Secondary fills only missing Unicode glyphs.",
        "footer": "Arrow keys move focus, typing edits the focused input, Enter saves, Tab completes paths, Esc goes back",
        "switch_language": "中文",
        "inputs": "Input Fonts",
        "primary": "Primary font",
        "secondary": "Secondary font",
        "settings": "Name And Output",
        "family": "Output Family Name",
        "output": "Output mode",
        "instances": "Instance mode",
        "out_dir": "Output directory",
        "summary": "Confirm Run",
        "back": "Back",
        "next": "Next",
        "run": "Run",
        "cancel": "Cancel",
        "choose_paths": "Enter font files or family directories. Long paths wrap inside the input field, Tab completes.",
        "detected_primary": "Primary",
        "detected_secondary": "Secondary",
        "empty_paths": "Primary and Secondary cannot be empty.",
        "detect_failed": "Detection failed",
        "no_detection": "Finish font detection first.",
        "ready": "Ready to run",
    },
}


def run_tui(args: argparse.Namespace) -> argparse.Namespace:
    try:
        _ensure_prompt_toolkit()
    except Exception as exc:
        raise RuntimeError("TUI requires prompt_toolkit. Install with: python -m pip install -r requirements.txt") from exc

    state = TuiState(
        language=_system_language(),
        primary=args.primary or "",
        secondary=args.secondary or "",
        family_name=args.family_name or "",
        output=args.output,
        instances=args.instances,
        out_dir=args.out_dir,
    )
    step = 0
    while True:
        if step == 0:
            action = _input_screen(state)
        elif step == 1:
            action = _settings_screen(state)
        else:
            action = _summary_screen(state)

        if action == "cancel":
            raise TuiCancelled()
        if action == "stay":
            continue
        if action == "language":
            state.language = "en" if state.language == "zh" else "zh"
            continue
        if action == "back":
            step = max(0, step - 1)
        elif action == "next":
            step = min(2, step + 1)
        elif action == "run":
            args.primary = state.primary
            args.secondary = state.secondary
            args.family_name = state.family_name or state.default_family_name
            args.output = state.output
            args.instances = state.instances
            args.out_dir = state.out_dir
            return args


def _ensure_prompt_toolkit() -> None:
    import prompt_toolkit  # noqa: F401


def _input_screen(state: TuiState) -> str:
    from prompt_toolkit.completion import PathCompleter
    from prompt_toolkit.widgets import Label, TextArea

    primary = _path_area(state.primary, "primary")
    secondary = _path_area(state.secondary, "secondary")

    def before_exit() -> None:
        state.primary = _clean_path_text(primary.text)
        state.secondary = _clean_path_text(secondary.text)
        if not state.primary or not state.secondary:
            state.error = _t(state, "empty_paths")
        else:
            _detect_sources_into_state(state)

    return _run_screen(
        state,
        title=_t(state, "inputs"),
        body=[
            Label(_t(state, "choose_paths")),
            Label(""),
            Label(_t(state, "primary")),
            primary,
            Label(""),
            Label(_t(state, "secondary")),
            secondary,
        ],
        focus=primary,
        before_exit=before_exit,
        show_back=False,
        text_fields=[primary, secondary],
    )


def _detect_sources_into_state(state: TuiState) -> None:
    if state.primary and state.secondary:
        try:
            primary_source = detect_source(Path(state.primary))
            secondary_source = detect_source(Path(state.secondary))
            state.detected_primary = describe_source(primary_source)
            state.detected_secondary = describe_source(secondary_source)
            state.default_family_name = default_blend_family(primary_source.faces[0], secondary_source.faces[0])
            state.error = ""
        except Exception as exc:
            state.error = f"{_t(state, 'detect_failed')}: {exc}"


def _settings_screen(state: TuiState) -> str:
    from prompt_toolkit.widgets import Label, RadioList, TextArea

    if not state.detected_primary and state.primary and state.secondary:
        _detect_sources_into_state(state)

    family = _text_area(state.family_name or state.default_family_name, "family", height=1)
    output = RadioList(
        values=[
            ("auto", "auto"),
            ("static", "static"),
            ("variable", "variable (experimental)"),
        ],
        default=state.output,
    )
    instances = RadioList(
        values=[
            ("auto", "auto"),
            ("named", "named"),
            ("custom", "custom"),
        ],
        default=state.instances,
    )
    out_dir = _path_area(state.out_dir, "out_dir", height=2)

    def before_exit() -> None:
        state.family_name = family.text.strip() or state.default_family_name
        state.output = output.current_value
        state.instances = instances.current_value
        state.out_dir = _clean_path_text(out_dir.text) or "./out"

    return _run_screen(
        state,
        title=_t(state, "settings"),
        body=[
            Label(f"{_t(state, 'detected_primary')}: {state.detected_primary or '-'}"),
            Label(f"{_t(state, 'detected_secondary')}: {state.detected_secondary or '-'}"),
            Label(""),
            Label(_t(state, "family")),
            family,
            Label(""),
            Label(_t(state, "output")),
            output,
            Label(""),
            Label(_t(state, "instances")),
            instances,
            Label(""),
            Label(_t(state, "out_dir")),
            out_dir,
        ],
        focus=family,
        before_exit=before_exit,
        text_fields=[family, out_dir],
        choice_fields=[output, instances],
    )


def _summary_screen(state: TuiState) -> str:
    from prompt_toolkit.widgets import Label

    if not state.detected_primary:
        state.error = _t(state, "no_detection")

    body = [
        Label(_t(state, "ready")),
        Label(""),
        Label(f"{_t(state, 'primary')}: {_middle_ellipsis(state.primary)}"),
        Label(f"{_t(state, 'secondary')}: {_middle_ellipsis(state.secondary)}"),
        Label(f"{_t(state, 'family')}: {state.family_name or state.default_family_name}"),
        Label(f"{_t(state, 'output')}: {state.output}"),
        Label(f"{_t(state, 'instances')}: {state.instances}"),
        Label(f"{_t(state, 'out_dir')}: {_middle_ellipsis(state.out_dir)}"),
    ]
    return _run_screen(
        state,
        title=_t(state, "summary"),
        body=body,
        run_button=True,
        show_next=False,
    )


def _run_screen(
    state: TuiState,
    *,
    title: str,
    body: list,
    focus=None,
    before_exit=None,
    show_back: bool = True,
    show_next: bool = True,
    run_button: bool = False,
    text_fields: list | None = None,
    choice_fields: list | None = None,
) -> str:
    from prompt_toolkit.application import Application
    from prompt_toolkit.application.current import get_app
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.filters import Condition, has_focus
    from prompt_toolkit.widgets import Box, Button, Frame, Label

    text_fields = text_fields or []
    choice_fields = choice_fields or []
    active = {"id": None}

    def exit_with(action: str):
        def handler() -> None:
            if before_exit:
                before_exit()
            if action == "next" and state.error:
                get_app().exit(result="stay")
                return
            get_app().exit(result=action)

        return handler

    buttons = []
    buttons.append(Button(text=_t(state, "switch_language"), handler=exit_with("language")))
    if show_back:
        buttons.append(Button(text=_t(state, "back"), handler=exit_with("back")))
    if show_next:
        buttons.append(Button(text=_t(state, "next"), handler=exit_with("next")))
    if run_button:
        buttons.append(Button(text=_t(state, "run"), handler=exit_with("run")))
    buttons.append(Button(text=_t(state, "cancel"), handler=exit_with("cancel")))

    error_lines = [Label(""), Label(state.error)] if state.error else []
    root = HSplit(
        [
            Window(FormattedTextControl([("class:title", " FontMerger "), ("class:subtitle", _t(state, "subtitle"))]), height=1),
            Window(FormattedTextControl([("class:rule", " " + "=" * 76)]), height=1),
            Frame(Box(HSplit(body + error_lines, padding=0), padding=1), title=title),
            VSplit(buttons, padding=2),
            Window(FormattedTextControl([("class:footer", " " + _t(state, "footer"))]), height=1),
        ]
    )

    bindings = KeyBindings()

    @bindings.add("c-c")
    def _cancel(event) -> None:
        event.app.exit(result="cancel")

    navigation_mode = Condition(lambda: active["id"] is None)

    @bindings.add("right", filter=navigation_mode, eager=True)
    @bindings.add("down", filter=navigation_mode, eager=True)
    @bindings.add("c-down", eager=True)
    def _focus_next(event) -> None:
        event.app.layout.focus_next()

    @bindings.add("left", filter=navigation_mode, eager=True)
    @bindings.add("up", filter=navigation_mode, eager=True)
    @bindings.add("c-up", eager=True)
    def _focus_previous(event) -> None:
        event.app.layout.focus_previous()

    for field in text_fields:
        field.read_only = True

        @bindings.add("enter", filter=has_focus(field.buffer) & navigation_mode, eager=True)
        def _enter_text(event, field=field) -> None:
            _activate_text_field(active, field)
            event.app.invalidate()

        @bindings.add("<any>", filter=has_focus(field.buffer) & navigation_mode, eager=True)
        def _type_into_text(event, field=field) -> None:
            key = event.key_sequence[0].key
            data = event.data
            if key in {
                "up",
                "down",
                "left",
                "right",
                "tab",
                "s-tab",
                "escape",
                "enter",
                "f1",
                "f2",
                "f3",
                "f4",
                "f5",
                "f6",
                "f7",
                "f8",
                "f9",
                "f10",
                "f11",
                "f12",
            }:
                return
            _activate_text_field(active, field)
            if key in {"backspace", "c-h"}:
                field.buffer.delete_before_cursor()
            elif key == "delete":
                field.buffer.delete()
            elif data and _is_text_input(data):
                field.buffer.insert_text(data)
            event.app.invalidate()

        @bindings.add("enter", filter=has_focus(field.buffer) & ~navigation_mode, eager=True)
        def _save_text(event, field=field) -> None:
            active["id"] = None
            field.read_only = True
            event.app.invalidate()

    for field in choice_fields:
        @bindings.add("enter", filter=has_focus(field.window) & navigation_mode, eager=True)
        def _enter_choice(event, field=field) -> None:
            active["id"] = f"choice:{id(field)}"
            event.app.invalidate()

    @bindings.add("escape", filter=navigation_mode)
    @bindings.add("escape", "b")
    @bindings.add("f8")
    def _back(event) -> None:
        if show_back:
            event.app.exit(result="back")

    @bindings.add("escape", "l")
    @bindings.add("f2")
    def _language(event) -> None:
        if before_exit:
            before_exit()
        event.app.exit(result="language")

    if show_next:
        @bindings.add("escape", "n")
        @bindings.add("f9")
        def _next(event) -> None:
            if before_exit:
                before_exit()
            if state.error:
                event.app.exit(result="stay")
                return
            event.app.exit(result="next")

    if run_button:
        @bindings.add("escape", "r")
        @bindings.add("f10")
        def _run(event) -> None:
            if before_exit:
                before_exit()
            event.app.exit(result="run")

    app = Application(
        layout=Layout(root, focused_element=focus),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False,
        style=_style(),
    )
    return app.run()


def _style():
    from prompt_toolkit.styles import Style

    return Style.from_dict(
        {
            "title": "ansicyan bold",
            "subtitle": "ansibrightblack",
            "rule": "ansibrightblack",
            "frame.label": "ansiwhite bold",
            "button": "ansiblack bg:ansibrightcyan",
            "button.focused": "ansiwhite bg:ansiblue bold",
            "radio-selected": "ansicyan bold",
            "radio": "ansiwhite",
            "footer": "ansibrightblack",
        }
    )


def _t(state: TuiState, key: str) -> str:
    return TEXT[state.language][key]


def _text_area(text: str, name: str, height: int = 1):
    from prompt_toolkit.widgets import TextArea

    return TextArea(
        text=text,
        height=height,
        multiline=False,
        wrap_lines=True,
        read_only=True,
        name=name,
    )


def _activate_text_field(active: dict, field) -> None:
    active["id"] = field.buffer.name
    field.read_only = False
    field.buffer.cursor_position = len(field.buffer.text)


def _is_text_input(data: str) -> bool:
    if not data:
        return False
    if "\x1b" in data:
        return False
    return data.isprintable()


def _path_area(text: str, name: str, height: int = 3):
    from prompt_toolkit.completion import PathCompleter
    from prompt_toolkit.widgets import TextArea

    return TextArea(
        text=text,
        height=height,
        multiline=True,
        wrap_lines=True,
        read_only=True,
        completer=PathCompleter(expanduser=True),
        name=name,
    )


def _middle_ellipsis(value: str, limit: int = 68) -> str:
    if len(value) <= limit:
        return value
    keep = max(8, (limit - 3) // 2)
    return f"{value[:keep]}...{value[-keep:]}"


def _clean_path_text(value: str) -> str:
    cleaned = " ".join(value.replace("\r", "\n").splitlines()).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _system_language() -> str:
    lang = ""
    try:
        lang = locale.getlocale()[0] or ""
    except Exception:
        lang = ""
    if not lang:
        try:
            lang = locale.getdefaultlocale()[0] or ""
        except Exception:
            lang = ""
    return "zh" if lang.lower().startswith("zh") else "en"
