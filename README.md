# Banter

Минимальный десктоп-клиент для [Google Messages](https://messages.google.com/web/): один Python-файл на GTK4 + WebKitGTK 6,
упакованный во flatpak поверх рантайма `org.gnome.Platform//50`. Для сборки нужен только `flatpak` и этот рантайм —
ни SDK, ни flatpak-builder. Само приложение весит ~5 КБ, в работе ~300 МБ RAM (почти всё — веб-процесс WebKit), 0% CPU в фоне.

Неофициальный проект, никак не связан с Google. Google Messages — товарный знак Google LLC.

## Сборка и установка

```sh
./build.sh
```

Повторный запуск пересобирает и обновляет установленное приложение. При первом запуске отсканируй QR-код телефоном:
«Сообщения» → профиль → «Сопряжение устройств».

## Поведение

- Закрытие окна (`Ctrl+W` или закрытие окна средствами sway) только прячет его: страница работает в фоне и присылает уведомления.
  Повторный запуск из лаунчера возвращает окно.
- Полный выход — `Ctrl+Q` или `flatpak kill io.github.tedvask.Banter`.
- `--background` — запуск без окна, для автозапуска.
- Клик по уведомлению открывает нужную беседу. Одна беседа — одно уведомление.
- Ссылки за пределами google.com открываются в браузере по умолчанию.
- `Ctrl+R` / `F5` — перезагрузить страницу.
- Скачанные файлы попадают в `~/Downloads`, данные приложения лежат в `~/.var/app/io.github.tedvask.Banter/`.

## Sway

```
assign [app_id="io.github.tedvask.Banter"] workspace number 2
exec flatpak run io.github.tedvask.Banter --background
```

## Доработка

- Настройки (URL, лимит памяти) — константы в начале `banter.py`.
- Запуск без сборки: `python3 banter.py`. Сначала закрой flatpak-версию (`Ctrl+Q`): у них общий ID приложения,
  и второй экземпляр просто покажет окно первого. Данные в этом режиме хранятся отдельно, в `~/.local/share/io.github.tedvask.Banter/`.
- `BANTER_DEBUG=1` добавляет «Inspect Element» в контекстное меню:
  `flatpak run --env=BANTER_DEBUG=1 io.github.tedvask.Banter`.

## Удаление

```sh
flatpak --user uninstall --delete-data io.github.tedvask.Banter
flatpak --user remote-delete banter-local
```
