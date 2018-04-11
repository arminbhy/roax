"""Module to implement resources."""

# Copyright © 2015–2018 Paul Bryan.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import roax.schema as s
#import roax.security
import wrapt

from collections import namedtuple
from roax.context import context

_Method = namedtuple("_Method", "function, kind, name, params, returns, security")


class Resource:
    """Base class for a resource."""

    def _register_method(self, function, kind=None, name=None, params=None, returns=None, security=None):
        """Register a resource method."""
        if self.methods.get((kind, name)):
            raise ResourceError("method already registered: {}".format((kind, name)))
        self.methods[(kind, name)] = _Method(function, kind, name, params, returns, security)

    def __init__(self):
        """Initialize the resource."""
        self.methods = {}
        for function in (attr for attr in (getattr(self, name) for name in dir(self)) if callable(attr)):
            try:
                method = function.roax_method
            except:
                continue  # ignore undecorated methods
            self._register_method(function, method.kind, method.name, method.params, method.returns, method.security)

    def call(self, kind, name=None, params={}):
        """Call a resource method."""
        try:
            function = self.methods[(kind, name)].function
        except KeyError as e:
            raise ResourceError("resource does not provide method", 400)
        return function(**params)


def method(*, kind=None, name=None, params=None, returns=None, security=None):
    """
    Decorate a function to register it as a resource method.

    kind: The kind of method being registered.
    name: The name of the query or action.
    params: The schema of function parameters.
    returns: The schema of function return value.
    security: TODO.
    """
    def decorator(function):
        _kind = kind
        _name = name
        split = function.__name__.split("_", 1)
        if _kind is None:
            _kind = split[0]
        if len(split) > 1:
            _name = _name or split[1]
        def wrapper(wrapped, instance, args, kwargs):
            with context({"type": "method", "kind": _kind, "name": _name}):
                #roax.security.apply(security)
                return wrapped(*args, **kwargs)
        decorated = s.validate(params, returns)(wrapt.decorator(wrapper)(function))
        try:
            getattr(function, "__self__")._register_method(decorated, _kind, _name, params, returns, security)
        except AttributeError:  # not bound to an instance
            function.roax_method = _Method(None, _kind, _name, params, returns, security)  # __init__ will register
        return decorated
    return decorator


class ResourceError(Exception):
    """Base class for all resource errors."""
    def __init__(self, detail, code):
        """
        detail: textual description of the error.
        code: the HTTP status most closely associated with the error.
        """
        super().__init__(self, detail)
        self.detail = detail
        self.code = code


class BadRequest(ResourceError):
    """Raised if the request is malformed."""
    def __init__(self, detail=None):
        super().__init__(detail, 400)


class Unauthorized(ResourceError):
    """Raised if the resource request requires authentication."""
    def __init__(self, realm, detail=None):
        super().__init__(detail, 401)
        self.realm = realm        


class Forbidden(ResourceError):
    """Raised if the resource request is refused."""
    def __init__(self, detail=None):
        super().__init__(detail, 403)

        
class NotFound(ResourceError):
    """Raised if the resource could not be found."""
    def __init__(self, detail=None):
        super().__init__(detail, 404)


class Conflict(ResourceError):
    """Raised if there is a conflict with the current state of the resource."""
    def __init__(self, detail=None):
        super().__init__(detail, 412)


class PreconditionFailed(ResourceError):
    """Raised if the revision provided does not match the current resource."""
    def __init__(self, detail=None):
        super().__init__(detail, 412)


class InternalServerError(ResourceError):
    """Raised if the server encountered an unexpected condition."""
    def __init__(self, detail=None):
        super().__init__(detail, 500)
