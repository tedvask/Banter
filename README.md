# Google Messages для Linux

Минимальная обёртка над [messages.google.com](https://messages.google.com/web/): один Python-файл на GTK4 + WebKitGTK 6,
упакованный во flatpak поверх рантайма `org.gnome.Platform//50`. Для сборки нужен только `flatpak` и этот рантайм —
ни SDK, ни flatpak-builder. Само приложение весит ~5 КБ, в работе ~300 МБ RAM (почти всё — веб-процесс WebKit), 0% CPU в фоне.

## Сборка и установка

```sh
./build.sh
```

Повторный запуск пересобирает и обновляет установленное приложение. При первом запуске отсканируй QR-код телефоном:
«Сообщения» → профиль → «Сопряжение устройств».

## Поведение

- Закрытие окна (`Ctrl+W` или закрытие окна средствами sway) только прячет его: страница работает в фоне и присылает уведомления.
  Повторный запуск из лаунчера возвращает окно.
- Полный выход — `Ctrl+Q` или `flatpak kill io.github.favask.GoogleMessages`.
- `--background` — запуск без окна, для автозапуска.
- Клик по уведомлению открывает нужную беседу. Одна беседа — одно уведомление.
- Ссылки за пределами google.com открываются в браузере по умолчанию.
- `Ctrl+R` / `F5` — перезагрузить страницу.
- Скачанные файлы попадают в `~/Downloads`, данные приложения лежат в `~/.var/app/io.github.favask.GoogleMessages/`.

## Sway

```
assign [app_id="io.github.favask.GoogleMessages"] workspace number 2
exec flatpak run io.github.favask.GoogleMessages --background
```

## Доработка

- Настройки (URL, лимит памяти) — константы в начале `googlemessages.py`.
- Запуск без сборки: `python3 googlemessages.py`. Сначала закрой flatpak-версию (`Ctrl+Q`): у них общий ID приложения,
  и второй экземпляр просто покажет окно первого. Данные в этом режиме хранятся отдельно, в `~/.local/share/io.github.favask.GoogleMessages/`.
- `GOOGLEMESSAGES_DEBUG=1` добавляет «Inspect Element» в контекстное меню:
  `flatpak run --env=GOOGLEMESSAGES_DEBUG=1 io.github.favask.GoogleMessages`.

## Удаление

```sh
flatpak --user uninstall --delete-data io.github.favask.GoogleMessages
flatpak --user remote-delete googlemessages-local
```
