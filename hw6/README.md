# IP2W

Сервис который по запросу на IPv4 адрес возвращает текущую погоду в городе, 
к которому относится IP.


#### Запуск

Для запуска нужно установить:

```bash
- uwsgi
- uwsgi-plugin-python36u
- nginx (конфиг взять из репозитория)
- python36u
- python36u-pip (с помощью pip установить зависимости из requirements.txt)
- python36u-devel
- gcc
- git

```

Установить пакет ip2w из репозитория (можно собрать через 
`./buildrpm.sh ip2w.spec`, но нужно будет еще установить `rpm-build`)

Создать конфиг для сервиса `/usr/local/etc/ip2w.json`

Конфиг - json вида:
```bash
{
    "LOGFILE": "/var/log/ip2w/error.log",
    "HTTP_CLIENT_TIMEOUT": 1,
    "HTTP_CLIENT_RETIES": 3,
    "HTTP_CLIENT_RETRY_TIMEOUT": 3,
    "WEATHER_API_KEY": "secret"
}
```

где:
- LOGFILE - путь к файлу с логами
- HTTP_CLIENT_TIMEOUT - timeout на получение ответа с внешнего API
- HTTP_CLIENT_RETIES - количество ретраев получения данных с API
- HTTP_CLIENT_RETRY_TIMEOUT - timeout между ретраями
- WEATHER_API_KEY - openWeatherMap api key


Запустить nginx и uwsgi:
```bash
systemctl start nginx
systemctl start ip2w

```


#### Запуск тестов

```bash
python3 test_ip2w.py
```
