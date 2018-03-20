#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# log_format ui_short '$remote_addr $remote_user $http_x_real_ip
#                     [$time_local] "$request" ' '$status $body_bytes_sent
#                     "$http_referer" ' '"$http_user_agent"
#                     "$http_x_forwarded_for"  "$http_X_REQUEST_ID"
#                     "$http_X_RB_USER" ' '$request_time';

import json
import logging
import os
import gzip
import time
import re
import io

from copy import deepcopy
from collections import defaultdict, namedtuple
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
    r"\[(?P<time_local>\d{1,2}/[a-zA-Z]{3}/"
    r"\d{4}:\d{2}:\d{2}:\d{2}\s.\d{1,4})\]\s+"  # time_local
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

LOG_FILENAME_REGEXP = re.compile(
    r"^nginx-access-ui\.log-(?P<log_date>\d{8})(\.gz|\.txt)?$"
)
REPORT_FILENAME_REGEXP = re.compile(
    r"^report-(?P<log_date>\d{4}\.\d{2}\.\d{2})\.html$"
)
REPORT_FILE_NAME_FORMAT = "report-{date}.html"
REPORT_PRECISION = 3


MAX_PARSING_ERR_PERCENT = .5


LogFileInfo = namedtuple("LogFileInfo", ("filepath", "date"))


def get_last_logfile_path(config):
    log_dir = config.get("LOG_DIR")
    if log_dir is None:
        raise ValueError("Config parameter 'LOG_DIR' is required")

    all_filenames = (
        LOG_FILENAME_REGEXP.fullmatch(name) for name in os.listdir(log_dir)
    )
    filtered_files = filter(
        lambda file_match: file_match is not None,
        all_filenames
    )

    latest_logfile_info = None
    for file_match in filtered_files:
        match_group = file_match.groupdict()
        log_date_string = match_group.get("log_date")
        log_date = time.strptime(log_date_string, "%Y%m%d")

        if latest_logfile_info is None or log_date > latest_logfile_info.date:
            latest_logfile_info = LogFileInfo(
                filepath=os.path.join(log_dir, file_match.string),
                date=log_date
            )

    return latest_logfile_info


def parse_arguments():
    parser = ArgumentParser()
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG_PATH, help="Path to config file"
    )
    cmd_arguments = parser.parse_args()
    return cmd_arguments


def parse_config(cmd_arguments):
    config = deepcopy(DEFAULT_CONFIG)

    if not os.path.exists(cmd_arguments.config):
        raise FileNotFoundError(
            "Config {0} does not exist".format(cmd_arguments.config)
        )

    with open(cmd_arguments.config, "r") as config_file:
        user_config = json.load(config_file)
        config.update(user_config)

    return config


def get_logger(config):
    filepath = None
    log_dir = config.get("ANALYZER_LOG_DIR")
    if log_dir is not None:
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
    if length == 0:
        return

    if length % 2 == 1:
        median_index = length // 2
        return times[median_index]

    # В списке четное количество элкментов. Берем среднее от двух элементов
    # находящихся в середине списка.
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
        line_match = LOG_LINE_REGEXP.fullmatch(line.strip())
        if line_match is None:
            parse_stat["parsing_error"] += 1
            continue

        line_groups = line_match.groupdict()
        request_time_str = line_groups.get("request_time", "")
        url = line_groups.get("url")
        if url is None:
            parse_stat["parsing_error"] += 1
            continue

        try:
            request_time = float(request_time_str)
        except ValueError:
            parse_stat["parsing_error"] += 1
            continue

        log_stat[url]["count"] = log_stat[url].get("count", 0) + 1.0

        time_sum = log_stat[url].get("time_sum", 0)
        log_stat[url]["time_sum"] = time_sum + request_time

        time_max = log_stat[url].get("time_max")
        if time_max is None or request_time > time_max:
            log_stat[url]["time_max"] = request_time

        log_stat[url].setdefault("url", url)

        total_stat["count"] += 1
        total_stat["time_sum"] += request_time
        request_times[url].append(request_time)

        parse_stat["parsing_success"] += 1

    success_delimiter = parse_stat["parsing_success"] or 1
    err_percent = parse_stat["parsing_error"] / success_delimiter
    if err_percent >= MAX_PARSING_ERR_PERCENT:
        message_format = "exceed max paring errors limit: errors {0:.0f}, " \
                         "success {1:.0f}"
        message = message_format.format(
            parse_stat["parsing_error"],
            parse_stat["parsing_success"]
        )
        logger.error(message)
        return

    result = sorted(
        log_stat.values(),
        key=lambda url_stat: url_stat["time_sum"],
        reverse=True
    )
    result = result[:report_size]

    # Для первых n url-в с наибольшим суммарным временем обработки запросов,
    # считаем метрики которые нельзя посчитать по ходу парсинга
    # (avg, медианы и т.д.)
    for url_stat in result:
        count_perc = url_stat["count"] / total_stat["count"] * 100
        time_perc = url_stat["time_sum"] / total_stat["time_sum"] * 100
        time_avg = url_stat["time_sum"] / url_stat["count"]

        url_stat["count_perc"] = round(count_perc, REPORT_PRECISION)
        url_stat["time_perc"] = round(time_perc, REPORT_PRECISION)
        url_stat["time_avg"] = round(time_avg, REPORT_PRECISION)
        url_stat["time_sum"] = round(url_stat["time_sum"], REPORT_PRECISION)

        url = url_stat["url"]
        request_times[url].sort()
        median = get_median(request_times[url])
        if median is not None:
            url_stat["time_med"] = round(median, REPORT_PRECISION)
        else:
            url_stat["time_med"] = None

    return result


def process_analyzing(last_logfile_info, config, logger):
    log_file = last_logfile_info.filepath
    file_open_func = gzip.open if log_file.endswith(".gz") else io.open

    with file_open_func(log_file, "rt") as log_file:
        stat = get_stat_from_file(log_file, config, logger)
        return stat


def create_report(stat, config, report_path, logger):
    template_path = config.get("REPORT_TEMPLATE")
    if template_path is None:
        raise ValueError("Config parameter 'REPORT_TEMPLATE' is required")

    os.makedirs(os.path.dirname(report_path), mode=DEFAULT_FS_MODE,
                exist_ok=True)

    with open(template_path) as template_file:
        report_content = template_file.read()

    report_template = Template(report_content)
    rendered_report = report_template.safe_substitute(table_json=stat)

    with open(report_path, "w") as report_file:
        report_file.write(rendered_report)

    logger.info("Report successfully created - {0}".format(report_path))


def main(config, logger):
    try:
        last_logfile_info = get_last_logfile_path(config)
    except FileNotFoundError as e:
        logger.error("{0} {1}".format(e.strerror, e.filename))
        return os.EX_OSFILE

    if last_logfile_info is None:
        logger.info("No logs for analyzing")
        write_complete_timestamp(config)
        return

    report_dir = config.get("REPORT_DIR")
    if report_dir is None:
        raise ValueError("Config parameter 'REPORT_DIR' is required")

    report_filename = REPORT_FILE_NAME_FORMAT.format(
        date=time.strftime("%Y.%m.%d", last_logfile_info.date)
    )
    report_path = os.path.join(report_dir, report_filename)

    if os.path.exists(report_path):
        logger.info("last log file {0} already processed".format(
            last_logfile_info.filepath)
        )
        write_complete_timestamp(config)
        return

    logger.info("Start processing {0}".format(last_logfile_info.filepath))
    stat = process_analyzing(last_logfile_info, config, logger)
    logger.info("Statistic collected for {0}".format(
        last_logfile_info.filepath))

    create_report(stat, config, report_path, logger)
    write_complete_timestamp(config)

    logger.info("Processing successfully completed")


if __name__ == "__main__":
    cmd_arguments = parse_arguments()
    config = parse_config(cmd_arguments=cmd_arguments)
    logger = get_logger(config)

    try:
        exit_code = main(config, logger)
    except:
        logging.exception("Runtime error: ")
        raise

    if exit_code is not None:
        exit(exit_code)
