# -*- coding: utf-8 -*-
"""
    tests.reqctx
    ~~~~~~~~~~~~~~~~~~~~~~

    Tests the request context.

    :copyright: (c) 2014 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""

import pytest

import flask
import unittest
try:
    from greenlet import greenlet
except ImportError:
    greenlet = None
from tests import TestFlask


class TestRequestContext(TestFlask):

    def test_teardown_on_pop(self):
        buffer = []
        app = flask.Flask(__name__)
        @app.teardown_request
        def end_of_request(exception):
            buffer.append(exception)

        ctx = app.test_request_context()
        ctx.push()
        assert buffer == []
        ctx.pop()
        assert buffer == [None]

    def test_teardown_with_previous_exception(self):
        buffer = []
        app = flask.Flask(__name__)
        @app.teardown_request
        def end_of_request(exception):
            buffer.append(exception)

        try:
            raise Exception('dummy')
        except Exception:
            pass

        with app.test_request_context():
            assert buffer == []
        assert buffer == [None]

    def test_proper_test_request_context(self):
        app = flask.Flask(__name__)
        app.config.update(
            SERVER_NAME='localhost.localdomain:5000'
        )

        @app.route('/')
        def index():
            return None

        @app.route('/', subdomain='foo')
        def sub():
            return None

        with app.test_request_context('/'):
            assert flask.url_for('index', _external=True) == \
                'http://localhost.localdomain:5000/'

        with app.test_request_context('/'):
            assert flask.url_for('sub', _external=True) == \
                'http://foo.localhost.localdomain:5000/'

        try:
            with app.test_request_context('/', environ_overrides={'HTTP_HOST': 'localhost'}):
                pass
        except ValueError as e:
            assert str(e) == (
                "the server name provided "
                "('localhost.localdomain:5000') does not match the "
                "server name from the WSGI environment ('localhost')"
            )

        app.config.update(SERVER_NAME='localhost')
        with app.test_request_context('/', environ_overrides={'SERVER_NAME': 'localhost'}):
            pass

        app.config.update(SERVER_NAME='localhost:80')
        with app.test_request_context('/', environ_overrides={'SERVER_NAME': 'localhost:80'}):
            pass

    def test_context_binding(self):
        app = flask.Flask(__name__)
        @app.route('/')
        def index():
            return 'Hello %s!' % flask.request.args['name']
        @app.route('/meh')
        def meh():
            return flask.request.url

        with app.test_request_context('/?name=World'):
            assert index() == 'Hello World!'
        with app.test_request_context('/meh'):
            assert meh() == 'http://localhost/meh'
        assert flask._request_ctx_stack.top is None

    def test_context_test(self):
        app = flask.Flask(__name__)
        assert not flask.request
        assert not flask.has_request_context()
        ctx = app.test_request_context()
        ctx.push()
        try:
            assert flask.request
            assert flask.has_request_context()
        finally:
            ctx.pop()

    def test_manual_context_binding(self):
        app = flask.Flask(__name__)
        @app.route('/')
        def index():
            return 'Hello %s!' % flask.request.args['name']

        ctx = app.test_request_context('/?name=World')
        ctx.push()
        assert index() == 'Hello World!'
        ctx.pop()
        try:
            index()
        except RuntimeError:
            pass
        else:
            assert 0, 'expected runtime error'

    def test_greenlet_context_copying(self):
        app = flask.Flask(__name__)
        greenlets = []

        @app.route('/')
        def index():
            reqctx = flask._request_ctx_stack.top.copy()
            def g():
                assert not flask.request
                assert not flask.current_app
                with reqctx:
                    assert flask.request
                    assert flask.current_app == app
                    assert flask.request.path == '/'
                    assert flask.request.args['foo'] == 'bar'
                assert not flask.request
                return 42
            greenlets.append(greenlet(g))
            return 'Hello World!'

        rv = app.test_client().get('/?foo=bar')
        assert rv.data == b'Hello World!'

        result = greenlets[0].run()
        assert result == 42

    def test_greenlet_context_copying_api(self):
        app = flask.Flask(__name__)
        greenlets = []

        @app.route('/')
        def index():
            reqctx = flask._request_ctx_stack.top.copy()
            @flask.copy_current_request_context
            def g():
                assert flask.request
                assert flask.current_app == app
                assert flask.request.path == '/'
                assert flask.request.args['foo'] == 'bar'
                return 42
            greenlets.append(greenlet(g))
            return 'Hello World!'

        rv = app.test_client().get('/?foo=bar')
        assert rv.data == b'Hello World!'

        result = greenlets[0].run()
        assert result == 42

    # Disable test if we don't have greenlets available
    if greenlet is None:
        test_greenlet_context_copying = None
        test_greenlet_context_copying_api = None


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestRequestContext))
    return suite
