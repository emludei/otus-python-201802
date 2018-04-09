# Web-server

В основе реализации web-сервера лежит prefork модель + epoll.
При старте поднимается n worker-в в отдельных процессах.
Каждый worker в свою очередь асинхронно обрабатывает поступающие запросы с помощью epoll eventloop.
Все worker-ы слушают один и тот же адрес и порт.


#### Команда запуска

```bash
sudo chmod +x httpd.py
sudo ./httpd.py --log server.log -r document_root


usage: httpd.py [-h] [--host HOST] [--port PORT] [--log LOG] [-w WORKERS]
                [-r ROOT]

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           Host for listening
  --port PORT           Port for listening
  --log LOG             Log file path
  -w WORKERS, --workers WORKERS
                        Workers count
  -r ROOT, --root ROOT  document_root
```
#### Запуск тестов

Для тестов нужно клонировать репозиторий https://github.com/s-stupnikov/http-test-suite

и перенести директорию httptest в document_root.

Запускать тесты с помощью `httptest.py` который лежит в данном репозитории.
Перед запуском тестов нужно запустить сам сервер по аддресу localhost:80

```bash
./httptest.py
```

#### Результат нагрузочного тестирования

```bash
ab -n 50000 -c 100 -r -s 60 http://127.0.0.1:80/httptest/wikipedia_russia.html

This is ApacheBench, Version 2.3 <$Revision: 1706008 $>
Copyright 1996 Adam Twiss, Zeus Technology Ltd, http://www.zeustech.net/
Licensed to The Apache Software Foundation, http://www.apache.org/

Benchmarking 127.0.0.1 (be patient)
Completed 5000 requests
Completed 10000 requests
Completed 15000 requests
Completed 20000 requests
Completed 25000 requests
Completed 30000 requests
Completed 35000 requests
Completed 40000 requests
Completed 45000 requests
Completed 50000 requests
Finished 50000 requests


Server Software:        Some
Server Hostname:        127.0.0.1
Server Port:            80

Document Path:          /httptest/wikipedia_russia.html
Document Length:        954824 bytes

Concurrency Level:      100
Time taken for tests:   30.507 seconds
Complete requests:      50000
Failed requests:        0
Total transferred:      47748650000 bytes
HTML transferred:       47741200000 bytes
Requests per second:    1638.99 [#/sec] (mean)
Time per request:       61.013 [ms] (mean)
Time per request:       0.610 [ms] (mean, across all concurrent requests)
Transfer rate:          1528507.60 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    1   0.3      1       4
Processing:    13   60   7.4     58      99
Waiting:        1    3   2.1      3      41
Total:         14   61   7.5     59     100

Percentage of the requests served within a certain time (ms)
  50%     59
  66%     61
  75%     62
  80%     63
  90%     72
  95%     80
  98%     84
  99%     87
 100%    100 (longest request)

```
