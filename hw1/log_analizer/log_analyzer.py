#!/usr/bin/env python3

# log_format ui_short '$remote_addr $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

import json
import logging
import os
import gzip
import time
import re
import signal

from collections import defaultdict
from datetime import date
from argparse import ArgumentParser
from string import Template


DEFAULT_FS_MODE = 0o766
DEFAULT_CONFIG_PATH = "./conf.json"
DEFAULT_CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "ANALYZER_LOG_DIR": "./analyzer_log",
    "LOG_DIR": "./log",
    "LAST_RUN_FILE": "./results/log_analyzer.ts",
    "REPORT_TEMPLATE": "./report.html"
}

LOGGER_FORMAT = "[%(asctime)s] %(levelname).1s %(message)s"
LOGGER_DATE_FORMAT = "%Y.%m.%d %H:%M:%S"

LOG_LINE_REGEXP = re.compile(
    r"^(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+"
    r"(?P<remote_user>[^\s]+)\s+"
    r"(?P<x_real_ip>[^\s]+)\s+"
    r"\[(?P<time_local>\d{1,2}/[a-zA-Z]{3}/\d{4}:\d{2}:\d{2}:\d{2}\s.\d{1,4})\]\s+"
    r"\"(?P<http_method>[A-Z]+)\s(?P<url>[^\s]+)\s(?P<http_version>[^\s]+)\"\s+"
    r"(?P<status>\d{3})\s+"
    r"(?P<body_bytes_sent>\d+)\s+"
    r"\"(?P<http_referer>[^\"]+)\"\s+"
    r"\"(?P<http_user_agent>[^\"]+)\"\s+"
    r"\"(?P<http_x_forwarded_for>[^\"]+)\"\s+"
    r"\"(?P<http_x_request_id>[^\"]+)\"\s"
    r"\"(?P<http_x_rb_user>[^\"]+)\"\s+"
    r"(?P<request_time>\d+\.?\d*)$"
)

LOG_FILENAME_REGEXP = re.compile(r"^nginx-access-ui\.log-(?P<log_date>\d{8}).*$")
REPORT_FILENAME_REGEXP = re.compile(r"^report-(?P<log_date>\d{4}\.\d{2}\.\d{2})\.html$")
REPORT_FILE_NAME_FORMAT = "report-{date}.html"
REPORT_PRECISION = 3


PARSING_ERROR_KEY = "parsing_error"
PARSING_SUCCESS_KEY = "parsing_success"
MAX_PARSING_ERR_PERCENT = .5
MIN_PARSING_ERR_COUNT = 5000

REQUEST_TIME_KEY = "request_time"
URL_KEY = "url"
TOTAL_KEY = "total"
COUNT_KEY = "count"
COUNT_PERC_KEY = "count_perc"
TIME_SUM_KEY = "time_sum"
TIME_PERC_KEY = "time_perc"
TIME_AVG_KEY = "time_avg"
TIME_MAX_KEY = "time_max"
TIME_MEDIAN_KEY = "time_med"


def get_last_logfile_path(config):
    log_dir = config.get("LOG_DIR")
    if log_dir is None:
        raise ValueError("Config parameter 'LOG_DIR' is required")

    all_filenames = (LOG_FILENAME_REGEXP.fullmatch(name) for name in os.listdir(log_dir))
    filenames = [filename.string for filename in all_filenames if filename]
    filenames.sort()

    if len(filenames) <= 0:
        return

    last_logfile = filenames.pop()
    full_path = os.path.join(log_dir, last_logfile)
    return full_path


def get_date_from_log_filename(log_filename):
    log_basename = os.path.basename(log_filename)
    log_match = LOG_FILENAME_REGEXP.fullmatch(log_basename)
    if log_match is None:
        message = "Invalid file name - {0}".format(log_filename)
        raise ValueError(message)

    log_groups = log_match.groupdict()
    log_date_string = log_groups.get("log_date")
    log_date = time.strptime(log_date_string, "%Y%m%d")
    return log_date


def is_processed_log(last_log_file, config):
    result_dir = config.get("REPORT_DIR")
    if result_dir is None:
        raise ValueError("Config parameter 'REPORT_DIR' is required")

    os.makedirs(result_dir, mode=DEFAULT_FS_MODE, exist_ok=True)

    all_filenames = (REPORT_FILENAME_REGEXP.fullmatch(name) for name in os.listdir(result_dir))
    filenames = [filename.string for filename in all_filenames if filename]
    if len(filenames) <= 0:
        return False

    log_date = get_date_from_log_filename(last_log_file)
    report_file_name = REPORT_FILE_NAME_FORMAT.format(date=time.strftime("%Y.%m.%d", log_date))

    if report_file_name in filenames:
        return True

    return False


def parse_config():
    parser = ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to config file")
    options = parser.parse_args()

    config = DEFAULT_CONFIG.copy()

    if not os.path.exists(options.config):
        return config

    with open(options.config, "r") as config_file:
        data = config_file.read()
        user_config = json.loads(data)
        config.update(user_config)

    return config


def setup_logger(config):
    log_dir = config.get("ANALYZER_LOG_DIR")
    if log_dir is None:
        logging.basicConfig(format=LOGGER_FORMAT, datefmt=LOGGER_DATE_FORMAT, level=logging.INFO)
        return

    os.makedirs(log_dir, mode=DEFAULT_FS_MODE, exist_ok=True)
    current_date = date.today().strftime("%Y%m%d")
    filename = "log_analyzer_{0}.log".format(current_date)
    filepath = os.path.join(log_dir, filename)

    logging.basicConfig(
        format=LOGGER_FORMAT,
        datefmt=LOGGER_DATE_FORMAT,
        filename=filepath,
        level=logging.INFO
    )

    logger = logging.getLogger("log_analyzer")
    return logger


def write_complete_timestamp(config):
    complete_timestamp = time.time()
    file_path = config.get("LAST_RUN_FILE")

    dirname = os.path.dirname(file_path)
    if dirname:
        os.makedirs(dirname, DEFAULT_FS_MODE, exist_ok=True)

    with open(file_path, "w") as result_file:
        result_file.write("{0}".format(complete_timestamp))

    os.utime(file_path, times=(complete_timestamp, complete_timestamp))


def get_median(times):
    length = len(times)
    if length <= 0:
        return

    if length == 1:
        return times[0]

    if length % 2 == 1:
        median_index = length // 2
        return times[median_index]

    # В списке четное количество элкментов. Берем среднее от двух элементов находящихся в середине списка.
    index = length // 2
    median = (times[index - 1] + times[index]) * .5
    return median


def get_stat_from_file(log_file, config, logger):
    request_times = defaultdict(list)
    parse_stat = defaultdict(float)
    log_stat = defaultdict(dict)
    total_stat = defaultdict(float)

    report_size = config.get("REPORT_SIZE")

    if report_size is None or report_size <= 0:
        raise ValueError("Config parameter 'REPORT_SIZE' is required")

    # Парсим построчно файл, считаем метрики которые можем посчитать на лету
    for line in log_file:
        err_percent = parse_stat[PARSING_ERROR_KEY] / (parse_stat[PARSING_SUCCESS_KEY] or 1)
        if parse_stat[PARSING_ERROR_KEY] >= MIN_PARSING_ERR_COUNT and err_percent >= MAX_PARSING_ERR_PERCENT:
            message = "exceed max paring errors limit: errors {0:.0f}, success {1:.0f}".format(
                parse_stat[PARSING_ERROR_KEY],
                parse_stat[PARSING_SUCCESS_KEY]
            )
            logger.error(message)
            return

        line_match = LOG_LINE_REGEXP.fullmatch(line.strip())
        if line_match is None:
            parse_stat[PARSING_ERROR_KEY] += 1
            continue

        line_groups = line_match.groupdict()
        request_time_str = line_groups.get(REQUEST_TIME_KEY, "")
        url = line_groups.get(URL_KEY)
        if url is None:
            parse_stat[PARSING_ERROR_KEY] += 1
            continue

        try:
            request_time = float(request_time_str)
        except ValueError:
            parse_stat[PARSING_ERROR_KEY] += 1
            continue

        try:
            log_stat[url][COUNT_KEY] += 1
        except KeyError:
            log_stat[url][COUNT_KEY] = 1.0

        try:
            log_stat[url][TIME_SUM_KEY] += request_time
        except KeyError:
            log_stat[url][TIME_SUM_KEY] = request_time

        if TIME_MAX_KEY not in log_stat[url] or request_time > log_stat[url][TIME_MAX_KEY]:
            log_stat[url][TIME_MAX_KEY] = request_time

        if URL_KEY not in log_stat[url]:
            log_stat[url][URL_KEY] = url

        total_stat[COUNT_KEY] += 1
        total_stat[TIME_SUM_KEY] += request_time
        request_times[url].append(request_time)

        parse_stat[PARSING_SUCCESS_KEY] += 1

    result = [url_stat for url_stat in log_stat.values()]
    result.sort(key=lambda url_stat: url_stat[TIME_SUM_KEY], reverse=True)
    result = result[:report_size]

    # Для первых n url-в с наибольшим суммарным временем обработки запросов, считаем метрики которые нельзя
    # посчитать по ходу парсинга (avg, медианы и т.д.)
    for url_stat in result:
        count_perc = url_stat[COUNT_KEY] / total_stat[COUNT_KEY] * 100
        time_perc = url_stat[TIME_SUM_KEY] / total_stat[TIME_SUM_KEY] * 100
        time_avg = url_stat[TIME_SUM_KEY] / url_stat[COUNT_KEY]

        url_stat[COUNT_PERC_KEY] = round(count_perc, REPORT_PRECISION)
        url_stat[TIME_PERC_KEY] = round(time_perc, REPORT_PRECISION)
        url_stat[TIME_AVG_KEY] = round(time_avg, REPORT_PRECISION)
        url_stat[TIME_SUM_KEY] = round(url_stat[TIME_SUM_KEY], REPORT_PRECISION)

        url = url_stat[URL_KEY]
        request_times[url].sort()
        median = get_median(request_times[url])
        if median is not None:
            url_stat[TIME_MEDIAN_KEY] = round(median, REPORT_PRECISION)
        else:
            url_stat[TIME_MEDIAN_KEY] = None

    return result


def process_analyzing(log_file, config, logger):
    if log_file.endswith(".gz"):
        with gzip.open(log_file, "rt") as log:
            return get_stat_from_file(log, config, logger)

    with open(log_file, "r") as log:
        return get_stat_from_file(log, config, logger)


def create_report(stat, config, last_log_file, logger):
    report_dir = config.get("REPORT_DIR")
    if report_dir is None:
        raise ValueError("Config parameter 'REPORT_DIR' is required")

    template_path = config.get("REPORT_TEMPLATE")
    if template_path is None:
        raise ValueError("Config parameter 'REPORT_TEMPLATE' is required")

    os.makedirs(report_dir, mode=DEFAULT_FS_MODE, exist_ok=True)

    log_date = get_date_from_log_filename(last_log_file)
    report_filename = REPORT_FILE_NAME_FORMAT.format(date=time.strftime("%Y.%m.%d", log_date))
    report_path = os.path.join(report_dir, report_filename)

    if os.path.exists(report_path):
        message = "File {0} already exists".format(report_path)
        raise FileExistsError(message)

    with open(template_path) as template_file:
        report_content = template_file.read()

    report_template = Template(report_content)
    rendered_report = report_template.safe_substitute(table_json=stat)

    with open(report_path, "w") as report_file:
        report_file.write(rendered_report)

    logger.info("Report successfully created - {0}".format(report_path))


def get_signals_handler(logger, current_signal_handler):
    def handler(signum, frame):
        logger.error("Got signal {0}".format(signum))
        current_signal_handler(signum, frame)

    return handler


def main():
    config = parse_config()
    logger = setup_logger(config)

    try:
        signal.signal(signal.SIGINT, get_signals_handler(logger, signal.getsignal(signal.SIGINT)))
        signal.signal(signal.SIGTERM, get_signals_handler(logger, signal.getsignal(signal.SIGTERM)))

        last_log_file = get_last_logfile_path(config)

        if last_log_file is None:
            logger.info("No logs for analyzing")
            return

        if is_processed_log(last_log_file, config):
            logger.info("No logs for processing")
            return

        logger.info("Start processing {0}".format(last_log_file))
        stat = process_analyzing(last_log_file, config, logger)
        logger.info("Statistic collected for {0}".format(last_log_file))

        create_report(stat, config, last_log_file, logger)
        write_complete_timestamp(config)

        logger.info("Processing successfully completed")

    except Exception as e:
        logging.exception("Runtime error: %s", e)
        exit(1)


if __name__ == "__main__":
    main()
