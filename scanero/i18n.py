"""Small runtime i18n layer (Russian source strings, English translation)."""
from __future__ import annotations

import locale
import os
import re
from typing import Any

_LANGUAGE = "ru"
_PREFERENCE = "system"
_HOOKS_INSTALLED = False

EN: dict[str, str] = {
    # Brand / shell
    "Scanero IP Сканер": "Scanero IP scanner",
    "Scanero IP Сканер · сканирование завершено": "Scanero IP scanner · scan complete",
    "Scanero IP Сканер · современный сканер локальной сети для Ubuntu.": "Scanero IP scanner · a modern local network scanner for Ubuntu.",
    "Локальная сеть": "Local network",
    "Нет подключения": "No connection",
    "Нет активного подключения": "No active connection",
    "Сеть не найдена": "Network not found",
    "Сканер": "Scanner",
    "Избранное": "Favorites",
    "История": "History",
    "Настройки": "Settings",
    "НАВИГАЦИЯ": "NAVIGATION",
    "ТЕКУЩАЯ СЕТЬ": "CURRENT NETWORK",
    "Репозиторий на GitHub": "GitHub repository",
    "ИНСПЕКТОР": "INSPECTOR",
    "ДЕЙСТВИЯ": "ACTIONS",
    "СЕРВИСЫ": "SERVICES",
    "СВЕДЕНИЯ": "DETAILS",
    "ВАША СЕТЬ": "YOUR NETWORK",
    "ОФОРМЛЕНИЕ": "APPEARANCE",
    "Репозиторий": "Repository",
    "Подключено": "Connected",
    "Недоступно": "Unavailable",
    "нет подключения": "no connection",
    "Wi-Fi": "Wi-Fi",
    "Виртуальный": "Virtual",
    "Ethernet": "Ethernet",
    # Page headers
    "СКАНИРОВАНИЕ": "SCANNING",
    "Сканирование": "Scanning",
    "Все устройства в вашей сети": "All devices on your network",
    "Быстрое сканирование, MAC-адреса, имена и открытые сервисы.": "Fast discovery, MAC addresses, names and open services.",
    "КОЛЛЕКЦИЯ": "COLLECTION",
    "Устройства, к которым вы хотите возвращаться.": "Devices you want to keep close at hand.",
    "АРХИВ": "ARCHIVE",
    "Архив": "Archive",
    "Коллекция": "Collection",
    "Параметры": "Preferences",
    "Имя": "Name",
    "Восстановить": "Restore",
    "Развернуть": "Expand",
    "Свернуть": "Collapse",
    "История уже пуста": "History is already empty",
    "Последние сканирования и сохранённые результаты.": "Recent scans and saved results.",
    "ПАРАМЕТРЫ": "PREFERENCES",
    "Скорость, обнаружение сервисов и данные приложения.": "Speed, service discovery and application data.",
    # Controls / filters
    "Сканировать": "Scan",
    "Остановить": "Stop",
    "Останавливаем сканирование…": "Stopping scan…",
    "Моя сеть": "My network",
    "192.168.1.0/24 или 192.168.1.10-192.168.1.100": "192.168.1.0/24 or 192.168.1.10-192.168.1.100",
    "Поиск по имени, IP, MAC…": "Search by name, IP, MAC…",
    "Детали": "Details",
    "Экспорт": "Export",
    "Сохранить отчёт": "Save report",
    "В сети": "Online",
    "Все адреса": "All addresses",
    "С сервисами": "With services",
    "Не в сети": "Offline",
    "Сервисы": "Services",
    "Время": "Time",
    "Все адреса · {total}": "All addresses · {total}",
    "С сервисами · {services}": "With services · {services}",
    "Избранное · {favs}": "Favorites · {favs}",
    "Найдено: {count}": "Found: {count}",
    "Детали сети": "Network details",
    "Показать или скрыть панель сведений": "Show or hide the details panel",
    # Stats
    "открытых портов": "open ports",
    "не отвечают": "not responding",
    "длительность": "duration",
    "устройств онлайн": "devices online",
    "из": "of",
    # Table
    "Устройство": "Device",
    "IP-адрес": "IP address",
    "MAC-адрес": "MAC address",
    "Статус": "Status",
    "Без имени": "Unnamed",
    "Неизвестное устройство": "Unknown device",
    "Устройство не в сети": "Device is offline",
    "порт": "port",
    "Открыть": "Open",
    "Открыть {name}": "Open {name}",
    "Нет доступных ресурсов": "No available resources",
    "Производитель": "Manufacturer",
    "Производитель неизвестен": "Unknown manufacturer",
    "NetBIOS": "NetBIOS",
    "Рабочая группа": "Workgroup",
    "ОС": "OS",
    "TTL": "TTL",
    "Тип": "Type",
    "Встроенная ОС": "Embedded OS",
    "RAW печать": "RAW printing",
    "Выключить…": "Shut down…",
    "Подсеть класса C из текущего адреса": "Class C subnet from the current address",
    "Общие папки": "Shared folders",
    "Общие папки (SMB)": "Shared folders (SMB)",
    "Сканировать всю подсеть {subnet}": "Scan the whole subnet {subnet}",
    "Сетевая ОС": "Network OS",
    "Сетевое устройство": "Network device",
    "Локальный адрес": "Local address",
    "Неизвестно": "Unknown",
    # Device kinds
    "Роутер": "Router",
    "Компьютер": "Computer",
    "Сервер": "Server",
    "Принтер": "Printer",
    "Смартфон": "Smartphone",
    "Планшет": "Tablet",
    "Телевизор": "TV",
    "Камера": "Camera",
    "IoT-устройство": "IoT device",
    # Inspector
    "Инспектор": "Inspector",
    "Выберите устройство": "Select a device",
    "Нажмите на строку в таблице, чтобы увидеть детали, сервисы и действия.": "Click a row in the table to see details, services and actions.",
    "Ваша сеть": "Your network",
    "Сведения": "Details",
    "Действия": "Actions",
    "Сервисы:": "Services:",
    "Открытые сервисы не обнаружены": "No open services found",
    "Файлы": "Files",
    "Веб": "Web",
    "Копировать": "Copy",
    "Выключить": "Shut down",
    "Добавить в избранное": "Add to favorites",
    "Удалить из избранного": "Remove from favorites",
    "Веб-интерфейс": "Web interface",
    "Удалённый рабочий стол": "Remote desktop",
    "Подключиться по SSH": "Connect via SSH",
    "Wake-on-LAN": "Wake-on-LAN",
    "Проверить пинг": "Ping device",
    "Скопировать сведения": "Copy details",
    "Копировать сведения": "Copy details",
    "Импорт избранного": "Import favorites",
    "Экспорт отчёта": "Export report",
    "Введите диапазон IP-адресов": "Enter an IP range",
    "Некорректный IP-адрес: {token}": "Invalid IP address: {token}",
    "Некорректный MAC-адрес": "Invalid MAC address",
    "Некорректный адрес: {token}": "Invalid address: {token}",
    "Некорректный диапазон: {token}": "Invalid range: {token}",
    "Конец диапазона меньше начала: {token}": "Range end is before start: {token}",
    "Диапазон не содержит адресов": "The range contains no addresses",
    "Слишком большой диапазон (максимум {n} адресов)": "Range is too large (maximum {n} addresses)",
    "Маска вида 192.168.1.* поддерживается только для последнего октета": "Wildcard is supported only in the last octet",
    "Поддерживается только одна звёздочка в адресе": "Only one wildcard is supported",
    "Поддерживаются только IPv4-адреса": "Only IPv4 addresses are supported",
    "Удалённое выключение": "Remote shutdown",
    "Открыть ресурс": "Open resource",
    # Empty / scan state
    "Готовы к сканированию": "Ready to scan",
    "Выберите диапазон и запустите сканирование": "Choose a range and start scanning",
    "Настроить диапазон": "Edit range",
    "Сканировать снова": "Scan again",
    "Сбросить фильтры": "Clear filters",
    "Ничего не найдено": "Nothing found",
    "Попробуйте изменить фильтр или поисковый запрос": "Try changing the filter or search query",
    "В этом диапазоне нет отвечающих устройств": "No devices responded in this range",
    "Сканируем сеть": "Scanning network",
    "Ищем устройства и открытые сервисы…": "Looking for devices and open services…",
    "Поиск устройств": "Discovering devices",
    "Определение сервисов": "Detecting services",
    "Сканирование сети…": "Scanning network…",
    "Сканирование завершено": "Scan complete",
    "Сканирование остановлено": "Scan stopped",
    "Сканирование уже выполняется": "Scan already running",
    "Сканирование сети": "Network scan",
    "Готово к работе": "Ready",
    "Готово": "Done",
    "Найдено": "Found",
    "Снимок от": "Snapshot from",
    "Снимок": "Snapshot",
    # Settings / appearance
    "Оформление": "Appearance",
    "Светлая, тёмная или системная тема интерфейса.": "Light, dark or system interface theme.",
    "Тема оформления": "Theme",
    "Системная": "System",
    "Тёмная": "Dark",
    "Светлая": "Light",
    "Системная подстраивается под оформление Ubuntu.": "System follows the Ubuntu appearance.",
    "Размер шрифта": "Font size",
    "Масштаб текста интерфейса от 85% до 120%.": "Interface text scale from 85% to 120%.",
    "Язык интерфейса": "Interface language",
    "Системный": "System",
    "Русский": "Russian",
    "English": "English",
    "Автоматически по языку системы. При смене приложение перезапустится.": "Automatically based on the system language. The app restarts when changed.",
    "Производительность": "Performance",
    "Баланс между скоростью и нагрузкой на сеть и процессор.": "Balance between speed and network/CPU load.",
    "Скорость сканирования": "Scan speed",
    "Больше потоков — быстрее, но заметнее нагрузка.": "More threads are faster but use more resources.",
    "Экономно": "Quiet",
    "Плавно": "Smooth",
    "Сбалансированно": "Balanced",
    "Быстро": "Fast",
    "Максимум": "Maximum",
    "Глубокое обнаружение": "Deep discovery",
    "Проверять TCP-порты, если хост не отвечает на ICMP.": "Probe TCP ports when a host does not answer ICMP.",
    "Обнаружение": "Discovery",
    "Какие данные собирать о найденных устройствах.": "What data to collect about discovered devices.",
    "Сканировать сервисы": "Scan services",
    "HTTP, HTTPS, SMB, SSH, RDP, FTP, печать и другие порты.": "HTTP, HTTPS, SMB, SSH, RDP, FTP, printing and other ports.",
    "Определять имена": "Resolve names",
    "Обратное DNS и mDNS-разрешение имён.": "Reverse DNS and mDNS name resolution.",
    "Запрашивать имя компьютера и рабочую группу Windows.": "Request the Windows computer and workgroup name.",
    "Имена из локальных сервисов, AirPlay, принтеров и NAS.": "Names from local services, AirPlay, printers and NAS.",
    "SSDP / UPnP": "SSDP / UPnP",
    "Дружественные имена телевизоров, роутеров и медиаустройств.": "Friendly names for TVs, routers and media devices.",
    "SNMP sysName": "SNMP sysName",
    "Читать имя сетевого оборудования и принтеров (community public).": "Read network equipment and printer names (community public).",
    "Порты для проверки": "Ports to scan",
    "Дополнительные сервисы для обнаружения.": "Additional services to detect.",
    "Порты TCP через запятую. По умолчанию — 18 популярных сервисов.": "Comma-separated TCP ports. Defaults to 18 popular services.",
    "Приложение": "Application",
    "Поведение интерфейса и уведомления.": "Interface behavior and notifications.",
    "Уведомления": "Notifications",
    "Показывать системное уведомление после завершения сканирования.": "Show a system notification when a scan finishes.",
    "Настройки по умолчанию": "Default settings",
    "Вернуть скорость, порты и параметры обнаружения.": "Restore speed, ports and discovery settings.",
    "Сбросить настройки": "Reset settings",
    "Данные": "Data",
    "Избранное и история хранятся локально на этом компьютере.": "Favorites and history are stored locally on this computer.",
    "Избранное и история": "Favorites and history",
    "Файлы находятся в ~/.config/scanero.": "Files are stored in ~/.config/scanero.",
    "Экспорт избранного": "Export favorites",
    "Импорт": "Import",
    "Очистить историю": "Clear history",
    "О программе": "About",
    "Сделано с вниманием к деталям · PyQt6 / Ubuntu": "Made with care · PyQt6 / Ubuntu",
    "Подробнее": "More",
    # Favorites / history
    "Нет устройств": "No devices",
    "Пока нет избранных устройств": "No favorites yet",
    "Добавьте устройства из результатов сканирования — они всегда будут под рукой.": "Add devices from scan results to keep them close at hand.",
    "Сканировать избранное": "Scan favorites",
    "Сохранённое устройство": "Saved device",
    "MAC неизвестен": "MAC unknown",
    "История пока пуста": "History is empty",
    "После первого сканирования здесь появятся сохранённые результаты.": "Saved results will appear here after the first scan.",
    "Повторить": "Repeat",
    # Dialogs
    "Выключить компьютер": "Shut down computer",
    "Учётная запись": "Account",
    "Пароль": "Password",
    "Администратор": "Administrator",
    "Принудительное выключение": "Force shutdown",
    "Перезагрузить вместо выключения": "Reboot instead of shutting down",
    "Сообщение пользователю (необязательно)": "Message to user (optional)",
    "Отмена": "Cancel",
    "Да": "Yes",
    "Нет": "No",
    "Отправляем команду…": "Sending command…",
    "Укажите имя пользователя.": "Enter a username.",
    "Команда выполнена": "Command completed",
    "Не удалось выполнить команду": "Command failed",
    "Закрыть": "Close",
    "Версия {version} · сканер сети для Ubuntu": "Version {version} · network scanner for Ubuntu",
    "Версия {version}": "Version {version}",
    # Updates
    "Доступно обновление": "Update available",
    "Вышла версия {version}. У вас установлена {current}.": "Version {version} is available. You have {current}.",
    "Что нового": "What's new",
    "Позже": "Later",
    "Обновить": "Update",
    "Открыть релиз": "Open release",
    "Скачиваем обновление…": "Downloading update…",
    "Устанавливаем обновление…": "Installing update…",
    "Обновление установлено. Перезапустите приложение.": "Update installed. Restart the application.",
    "Перезапустить": "Restart",
    "код {code}": "code {code}",
    "Не удалось запустить установку. Скачайте пакет вручную со страницы релиза.": "Could not start the installation. Download the package manually from the release page.",
    "Не удалось установить обновление: {error}": "Could not install the update: {error}",
    "Не удалось скачать обновление: {error}": "Could not download the update: {error}",
    "Проверить обновления": "Check for updates",
    "Проверять обновления": "Check for updates",
    "При запуске проверять новые версии на GitHub.": "Check GitHub for new versions on startup.",
    "Проверяем обновления…": "Checking for updates…",
    "Проверка обновлений уже выполняется": "An update check is already running",
    "У вас установлена последняя версия.": "You are running the latest version.",
    "Не удалось проверить обновления.": "Could not check for updates.",
    "Команда отправляется через Samba (net rpc) и работает для Windows-компьютеров с включённой службой удалённого реестра. Нужны права администратора.": "The command is sent via Samba (net rpc) and works for Windows computers with the remote registry service enabled. Administrator rights are required.",
    "Утилита net (samba-common-bin) не найдена в системе.": "The net utility (samba-common-bin) was not found.",
    # About body
    "Быстрый сканер локальной сети с современным интерфейсом. Находит устройства, определяет MAC-адреса и производителей, имена NetBIOS/DNS/mDNS/SSDP, открытые сервисы и операционные системы. Позволяет открывать общие папки, FTP, HTTP и RDP, отправлять Wake-on-LAN, выключать компьютеры удалённо, работать в тёмной или светлой теме и экспортировать отчёты.": "A fast local network scanner with a modern interface. It finds devices, determines MAC addresses and vendors, NetBIOS/DNS/mDNS/SSDP names, open services and operating systems. Open SMB/FTP/HTTP/RDP resources, send Wake-on-LAN packets, shut down computers remotely, use dark or light themes and export reports.",
    # Menus / tooltips
    "Выбрать сетевой интерфейс": "Choose network interface",
    "Подставить диапазон текущей сети": "Use the current network range",
    "Обновить список сетей": "Refresh network list",
    "Настройки сканирования": "Scan settings",
    "Сканировать всю подсеть": "Scan the whole subnet",
    "Сканировать этот адрес": "Scan this address",
    "Общие ресурсы не обнаружены": "No shared resources found",
    "У устройства не найдено открытых сервисов": "No open services were found on this device",
    "Сведения скопированы": "Details copied",
    "Traceroute": "Traceroute",
    # Toasts / notifications
    "Добавлено в избранное": "Added to favorites",
    "Удалено из избранного": "Removed from favorites",
    "Устройство удалено из избранного": "Device removed from favorites",
    "Сначала остановите сканирование": "Stop scanning first",
    "Сначала остановите текущее сканирование": "Stop the current scan first",
    "Сеть": "Network",
    "Загружен снимок от {date}": "Snapshot loaded from {date}",
    "История очищена": "History cleared",
    "Настройки сброшены": "Settings reset",
    "Неизвестен MAC-адрес для Wake-on-LAN": "No MAC address available for Wake-on-LAN",
    "Magic-пакет отправлен": "Magic packet sent",
    "Не удалось отправить пакет: {exc}": "Could not send packet: {exc}",
    "Нет данных для экспорта": "No data to export",
    "Список избранного пуст": "Favorites list is empty",
    "Отчёт сохранён: {name}": "Report saved: {name}",
    "Экспортировано: {count}": "Exported: {count}",
    "Импортировано устройств: {count}": "Devices imported: {count}",
    "Ошибка экспорта: {exc}": "Export error: {exc}",
    "Ошибка импорта: {exc}": "Import error: {exc}",
    "Не удалось сохранить: {exc}": "Could not save: {exc}",
    "Ошибка: {message}": "Error: {message}",
    "Ошибка сканирования": "Scan error",
    "Большой диапазон": "Large range",
    "Будет просканировано {count} адресов. Это может занять несколько минут.\n\nПродолжить?": "About to scan {count} addresses. This may take a few minutes.\n\nContinue?",
    "Удалить все сохранённые результаты сканирований?": "Delete all saved scan results?",
    "Не удалось перезапустить приложение": "Could not restart the application",
    "Сканируем": "Scanning",
    "Проверим": "Checking",
    # Errors / terminal
    "Не найден терминал. Установите gnome-terminal или xterm.": "No terminal found. Install gnome-terminal or xterm.",
    "Не удалось запустить терминал.": "Could not start terminal.",
    "Не удалось запустить команду net rpc shutdown.": "Could not run net rpc shutdown.",
    "Не удалось запустить net rpc shutdown": "Could not run net rpc shutdown",
    "Не удалось определить локальную сеть. Укажите --range.": "Could not determine the local network. Specify --range.",
    "Не удалось запустить Remmina.": "Could not start Remmina.",
    "Не удалось запустить FreeRDP.": "Could not start FreeRDP.",
    "Не удалось запустить rdesktop.": "Could not start rdesktop.",
    "Не удалось запустить плеер.": "Could not start player.",
    "Не найден обработчик для этой ссылки": "No handler found for this link",
    "Не удалось открыть ресурс": "Could not open resource",
    "Утилита traceroute не установлена.": "traceroute is not installed.",
    "Wake-on-LAN отправлен": "Wake-on-LAN sent",
    "Нажмите Enter, чтобы закрыть…": "Press Enter to close…",
    # Export
    "CSV (Excel)": "CSV (Excel)",
    "JSON": "JSON",
    "HTML-отчёт": "HTML report",
    "Статус;Имя;IP-адрес;MAC-адрес;Производитель;Тип;ОС;Сервисы;NetBIOS;Рабочая группа": "Status;Name;IP address;MAC address;Manufacturer;Type;OS;Services;NetBIOS;Workgroup",
    "Отчёт о сканировании": "Scan report",
    "Устройств в сети": "Devices online",
    "Открытых сервисов": "Open services",
    "Диапазон сканирования": "Scan range",
    "Длительность": "Duration",
    "с": "s",
    "Неизвестный формат: {fmt}": "Unknown format: {fmt}",
    "Интерфейсы не найдены": "No interfaces found",
    "Интерфейс не найден: {name}": "Interface not found: {name}",
    "Ошибка диапазона: {exc}": "Range error: {exc}",
    "диапазон IP (например, 192.168.1.0/24)": "IP range (for example 192.168.1.0/24)",
    "сканировать подсеть интерфейса": "scan the interface subnet",
    "порты через запятую": "comma-separated ports",
    "не сканировать порты": "do not scan ports",
    "не определять имена": "do not resolve names",
    "сохранить отчёт JSON": "save a JSON report",
    "сохранить отчёт CSV": "save a CSV report",
    "сохранить отчёт HTML": "save an HTML report",
    "показать и выключенные адреса": "include offline addresses",
    "поиск": "discovery",
    "сервисы": "services",
    "Scanero IP scanner — сканер локальной сети": "Scanero IP scanner — local network scanner",
    "Scanero IP scanner — сканер локальной сети для Ubuntu\n\nГрафический режим:      python3 app.py\nCLI:                    python3 app.py --cli --range 192.168.1.0/24 [--json out.json]\nПомощь по CLI:          python3 app.py --cli --help\n\nСлужебные флаги демо/скриншотов: --demo --size 1460x900 --screenshot out.png": "Scanero IP scanner — local network scanner for Ubuntu\n\nGUI mode:               python3 app.py\nCLI:                    python3 app.py --cli --range 192.168.1.0/24 [--json out.json]\nCLI help:               python3 app.py --cli --help\n\nDemo/screenshot flags:  --demo --size 1460x900 --screenshot out.png",
    "Устройства не найдены": "No devices found",
    "Создано в Scanero IP scanner · сканер локальной сети для Ubuntu": "Created by Scanero IP scanner · local network scanner for Ubuntu",
}


_PATTERNS: list[tuple[re.Pattern[str], Any]] = [
    (re.compile(r"^Проверим (\d+) (\w+) в сети (.+)$"), lambda m: f"Checking {m.group(1)} {translate_text(m.group(2))} in {m.group(3)}"),
    (re.compile(r"^Сканирование (.+)…$"), lambda m: f"Scanning {m.group(1)}…"),
    (re.compile(r"^Сканируем (\d+) (\w+) · (.+)$"), lambda m: f"Scanning {m.group(1)} {translate_text(m.group(2))} · {m.group(3)}"),
    (re.compile(r"^(.+) · (\d+) из (\d+)$"), lambda m: f"{translate_text(m.group(1))} · {m.group(2)} of {m.group(3)}"),
    (re.compile(r"^(\d+) в сети$"), lambda m: f"{m.group(1)} online"),
    (re.compile(r"^(\d+(?:[.,]\d+)?) с$"), lambda m: f"{m.group(1)} s"),
    (re.compile(r"^(.+) · (\d+(?:[.,]\d+)?) с$"), lambda m: f"{translate_text(m.group(1))} · {m.group(2)} s"),
    (re.compile(r"^Снимок от (.+)$"), lambda m: f"Snapshot from {m.group(1)}"),
    (re.compile(r"^Сеть: (.+)$"), lambda m: f"Network: {translate_text(m.group(1))}"),
    (re.compile(r"^Диапазон: (.+)$"), lambda m: f"Range: {m.group(1)}"),
    (re.compile(r"^Версия (\d+\.\d+\.\d+)$"), lambda m: f"Version {m.group(1)}"),
    (re.compile(r"^Версия (\d+\.\d+\.\d+) · сканер сети для Ubuntu$"), lambda m: f"Version {m.group(1)} · network scanner for Ubuntu"),
    (re.compile(r"^(\d+) из (\d+)$"), lambda m: f"{m.group(1)} of {m.group(2)}"),
    (re.compile(r"^(.+) · (\d+)$"), lambda m: f"{translate_text(m.group(1))} · {m.group(2)}"),
    (re.compile(r"за (\d+(?:\.\d+)?) с"), lambda m: f"in {m.group(1)} s"),
    (re.compile(r"(\d+(?:\.\d+)?) с\b"), lambda m: f"{m.group(1)} s"),
    (re.compile(r"^Порт (\d+)$"), lambda m: f"Port {m.group(1)}"),
    (re.compile(r"^порт (\d+)$"), lambda m: f"port {m.group(1)}"),
    (re.compile(r"^Слишком большой диапазон \(максимум (\d+) адресов\)$"), lambda m: f"Range is too large (maximum {m.group(1)} addresses)"),
    (re.compile(r"^Конец диапазона меньше начала: (.+)$"), lambda m: f"Range end is before start: {m.group(1)}"),
    (re.compile(r"^Некорректный IP-адрес: (.+)$"), lambda m: f"Invalid IP address: {m.group(1)}"),
    (re.compile(r"^Некорректный диапазон: (.+)$"), lambda m: f"Invalid range: {m.group(1)}"),
    (re.compile(r"^Некорректный адрес: (.+)$"), lambda m: f"Invalid address: {m.group(1)}"),
    (re.compile(r"^Сохранено: (.+)$"), lambda m: f"Saved: {m.group(1)}"),
    (re.compile(r"^Не удалось сохранить: (.+)$"), lambda m: f"Could not save: {m.group(1)}"),
    (re.compile(r"^Не удалось отправить пакет: (.+)$"), lambda m: f"Could not send packet: {m.group(1)}"),
    (re.compile(r"^Не удалось (.+)$"), lambda m: f"Failed: {translate_text(m.group(1))}"),
    (re.compile(r"^Отчёт сохранён: (.+)$"), lambda m: f"Report saved: {m.group(1)}"),
    (re.compile(r"^Экспортировано: (.+)$"), lambda m: f"Exported: {m.group(1)}"),
    (re.compile(r"^Импортировано устройств: (.+)$"), lambda m: f"Devices imported: {m.group(1)}"),
    (re.compile(r"^Загружен снимок от (.+)$"), lambda m: f"Snapshot loaded from {m.group(1)}"),
    (re.compile(r"^найдено (.+)$", re.IGNORECASE), lambda m: f"Found {translate_text(m.group(1))}"),
    (re.compile(r"^Ошибка: (.+)$"), lambda m: f"Error: {translate_text(m.group(1))}"),
    (re.compile(r"\bиз\b"), lambda m: "of"),
    (re.compile(r"\bпорт\b"), lambda m: "port"),
    (re.compile(r"(\d+)\s+адрес(?:а|ов)?"), lambda m: f"{m.group(1)} address" + ("" if m.group(1) == "1" else "es")),
    (re.compile(r"(\d+)\s+устройств(?:о|а)?"), lambda m: f"{m.group(1)} device" + ("" if m.group(1) == "1" else "s")),
    (re.compile(r"(\d+)\s+сервис(?:а|ов)?"), lambda m: f"{m.group(1)} service" + ("" if m.group(1) == "1" else "s")),
    (re.compile(r"(\d+)\s+порт(?:а|ов)?"), lambda m: f"{m.group(1)} port" + ("" if m.group(1) == "1" else "s")),
]

_FRAGMENTS = [
    ("Сканирование уже выполняется", "Scan already running"),
    ("Сканирование остановлено", "Scan stopped"),
    ("Сканирование завершено", "Scan complete"),
    ("Сканирование сети", "Scanning network"),
    ("Останавливаем сканирование", "Stopping scan"),
    ("Поиск устройств", "Discovering devices"),
    ("Определение сервисов", "Detecting services"),
    ("Сканировать избранное", "Scan favorites"),
    ("Сканировать снова", "Scan again"),
    ("Сканировать этот адрес", "Scan this address"),
    ("Сканировать всю подсеть", "Scan the whole subnet"),
    ("Сканирование", "Scanning"),
    ("Сканировать", "Scan"),
    ("Сканируем", "Scanning"),
    ("Проверим", "Checking"),
    ("Найдено:", "Found:"),
    ("Готово:", "Done:"),
    ("Готово", "Done"),
    ("Все адреса", "All addresses"),
    ("С сервисами", "With services"),
    ("Избранное", "Favorites"),
    ("в сети", "online"),
    ("не отвечают", "offline"),
    ("открытых портов", "open ports"),
    ("длительность", "duration"),
    ("устройств онлайн", "devices online"),
    ("Производитель неизвестен", "Unknown manufacturer"),
    ("Сохранённое устройство", "Saved device"),
    ("MAC неизвестен", "MAC unknown"),
    ("Ошибка", "Error"),
    ("найдено", "found"),
    ("не удалось", "failed"),
    ("Неизвестно", "Unknown"),
    ("В сети", "Online"),
    ("Не в сети", "Offline"),
    ("Снимок", "Snapshot"),
    ("История", "History"),
    ("Настройки", "Settings"),
    ("Открыть", "Open"),
    ("Репозиторий на GitHub", "GitHub repository"),
    ("Виртуальный", "Virtual"),
    ("Без имени", "Unnamed"),
    ("Локальный адрес", "Local address"),
    ("вся подсеть", "whole subnet"),
]


def detect_system_language() -> str:
    try:
        from PyQt6.QtCore import QLocale

        name = QLocale.system().name().lower()
    except Exception:
        name = ""
    if not name:
        name = (
            os.environ.get("LC_ALL")
            or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG")
            or locale.getlocale()[0]
            or ""
        ).lower()
    return "ru" if name.startswith("ru") else "en"


def resolve_language(preference: str | None) -> str:
    if preference in ("ru", "en"):
        return preference
    return detect_system_language()


def set_language(preference: str | None) -> str:
    global _LANGUAGE, _PREFERENCE
    _PREFERENCE = preference or "system"
    _LANGUAGE = resolve_language(_PREFERENCE)
    return _LANGUAGE


def current_language() -> str:
    return _LANGUAGE


def language_preference() -> str:
    return _PREFERENCE


def translate_text(text: str) -> str:
    if not text or _LANGUAGE == "ru" or not re.search(r"[А-Яа-яЁё]", text):
        return text
    exact = EN.get(text)
    if exact is not None:
        return exact
    result = text
    for pattern, handler in _PATTERNS:
        if pattern.search(result):
            result = pattern.sub(handler, result)
    for source, target in _FRAGMENTS:
        if source in result:
            result = result.replace(source, target)
    return result


def tr(text: str, **kwargs: Any) -> str:
    translated = translate_text(text)
    if kwargs:
        try:
            return translated.format(**kwargs)
        except Exception:
            pass
    return translated


def install_text_hooks() -> None:
    """Translate texts set after the UI has been constructed.

    Text passed to widget constructors is translated by translate_widget_tree()
    once the main window exists.
    """
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QAbstractButton,
        QGroupBox,
        QLabel,
        QLineEdit,
        QTabWidget,
        QWidget,
    )

    def wrap_settext(cls):
        original = cls.setText

        def wrapped(self, text):
            return original(self, translate_text(text))

        cls.setText = wrapped

    wrap_settext(QLabel)
    wrap_settext(QAbstractButton)
    wrap_settext(QAction)

    original_title = QWidget.setWindowTitle

    def set_title(self, text):
        return original_title(self, translate_text(text))

    QWidget.setWindowTitle = set_title

    original_tooltip = QWidget.setToolTip

    def set_tooltip(self, text):
        return original_tooltip(self, translate_text(text))

    QWidget.setToolTip = set_tooltip

    original_placeholder = QLineEdit.setPlaceholderText

    def set_placeholder(self, text):
        return original_placeholder(self, translate_text(text))

    QLineEdit.setPlaceholderText = set_placeholder

    original_group = QGroupBox.setTitle

    def set_group(self, text):
        return original_group(self, translate_text(text))

    QGroupBox.setTitle = set_group

    original_tab = QTabWidget.setTabText

    def set_tab(self, index, text):
        return original_tab(self, index, translate_text(text))

    QTabWidget.setTabText = set_tab
    _HOOKS_INSTALLED = True


def translate_widget_tree(root: QWidget) -> None:
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QWidget

    widgets = [root] + root.findChildren(QWidget)
    for widget in widgets:
        if isinstance(widget, QLabel):
            widget.setText(translate_text(widget.text()))
        elif isinstance(widget, QAbstractButton):
            widget.setText(translate_text(widget.text()))
        elif isinstance(widget, QLineEdit):
            widget.setPlaceholderText(translate_text(widget.placeholderText()))
        title = widget.windowTitle()
        if title:
            widget.setWindowTitle(translate_text(title))
        tooltip = widget.toolTip()
        if tooltip:
            widget.setToolTip(translate_text(tooltip))
    for action in root.findChildren(QAction):
        if action.text():
            action.setText(translate_text(action.text()))


def translate_menu(menu) -> None:
    for action in menu.actions():
        if action.text():
            action.setText(translate_text(action.text()))
        submenu = action.menu()
        if submenu is not None:
            translate_menu(submenu)
