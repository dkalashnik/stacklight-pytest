import logging
from logging import config

from stacklight_tests.settings import CONSOLE_LOG_LEVEL

logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("paramiko.hostkeys").setLevel(logging.INFO)
logging.getLogger("iso8601.iso8601").setLevel(logging.INFO)


config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'minimal': {
            '()': logging.Formatter,
            'format':
                '[%(levelname)s]: %(message)s'
        },
        'default': {
            '()': logging.Formatter,
            'format':
                '%(asctime)s [%(levelname)s] '
                '%(name)s:%(lineno)s %(funcName)s: %(message)s'
        },
    },

    'handlers': {
        'console': {
            'level': CONSOLE_LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'minimal',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'level': logging.DEBUG,
            'class': 'logging.FileHandler',
            'filename': 'test.log',
            'formatter': 'default',
        },
    },
    'loggers': {
        '': {
            'handlers': ['file'],
            'level': logging.DEBUG,
        },
        'stacklight_tests': {
            'handlers': ['console'],
            'level': logging.INFO,
        }
    }
})
