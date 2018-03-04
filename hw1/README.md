# Анализатор логов

Запуск: `python log_analyzer.py --config conf.json`

Параметр `--config` - путь до json файла с конфигурацией.


Запуск тестов: `python3 -m unittest -v test_log_analyzer.py`


Конфиг:
* REPORT_SIZE - сколько url-в показывать в отчете
* REPORT_DIR - каталог в который будут складываться отчеты
* ANALYZER_LOG_DIR - каталог в котором будут логи самого скрипта
* LOG_DIR - католог в котором находятся логи веб сервиса
* LAST_RUN_FILE - путь до файла в котором будет храниться timestamp c временем окончания работы
* REPORT_TEMPLATE - путь до html шаблона, с помощью которого будет рендериться основной отчет

# Deco

Запуск: `python3 deco.py`