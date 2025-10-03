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
        parent_dir: Path, job_id: Path | None, verbosity_console: int, verbosity_logfile: int, overwrite_job_dir: bool = True,
) -> Path:
    """Sets a logging directory and configures logging. The dir id is set either
    incrementally or according to --log_id option.

    Parameters
    ----------
    output: Path: Output parent directory for job directories.
    job_id: Path: Job ID of the current execution. If None, the current datetime of execution is
                        used.

    verbosity_console: int: Set default verbosity level to print for console.
    verbosity_logfile: int: Set default verbosity level to print for log file.
    overwrite_job_dir: bool: If existing job_id (given that it is the same id) should be overwritten.
                        Everyhting except .hydra will be pruned.

    Returns
    -------
    Path: Path to the log dir.
    """
    log_dir_base = parent_dir

    if not log_dir_base.exists():
        log_dir_base.mkdir(parents=True, exist_ok=True)

    if job_id is None:
        job_id = Path(datetime.datetime.now().strftime("%y%m%d_%H%M%S"))
    elif not isinstance(job_id, Path):
        raise ValueError

    log_dir = log_dir_base / job_id

    # Make sure log directories are ok
    if log_dir.exists() and log_dir.is_dir() and overwrite_job_dir:
        _clear_dir_except(log_dir, keep={".hydra"})
    elif not log_dir.exists():
        log_dir.mkdir(parents=True)

    # Here we set up the actual logger
    _setup_logging(log_dir, default_level_console=verbosity_console, default_level_log_file=verbosity_logfile)
    logger = get_logger()
    logger.info(f"Setting up logs at {log_dir}")

    # Re-enable all loggers (they might have been disabled previously)
    for logger_obj in logging.root.manager.loggerDict.values():
        if isinstance(logger_obj, logging.Logger):
            logger_obj.disabled = False
    return log_dir

def _clear_dir_except(base: Path, keep: set[str] = {".hydra"}) -> None:
    """Remove all children of `base` except those in `keep` (by name)."""
    if not base.exists():
        return
    for child in base.iterdir():
        if child.name in keep:
            continue
        if child.is_file() or child.is_symlink():
            try:
                child.unlink()
            except FileNotFoundError:
                pass
        elif child.is_dir():
            shutil.rmtree(child, ignore_errors=True)

def _setup_logging(save_dir: Path, default_level_console: int, default_level_log_file: int) -> None:
    """Setup logging configuration according to json."""
    log_config = Path(os.path.dirname(__file__)) / "logger_config.json"
    if log_config.is_file():
        config = _read_json(log_config)
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

        config["handlers"]["console"]["level"] = LOG_LEVELS[default_level_console]
        config["handlers"]["info_file_handler"]["level"] = LOG_LEVELS[default_level_log_file]
        logging.config.dictConfig(config)
    else:
        print(f"Warning: logging configuration file is not found in {log_config}.")
        logging.basicConfig(level=default_level)



def _read_json(fname: Path) -> OrderedDict:
    """Reads json file into json object"""
    fname = Path(fname)
    with fname.open("rt", encoding="utf-8") as handle:
        return json.load(handle, object_hook=OrderedDict)

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
