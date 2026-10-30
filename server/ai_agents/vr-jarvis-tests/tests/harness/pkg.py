'''Resolve the package under test. Default is this repo's ai_agents package; override with JARVIS_PKG.'''
import importlib
import os

PKG = os.getenv('JARVIS_PKG', 'ai_agents')


def mod(name):
    return importlib.import_module('%s.%s' % (PKG, name))
