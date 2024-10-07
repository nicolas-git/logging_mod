"""Logging module."""

# Standard library
import datetime
import inspect
import json

import logging
import logging.config
import os
import shutil
from pathlib import Path
from typing import Optional, OrderedDict

# Third-party
import coloredlogs  # type: ignore

LOG_LEVELS = {0: logging.ERROR, 1: logging.WARNING, 2: logging.INFO, 3: logging.DEBUG}


def read_json(fname: Path) -> OrderedDict:
    """Reads json file into json object

    Parameters
    ----------
    fname : path to json file
    """
    fname = Path(fname)
    with fname.open("rt", encoding="utf-8") as handle:
        return json.load(handle, object_hook=OrderedDict)

def get_logger() -> logging.Logger:
    """Get an instance of a logger with a name.

    Returns
    -------
    Logging instance.
    """
    filename = Path(inspect.stack()[1].filename).stem
    logger = logging.getLogger(filename)
    logger.setLevel(LOG_LEVELS[3])
    return logger


def setup_job_dir(
        output: Path, verbosity: int, log_id: Path, rm_exist: bool = True, optuna_override: Optional[bool] = False
) -> Path:
    """Sets a logging directory and configures logging. The dir id is set either
    incrementally or according to --log_id option.

    Parameters
    ----------
    log_id: int, str or None: Determine the id of the current logging session in
                        logs. If None, the current datetime of execution is
                        used.
    output: Path: Output job directory
    verbosity: int: Set default verbosity to print for all loggers.
                    From 0 (exceptions) to 3 (debug)
    rm_exist: bool: If existing job_dir should be removed or not.
    optuna_override: Optional bool: If True, the log file will only log the specified level, otherwise everything.

    Returns
    -------
    Path: Path to the log dir.
    """
    log_dir_base = output

    if not log_dir_base.exists():
        log_dir_base.mkdir(parents=True, exist_ok=True)

    if log_id is None:
        log_id = Path(datetime.datetime.now().strftime("%y%m%d_%H%M%S"))
    elif not isinstance(log_id, Path):
        raise ValueError

    log_dir = log_dir_base / log_id

    if log_dir.exists() and log_dir.is_dir() and rm_exist:
        shutil.rmtree(log_dir)

    log_dir.mkdir(parents=True, exist_ok=rm_exist)
    _setup_logging(log_dir, default_level=verbosity, optuna_override=optuna_override)
    logger = get_logger()
    logger.info(f"Setting up logs at {log_dir}")
    return log_dir


def _setup_logging(save_dir: Path, default_level: int, optuna_override: Optional[bool] = False) -> None:
    """Setup logging configuration according to json."""
    log_config = Path(os.path.dirname(__file__)) / "logger_config.json"
    if log_config.is_file():
        config = read_json(log_config)
        # modify logging paths based on run config
        for _, handler in config["handlers"].items():
            if "filename" in handler:
                handler["filename"] = str(save_dir / handler["filename"])
        # Create nice console output
        coloredlogs.DEFAULT_FIELD_STYLES = {
            "hostname": {"color": "magenta"},
            "programname": {"color": "cyan"},
            "name": {"color": "blue"},
            "levelname": {"color": "magenta", "bold": True},
            "asctime": {"color": "green"},
        }

        config["handlers"]["console"]["level"] = LOG_LEVELS[default_level]
        if optuna_override:
            config["handlers"]["info_file_handler"]["level"] = LOG_LEVELS[default_level]
        logging.config.dictConfig(config)
    else:
        print(f"Warning: logging configuration file is not found in {log_config}.")
        logging.basicConfig(level=default_level)


class MultiLineFormatter(logging.Formatter):
    """Multi-line formatter. Makes sure the console logs have correct indentation
    even for multiline logs."""

    def get_header_length(self, record):
        """Get the header length of a given record."""
        return len(
            super().format(
                logging.LogRecord(
                    name=record.name,
                    level=record.levelno,
                    pathname=record.pathname,
                    lineno=record.lineno,
                    msg="",
                    args=(),
                    exc_info=None,
                )
            )
        )

    def format(self, record):
        """Format a record with added indentation."""
        indent = " " * self.get_header_length(record)
        self.datefmt = "%Y-%m-%d,%H:%M:%S"
        head, *trailing = super().format(record).splitlines(True)
        return head + "".join(indent + line for line in trailing)
