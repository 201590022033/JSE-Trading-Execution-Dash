"""Run the established offline unittest suite without manual provider probes."""
from pathlib import Path
import argparse
import os
import sys
import unittest
import socket
from contextvars import ContextVar

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'test_cloud', 'test_ost_login', 'test_reddit', 'test_sentiment', 'test_llm_sentiment'}


def test_modules(focused=False):
    return [p.stem for p in sorted(ROOT.glob('test_*.py'))
            if p.stem not in EXCLUDED and (not focused or p.stem.startswith('test_hr11_') or p.stem == 'test_dev_environment')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--focused', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['TRADING_OFFLINE_TESTS'] = '1'
    # Test imports must not probe broker, LLM or market services.
    def offline(*args, **kwargs):
        raise OSError('external sockets disabled by safe test runner')
    # CPython on Windows implements socketpair with an internal loopback
    # connection. Asyncio needs that pair even for wholly mocked transports.
    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair
    building_pair = ContextVar('building_offline_socketpair', default=False)

    def connect(sock, address):
        if building_pair.get() and isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
            return original_connect(sock, address)
        return offline()

    def socketpair(*args, **kwargs):
        token = building_pair.set(True)
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            building_pair.reset(token)

    socket.socket.connect = connect
    socket.socketpair = socketpair
    socket.socket.connect_ex = offline
    socket.create_connection = offline
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.loadTestsFromNames(test_modules(args.focused))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
