import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import flet as ft
from typing import Any
from datetime import datetime


# ---------- Заглушка бэкенда ----------
def backend_load() -> list[dict[str, Any]]:
    return [
        {"ver": "1.0.0",       "desc": "Первый релиз",                "release": True,  "archive": False},
        {"ver": "1.0.1",       "desc": "Фикс парсера,\nмелкие правки", "release": True,  "archive": False},
        {"ver": "1.1.0-beta",  "desc": "Черновик новой ветки",         "release": False, "archive": False},
    ]


def backend_save(items: list[dict[str, Any]]) -> None:
    print("SAVE:", items)  # сюда придёт список dict


# ---------- UI ----------
COL_VER_W = 160   # ширина колонки "Версия"
COL_BOOL_W = 110  # ширина колонок "Релиз"/"Архив"


def main(page: ft.Page):
    page.title = "The Version"
    page.window.width = 980
    page.window.height = 640
    page.padding = 16

    # ----- контейнер строк, который будет скроллиться -----
    rows_box = ft.Column(
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # Ссылки на «живые» контролы строк, чтобы потом собрать данные при сохранении
    row_widgets: list[dict[str, ft.Control]] = []

    # Обработчики индикатора статуса

    # ----- статусная строка -----
    status = ft.Text("", italic=True, color=ft.Colors.GREY, size=13)

    def set_status(text: str, color=ft.Colors.GREY):
        status.value = text
        status.color = color or ft.Colors.ON_SECONDARY_CONTAINER
        page.update()

    def mark_dirty(e=None):
        set_status("Изменено", ft.Colors.ORANGE)

    def build_row(item: dict[str, Any]) -> ft.Row:
        ver = ft.TextField(
            value=str(item.get("ver", "")),
            read_only=True,
            width=COL_VER_W,
            dense=True,
            text_style=ft.TextStyle(font_family="monospace"),
            border=ft.InputBorder.NONE,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=6)
        )
        desc = ft.TextField(
            value=str(item.get("desc", "")),
            multiline=True,
            min_lines=1,
            max_lines=4,
            expand=True,
            dense=True,
            border=ft.InputBorder.NONE,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            on_change=mark_dirty
        )
        release = ft.Checkbox(value=bool(item.get("release", False)),
                              on_change=mark_dirty)
        archive = ft.Checkbox(value=bool(item.get("archive", False)),
                              on_change=mark_dirty)

        row_widgets.append({"ver": ver, "desc": desc, "release": release, "archive": archive})

        return ft.Row(
            controls=[
                ver,
                desc,
                ft.Container(content=release, width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
                ft.Container(content=archive, width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    # ----- шапка таблицы -----
    header = ft.Row(
        controls=[
            ft.Text("Версия",   width=COL_VER_W, weight=ft.FontWeight.BOLD),
            ft.Text("Описание", expand=True,     weight=ft.FontWeight.BOLD),
            ft.Container(ft.Text("Релиз",  weight=ft.FontWeight.BOLD), width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
            ft.Container(ft.Text("Архив",  weight=ft.FontWeight.BOLD), width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
        ],
    )

    # ----- перезагрузка данных -----
    def reload_data():
        rows_box.controls.clear()
        row_widgets.clear()
        items = backend_load()

        for i, item in enumerate(items):
            rows_box.controls.append(build_row(item))
            if i < len(items) - 1:
                rows_box.controls.append(ft.Divider(height=1, thickness=1))

        set_status('')
        page.update()

    def on_refresh(e: ft.ControlEvent):
        reload_data()

    def on_save(e: ft.ControlEvent):
        data = [
            {
                "ver":     r["ver"].value,
                "desc":    r["desc"].value,
                "release": r["release"].value,
                "archive": r["archive"].value,
            }
            for r in row_widgets
        ]
        backend_save(data)
        set_status(f"Сохранено в {datetime.now():%H:%M:%S}", ft.Colors.GREEN)
        page.update()

    # ----- верхняя панель с кнопками -----
    top_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.FilledButton("Обновить", icon=ft.Icons.REFRESH, on_click=on_refresh),
                ft.FilledTonalButton("Записать", icon=ft.Icons.CLOUD_UPLOAD, on_click=on_save),
                ft.Container(expand=True),
                status,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,  # <-- цвет панели из seed
        border_radius=None,
    )

    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.INDIGO,
        use_material3=True,
    )

    # ----- сборка страницы -----
    page.add(
        top_bar,
        ft.Divider(height=1),
        header,
        ft.Divider(height=1),
        rows_box

    )

    reload_data()


if __name__ == "__main__":
    ft.run(main)