# Scoring API

Command for start api server: `python3 api.py`

Command for run tests: `python3 -m unittest -v test.py`

Commands for run integration-test via docker-compose
```bash
sudo docker-compose run --rm api
sudo docker-compose down
```

### online_score
Request via curl
```bash
curl -X POST  -H "Content-Type: application/json" -d '
{
    "account": "horns&hoofs",
    "login": "h&f",
    "method": "online_score",
    "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95",
    "arguments":
        {
            "phone": "79175002040",
            "email": "john@gmail.com",
            "first_name": "John",
            "last_name": "Smith",
            "birthday": "01.01.1990",
            "gender": 1
        }
}' http://127.0.0.1:8080/method
```

### clients_interests
Request via curl
```bash
curl -X POST  -H "Content-Type: application/json" -d '
{
    "account": "horns&hoofs",
    "login": "h&f",
    "method": "clients_interests",
    "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95",
    "arguments": {
        "client_ids": [1,2,3,4],
        "date": "20.07.2017"
    }
}' http://127.0.0.1:8080/method
```

