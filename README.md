# @basefrom50bot — Telegram-бот Старины Фифти

## Структура проекта

```
basefrom50bot/
├── main.py                  # Точка входа
├── config.py                # Конфигурация (читает .env)
├── requirements.txt         # Зависимости Python
├── .env.example             # Шаблон секретов
├── DEPLOY.md                # Инструкция по деплою
│
├── handlers/                # Обработчики команд и кнопок
│   ├── main_menu.py         # /start и главное меню
│   ├── start_rf.py          # Раздел "Старт с РФ" (мини-курс + лид-магнит)
│   ├── calculator.py        # Калькулятор стоимости
│   ├── guide.py             # ULTIMATE GUIDE и оплата
│   ├── simple.py            # Услуга выкупа и контакты
│   └── admin.py             # Админ-команды
│
├── db/
│   └── database.py          # Работа с SQLite
│
├── utils/
│   ├── keyboards.py         # Inline-клавиатуры
│   └── helpers.py           # Проверка подписки, расчёты
│
└── content/
    ├── texts.py             # Все тексты бота
    └── pdfs/                # PDF-файлы лид-магнита (создашь сам)
```

## Что меняется чаще всего

- **Тексты** — `content/texts.py`
- **Цены** — `config.py` (PRICE_ULTIMATE_GUIDE, PRICE_BUYOUT_SERVICE)
- **Курс юаня** — через команду `/set_rate 13.6` в боте

## Как обновить тексты на сервере

```bash
cd /opt/bot
nano content/texts.py
# редактируешь
# Ctrl+O, Enter, Ctrl+X для сохранения
systemctl restart basefrom50bot
```

## Админ-команды

После запуска бота напиши ему:
- `/stats` — статистика
- `/set_rate 13.6` — обновить курс юаня
- `/user 12345678` — инфа о юзере
- `/broadcast` — рассылка (с подтверждением)

## База данных

SQLite-файл `data/bot.db`. Бэкап:
```bash
cp /opt/bot/data/bot.db /opt/bot/data/bot.db.backup
```
