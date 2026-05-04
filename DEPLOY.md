# 🚀 ИНСТРУКЦИЯ ПО ДЕПЛОЮ БОТА

Эта инструкция написана для тебя. Просто копируй команды по очереди и вставляй в терминал на сервере.

## 0. Что тебе нужно перед началом

- IP сервера: `5.129.247.209`
- Пароль root: тот что Timeweb прислал в письме
- Новый токен бота от @BotFather (ты уже получил)
- Твой Telegram ID — узнать у @userinfobot (просто напиши ему `/start`, пришлёт твой ID)
- ID закрытого канала: `-1003552231781` (уже есть)
- Номер кошелька YooMoney: `4100118793697883` (уже есть)

## 1. Подключение к серверу

### Если у тебя Windows:
- Открой стандартное приложение **PowerShell** (Win+R → `powershell` → Enter)
- Введи команду: `ssh root@5.129.247.209`
- Нажми **yes** на вопрос про fingerprint
- Введи пароль (он не отображается при вводе, это нормально — просто введи и Enter)

### Если у тебя Mac/Linux:
- Открой Терминал
- Введи: `ssh root@5.129.247.209`
- Дальше как на Windows

После успешного входа увидишь приглашение типа `root@msk-1-vm-urbx:~#`.

## 2. Базовая настройка сервера

Скопируй и выполни эти команды одну за другой (по одной строке):

```bash
# Обновляем пакеты
apt update && apt upgrade -y

# Ставим всё что нужно
apt install -y python3 python3-pip python3-venv git nano ufw

# Настраиваем firewall — открываем только SSH
ufw allow 22/tcp
ufw --force enable

# Создаём папку для бота
mkdir -p /opt/bot
cd /opt/bot
```

## 3. Загрузка кода бота

Я приложил архив с кодом отдельно. Чтобы загрузить его на сервер:

### Вариант А (рекомендую) — через Git

Если у тебя есть GitHub аккаунт, заливаешь туда код, а на сервере клонируешь. Подробнее напишу позже.

### Вариант Б — через файл напрямую

Открой **новый** PowerShell/Терминал (не закрывая старый!) и выполни:

```bash
# С твоего компьютера, заменив путь на правильный
scp /путь/к/basefrom50bot.zip root@5.129.247.209:/opt/bot/
```

Дальше **в первом окне** (где сервер):

```bash
cd /opt/bot
apt install -y unzip
unzip basefrom50bot.zip
ls
```

Должны увидеть файлы: `main.py`, `config.py`, `requirements.txt`, папки `handlers/`, `db/`, `content/`, `utils/`.

## 4. Установка зависимостей

```bash
cd /opt/bot

# Создаём виртуальное окружение Python
python3 -m venv venv

# Активируем его
source venv/bin/activate

# Ставим библиотеки
pip install -r requirements.txt
```

## 5. Настройка секретов

```bash
# Копируем шаблон в реальный .env
cp .env.example .env

# Открываем редактор
nano .env
```

Откроется текстовый редактор. **Вписываешь свои значения** в поля:

```env
BOT_TOKEN=сюда_токен_от_BotFather
ADMIN_ID=твой_id_из_userinfobot
MAIN_CHANNEL_USERNAME=basefrom50
PRIVATE_CHANNEL_ID=-1003552231781
YOOMONEY_WALLET=4100118793697883
YOOMONEY_TOKEN=
YOUTUBE_LINK=
TIKTOK_LINK=
```

**YOOMONEY_TOKEN пока оставь пустым** — мы подключим его позже когда будем тестировать платежи.

Сохранить и выйти из nano: **Ctrl+O** → Enter → **Ctrl+X**.

## 6. Тестовый запуск

```bash
# Создаём папку для БД и логов
mkdir -p data

# Запускаем бота
python3 main.py
```

Если всё ок — увидишь сообщения типа:
```
[INFO] База данных готова
[INFO] Бот @basefrom50bot запущен. Polling started.
```

**Открой Telegram, найди своего бота, напиши `/start`** — должен ответить!

Потыкай все кнопки чтобы проверить:
- Главное меню работает
- Калькулятор считает
- Старт с РФ запрашивает подписку (если ещё не подписан на канал)
- ULTIMATE GUIDE открывается
- Связь и каналы показывают ссылки

Если всё работает — нажми **Ctrl+C** в терминале чтобы остановить бота.

## 7. Запуск в режиме сервиса (24/7)

Чтобы бот работал постоянно даже после закрытия SSH, делаем systemd-сервис.

```bash
# Создаём конфиг сервиса
cat > /etc/systemd/system/basefrom50bot.service << 'EOF'
[Unit]
Description=basefrom50bot Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bot
ExecStart=/opt/bot/venv/bin/python3 /opt/bot/main.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/bot/data/bot.log
StandardError=append:/opt/bot/data/bot.log

[Install]
WantedBy=multi-user.target
EOF

# Регистрируем и запускаем
systemctl daemon-reload
systemctl enable basefrom50bot
systemctl start basefrom50bot

# Проверяем статус
systemctl status basefrom50bot
```

Должен быть статус `active (running)`. Жми **q** чтобы выйти из просмотра статуса.

## 8. Полезные команды для управления

```bash
# Статус бота
systemctl status basefrom50bot

# Перезапустить бота (после обновления кода)
systemctl restart basefrom50bot

# Остановить бота
systemctl stop basefrom50bot

# Запустить бота
systemctl start basefrom50bot

# Посмотреть логи в реальном времени
tail -f /opt/bot/data/bot.log

# Последние 100 строк лога
tail -n 100 /opt/bot/data/bot.log
```

## 9. Безопасность сервера (важно!)

После того как всё работает, обязательно:

```bash
# Меняем пароль root на свой
passwd

# Ставим fail2ban от брутфорса
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

Дальше — рекомендую отключить вход по паролю и настроить SSH-ключи. Но это отдельная история, можно сделать через неделю.

## 🚨 Если что-то не работает

1. **Бот не запускается** — посмотри логи: `tail -n 100 /opt/bot/data/bot.log`
2. **Бот не отвечает на /start** — проверь что в `.env` правильный BOT_TOKEN
3. **Ошибка про права в канале** — добавь бота админом в `@basefrom50` и в закрытый канал
4. **Любой непонятный момент** — скопируй ошибку из логов и пришли мне

## Что дальше — после успешного запуска

1. Заливаешь PDF-файлы в `/opt/bot/content/pdfs/` (это для лид-магнита)
2. Дорабатываешь тексты уроков в файле `content/texts.py`
3. Настраиваем YooMoney токен для проверки платежей
4. Тестируем оплату гайда
5. Запускаем!
