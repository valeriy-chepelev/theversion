import ssl

ssl._create_default_https_context = ssl._create_unverified_context

import flet as ft
from typing import Any
from datetime import datetime

from yandex_tracker_client import TrackerClient
import functools
import time
import configparser
from natsort import natsorted


# ---------- Backend ----------


def retry_on_exception(exception=Exception, retries=3, delay=1):
    """
    Декоратор для повторных попыток выполнения функции при возникновении указанного исключения.
    ai-generated

    Параметры:
        exception : класс исключения (или кортеж классов), которые нужно перехватывать.
        retries   : максимальное количество попыток (включая первый вызов).
        delay     : пауза в секундах между попытками.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except exception as e:
                    last_exception = e
                    # print(f"Попытка {attempt}/{retries} завершилась ошибкой: {e}. "
                    #       f"Повтор через {delay} сек...")
                    time.sleep(delay)
            # Все попытки исчерпаны, выбрасываем последнее пойманное исключение
            raise last_exception

        return wrapper

    return decorator


class VerDataHost:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('theversion.ini')
        assert 'token' in config['DEFAULT']
        assert 'org' in config['DEFAULT']
        assert 'prefix' in config['DEFAULT']
        assert 'queues' in config['DEFAULT']
        self._filters = [u.strip() for u in config['DEFAULT']['prefix'].split(',')]
        self._prefix = self._filters[0]
        self._queues = [u.strip() for u in config['DEFAULT']['queues'].split(',')]
        if len(config['DEFAULT']['org']) < 15:  # Yes, a magic number! cloud_org_id usually have length 20
            self._client = TrackerClient(token=config['DEFAULT']['token'],
                                         org_id=config['DEFAULT']['org'])
        else:
            self._client = TrackerClient(token=config['DEFAULT']['token'],
                                         cloud_org_id=config['DEFAULT']['org'])
        if self._client.myself is None:
            raise Exception('Unable to connect Yandex Tracker.')

    def _read_ver(self):
        for q_name in self._queues:
            for v in self._client.queues[q_name].versions:
                if str(v.name).lower().startswith(self._prefix.lower()):
                    yield {'name': v.name,
                           'desc': '' if v.description is None else v.description,
                           'release': v.released,
                           'archive': v.archived}

    @retry_on_exception()
    def versions(self):
        v = dict()
        for ver in self._read_ver():
            if ver['name'] in v:
                v[ver['name']]['release'] = v[ver['name']]['release'] or ver['release']
                v[ver['name']]['archive'] = v[ver['name']]['archive'] or ver['archive']
                if v[ver['name']]['desc'] != ver['desc']:
                    if v[ver['name']]['desc'] == '':
                        v[ver['name']]['desc'] = ver['desc']
                    elif ver['desc'] != '':
                        v[ver['name']]['desc'] = '; '.join([v[ver['name']]['desc'],
                                                            ver['desc']])
            else:
                v.update({ver['name']:
                              {'desc': ver['desc'],
                               'release': ver['release'],
                               'archive': ver['archive']}})
        return v

    @property
    def queues(self):
        return self._queues

    @property
    def filters(self):
        return self._filters

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        assert value in self._filters
        self._prefix = value


# ---------- UI ----------

def backend_save(items: list[dict[str, Any]]) -> None:
    print("SAVE:", items)  # сюда придёт список dict
    time.sleep(5)


COL_VER_W = 160  # ширина колонки "Версия"
COL_BOOL_W = 110  # ширина колонок "Релиз"/"Архив"


def main(page: ft.Page):
    page.title = "The Version"
    page.window.width = 980
    page.window.height = 640
    page.padding = 16

    data_host = None

    def make_palette(dark: bool) -> dict:
        """Все цвета строк в одном месте. Меняйте только здесь."""
        if dark:
            return {
                "release_bg": ft.Colors.with_opacity(0.14, ft.Colors.GREEN),
                "release_fg": ft.Colors.GREEN_300,
                "normal_fg": None,
                "archive_bg": ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                "archive_fg": ft.Colors.GREY_600,
            }
        return {
            "release_bg": ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
            "release_fg": ft.Colors.GREEN_800,
            "normal_fg": None,
            "archive_bg": ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            "archive_fg": ft.Colors.GREY_500,
        }

    PALETTE = make_palette(page.theme_mode == ft.ThemeMode.DARK)

    def colors_for(is_release: bool, is_archive: bool) -> tuple[str | None, str]:
        """Приоритет: архив глушит всё; иначе релиз — зелёный; иначе — дефолт."""
        if is_archive and is_release:
            return PALETTE["archive_bg"], PALETTE["release_fg"]
        elif is_archive:
            return PALETTE["archive_bg"], PALETTE["archive_fg"]
        elif is_release:
            return PALETTE["release_bg"], PALETTE["release_fg"]
        return None, PALETTE["normal_fg"]

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

    def build_row(item: dict) -> ft.Container:
        is_release = bool(item.get("release", False))
        is_archive = bool(item.get("archive", False))
        bg, fg = colors_for(is_release, is_archive)

        ver = ft.TextField(
            value=str(item.get("ver", "")),
            read_only=True,
            width=COL_VER_W,
            dense=True,
            text_style=ft.TextStyle(font_family="monospace", color=fg),
            border=ft.NoInputBorder(),
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        )
        desc = ft.TextField(
            value=str(item.get("desc", "")),
            multiline=True,
            min_lines=1,
            max_lines=10,
            expand=True,
            dense=True,
            border=ft.NoInputBorder(),
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            on_change=mark_dirty,
            text_style=ft.TextStyle(color=fg),
        )
        release = ft.Checkbox(value=is_release)
        archive = ft.Checkbox(value=is_archive)

        row_widgets.append({"ver": ver, "desc": desc, "release": release, "archive": archive})

        inner = ft.Row(
            controls=[
                ver,
                desc,
                ft.Container(content=release, width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
                ft.Container(content=archive, width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        row_container = ft.Container(
            content=inner,
            bgcolor=bg,
            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
        )

        # --- живая перекраска при клике по чекбоксам ---
        def recolor(e=None):
            b, f = colors_for(release.value, archive.value)
            row_container.bgcolor = b
            ver.text_style.color = f
            desc.text_style.color = f
            page.update()

        def on_release(e):
            recolor()
            mark_dirty()

        def on_archive(e):
            recolor()
            mark_dirty()

        release.on_change = on_release
        archive.on_change = on_archive

        return row_container

    def build_filter_row() -> ft.Control:
        nonlocal data_host
        if data_host is None:
            data_host = VerDataHost()
        names = data_host.filters  # list[str]

        if not names:
            return ft.Container()  # пустой ряд, если фильтров нет

        seg = ft.SegmentedButton(
            selected=[data_host.prefix],
            allow_multiple_selection=False,
            allow_empty_selection=False,  # всегда что-то выбрано
            on_change=on_filter_change,
            segments=[ft.Segment(value=n, label=ft.Text(n)) for n in names],
        )
        return seg

    def on_filter_change(e):
        # SegmentedButton кладёт выбранное в .selected — это set
        new_filter = next(iter(e.control.selected))
        if new_filter == data_host.prefix:
            return
        data_host.prefix = new_filter
        # Без предупреждения: любые правки пользователя просто теряются
        on_refresh(None)

    # ----- шапка таблицы -----
    header = ft.Row(
        controls=[
            ft.Text("Версия", width=COL_VER_W, weight=ft.FontWeight.BOLD),
            ft.Text("Описание", expand=True, weight=ft.FontWeight.BOLD),
            ft.Container(ft.Text("Релиз", weight=ft.FontWeight.BOLD), width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
            ft.Container(ft.Text("Архив", weight=ft.FontWeight.BOLD), width=COL_BOOL_W, alignment=ft.Alignment.CENTER),
        ],
    )

    # ----- перезагрузка данных -----

    def on_refresh(e):
        if busy.visible:
            return  # защита от двойного клика
        set_busy(True)
        set_status("Обновление…")

        def work():
            nonlocal data_host
            try:
                if data_host is None:
                    data_host = VerDataHost()
                v = data_host.versions()
                items = [{'ver': key, 'desc': v[key]['desc'],
                          'release': v[key]['release'], 'archive': v[key]['archive']}
                         for key in natsorted([*v], reverse=True)]
            except Exception as ex:
                set_busy(False)
                set_status(f"Ошибка: {ex}", ft.Colors.RED)
                return

            # обновляем UI в главном потоке — Flet сам переключит контекст
            rows_box.controls.clear()
            row_widgets.clear()

            for i, item in enumerate(items):
                rows_box.controls.append(build_row(item))
                if i < len(items) - 1:
                    rows_box.controls.append(ft.Divider(height=1, thickness=1))

            set_busy(False)
            set_status("")

        page.run_thread(work)

    def do_save():
        """Собственно сохранение — вынесли из on_save, чтобы вызывать после подтверждения."""
        data = [
            {
                "ver": r["ver"].value,
                "desc": r["desc"].value,
                "release": r["release"].value,
                "archive": r["archive"].value,
            }
            for r in row_widgets
        ]

        set_busy(True)
        set_status("Сохранение…")

        def work():
            try:
                backend_save(data)
            except Exception as ex:
                set_busy(False)
                set_status(f"Ошибка: {ex}", ft.Colors.RED)
                return
            set_busy(False)
            set_status(f"Сохранено в {datetime.now():%H:%M:%S}", ft.Colors.GREEN)

        page.run_thread(work)

    def on_save(e):
        if busy.visible:
            return

        def close_dialog():
            page.pop_dialog()

        def on_confirm(e):
            close_dialog()
            do_save()

        def on_cancel(e):
            close_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Записать данные?"),
            content=ft.Text(
                "Содержимое таблицы будет отправлено на сервер\n"
                "и изменит версии в очередях "
                f"{', '.join(data_host.queues)}."
            ),
            actions=[
                ft.FilledButton("Отмена", on_click=on_cancel),
                ft.TextButton("Записать", on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.show_dialog(dlg)



    # ----- верхняя панель с кнопками -----

    busy = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)

    filter_row = ft.Container(
        content=build_filter_row(),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,  # чуть тише, чем top_bar
        border_radius=ft.BorderRadius.all(10),
    )

    top_bar = ft.Container(
        content=ft.Row(
            controls=[
                btn_refresh := ft.FilledButton("Обновить", icon=ft.Icons.REFRESH, on_click=on_refresh),
                btn_save := ft.FilledTonalButton("Записать", icon=ft.Icons.CLOUD_UPLOAD, on_click=on_save),
                ft.Container(expand=True),
                busy,
                status,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,  # <-- цвет панели из seed
        border_radius=None,
    )

    def set_busy(is_busy: bool):
        busy.visible = is_busy
        btn_refresh.disabled = is_busy
        btn_save.disabled = is_busy
        page.update()

    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.INDIGO,
        use_material3=True,
    )

    # ----- сборка страницы -----
    page.add(
        top_bar,
        filter_row,
        ft.Divider(height=1),
        header,
        ft.Divider(height=1),
        rows_box

    )

    on_refresh(None)


if __name__ == "__main__":
    ft.run(main)
